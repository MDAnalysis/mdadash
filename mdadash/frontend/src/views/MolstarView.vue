<template>
  <div
    v-if="webglAvailable"
    class="position-fixed"
    :style="{ top: 'var(--v-layout-top)', left: '0px', zIndex: 1000 }"
  >
    <!-- Selection tab -->
    <v-sheet
      v-if="!selectionExpanded"
      class="tab-closed d-flex align-center justify-center cursor-pointer"
      color="primary"
      elevation="2"
      @click="selectionExpanded = true"
    >
      <v-icon size="small" color="white" :icon="mdiChevronRight"></v-icon>
    </v-sheet>
    <v-card
      v-else
      class="d-flex align-stretch align-center pa-0 mt-0"
      elevation="2"
      rounded="e-lg"
      width="350"
    >
      <v-sheet
        class="tab-open mt-0 d-flex align-center justify-center cursor-pointer"
        color="primary"
        elevation="2"
        @click="selectionExpanded = false"
      >
        <v-icon size="small" color="white" :icon="mdiChevronLeft"></v-icon>
      </v-sheet>
      <v-text-field
        :disabled="!runningState.connected"
        autofocus
        class="pa-2"
        v-model="selection"
        placeholder="Selection phrase..."
        variant="outlined"
        clearable
        :error-messages="selection_error"
        hint="Selection phrase"
        persistent-hint
        @change="updateSelection"
        @click:clear="updateSelection"
        :spellcheck="false"
        autocomplete="off"
        autocorrect="off"
        autocapitalize="off"
      ></v-text-field>
    </v-card>
  </div>
  <!-- Molstar plugin -->
  <div class="molstar-container">
    <div ref="molstarTarget" class="molstar-target"></div>
    <!-- Info overlay -->
    <v-overlay
      v-model="overlay"
      contained
      persistent
      class="align-center justify-center"
      z-index="0"
      :close-on-back="false"
    >
      <div class="text-center text-multi-line">
        <p>{{ overlayText }}</p>
      </div>
    </v-overlay>
  </div>
</template>

<script setup>
import { socket } from '@/socket'
import { inject, nextTick, ref, onMounted, onActivated, onDeactivated, onBeforeUnmount } from 'vue'
import { createPluginUI } from 'molstar/lib/mol-plugin-ui'
import { renderReact18 } from 'molstar/lib/mol-plugin-ui/react18'
import { PluginConfig } from 'molstar/lib/mol-plugin/config'
import { DefaultPluginUISpec } from 'molstar/lib/mol-plugin-ui/spec'
import { StateTransforms } from 'molstar/lib/mol-plugin-state/transforms'
import { mdiChevronLeft, mdiChevronRight } from '@mdi/js'
import 'molstar/build/viewer/molstar.css'

const webglAvailable = ref(true)
const overlay = ref(false)
const overlayText = ref('')
const selection = ref('')
const selection_error = ref('')
const selectionExpanded = ref(false)
const settings = inject('settings')
const runningState = inject('runningState')
const molstarTarget = ref(null)

let plugin = null
let baseModel = null
let coordinatesNode = null
let isResetting = false
let isRenderingFrame = false

function isWebGLAvailable() {
  try {
    const canvas = document.createElement('canvas')
    const attr = { failIfMajorPerformanceCaveat: true }
    const context = canvas.getContext('webgl2', attr) || canvas.getContext('webgl', attr)
    if (!context) return false
    context.getExtension('WEBGL_lose_context')?.loseContext()
    return true
  } catch (e) {
    console.log(e)
    return false
  }
}

const initMolstar = async () => {
  webglAvailable.value = isWebGLAvailable()
  if (!webglAvailable.value) {
    showOverlay(
      `WebGL not detected.

      Please reload the page and try.
      If problen persists, you might have to restart the browser.`,
    )
    return
  }

  if (!molstarTarget.value || plugin) {
    return
  }

  const customSpec = DefaultPluginUISpec()
  customSpec.config = [
    ...(customSpec.config || []),
    [PluginConfig.Viewport.ShowControls, true],
    [PluginConfig.Viewport.ShowSettings, true],
    [PluginConfig.Viewport.ShowSelectionMode, true],
    [PluginConfig.General.IsExpanded, false],
    [PluginConfig.Viewport.ShowAnimation, false],
    [PluginConfig.Viewport.ShowComponentControls, true],
  ]
  customSpec.layout = {
    initial: {
      showControls: false,
      controlsDisplay: 'landscape',
      regionState: {
        left: 'show',
        right: 'show',
        top: 'show',
        bottom: 'hidden',
      },
    },
  }

  try {
    plugin = await createPluginUI({
      target: molstarTarget.value,
      spec: customSpec,
      render: renderReact18,
    })
  } catch (error) {
    console.error('Failed to create Mol* Plugin UI:', error)
  }

  if (plugin) {
    plugin.layout.setProps({
      showControls: false,
      regionState: { left: 'collapsed', right: 'show', top: 'show', bottom: 'hidden' },
    })
    if (plugin.behaviors?.layout?.leftPanelTabName) {
      plugin.behaviors.layout.leftPanelTabName.next('help')
    }
    const canvas = molstarTarget.value.querySelector('canvas')
    if (canvas) {
      canvas.addEventListener('webglcontextlost', handleContextLost)
    }
  }
}

async function updateSelection() {
  if (plugin) {
    await plugin.clear()
  }
  showOverlay(`Updating selection...`)
  socket.emit('update_3dview_selection', selection.value || '')
}

const updateTopology = async (topology) => {
  const data = await plugin.builders.data.rawData({
    data: topology,
    label: 'Topology',
  })
  const trajectory = await plugin.builders.structure.parseTrajectory(data, 'gro')
  const hierarchy = await plugin.builders.structure.hierarchy.applyPreset(trajectory, 'default')
  if (!hierarchy) {
    console.error('No structure hierarchy')
    return
  }
  const modelNode = hierarchy.model
  baseModel = modelNode.cell.obj.data
  coordinatesNode = await plugin
    .build()
    .to(modelNode.cell.transform.ref)
    .apply(StateTransforms.Model.ModelWithCoordinates)
    .commit()
}

const update3dview = async (view) => {
  isResetting = true
  showOverlay('Updating view...')
  selection.value = view.inputs.selection
  selection_error.value = view.inputs.selection_error
  if (view.inputs.selection_error) {
    selectionExpanded.value = true
  }
  if (plugin) {
    await plugin.clear()
  }
  if (view.topology) {
    if (plugin) {
      await updateTopology(view.topology)
      plugin.managers.camera.reset()
    }
    hideOverlay()
  } else {
    showOverlay(`Topology not available.

    Please ensure you are connected and have a valid selection phrase.`)
  }
  isResetting = false
}

const load3dView = async () => {
  showOverlay('Loading...')
  const response = await socket
    .timeout(settings.value.dashboard_config.ui_request_timeout * 1000)
    .emitWithAck('load_3dview')
  if (response) {
    await update3dview(response)
    selectionExpanded.value = true
  } else {
    showOverlay(`Timeout waiting for server response. Please retry.`)
  }
}

const updatePositions = async (data) => {
  if (
    isResetting ||
    isRenderingFrame ||
    !baseModel ||
    !coordinatesNode ||
    !plugin?.state.data.cells.has(coordinatesNode.ref)
  ) {
    return
  }
  const positions = new Float32Array(data)
  const atomCount = baseModel.atomicConformation.x.length
  if (atomCount !== positions.length / 3) {
    // Topology changed
    return
  }
  // Reference: https://molstar.org/docs/plugin/transforms/custom-conformation/
  isRenderingFrame = true
  await plugin
    .build()
    .to(coordinatesNode)
    .update({
      atomicCoordinateFrame: {
        elementCount: atomCount,
        xyzOrdering: { isIdentity: true },
        x: positions.subarray(0, atomCount),
        y: positions.subarray(atomCount, atomCount * 2),
        z: positions.subarray(atomCount * 2, atomCount * 3),
      },
    })
    .commit()
  isRenderingFrame = false
}

async function handleContextLost(event) {
  event.preventDefault()
  if (plugin) {
    plugin.dispose()
    plugin = null
    molstarTarget.value.innerHTML = ''
    await initMolstar()
    if (plugin) {
      await load3dView()
    }
  }
}

function showOverlay(text) {
  overlayText.value = text
  overlay.value = true
}

function hideOverlay() {
  overlay.value = false
  overlayText.value = ''
}

onMounted(async () => {
  await initMolstar()
  if (plugin) {
    await load3dView()
  }
  socket.on('3dview', update3dview)
})

onActivated(() => {
  socket.on('positions', updatePositions)
  if (plugin?.canvas3d) {
    plugin.canvas3d.resume()
    nextTick(() => {
      plugin.canvas3d.handleResize()
    })
  }
})

onDeactivated(() => {
  socket.off('positions')
  if (plugin?.canvas3d) {
    plugin.canvas3d.pause()
  }
})

onBeforeUnmount(() => {
  socket.off('3dview')
  const canvas = molstarTarget.value?.querySelector('canvas')
  if (canvas) {
    canvas.removeEventListener('webglcontextlost', handleContextLost)
  }
  if (plugin) {
    plugin.dispose()
    plugin = null
  }
})
</script>

<style scoped>
/* multi-line overlay text */
.text-multi-line {
  white-space: pre-line;
}
/* Disable vuetify animations for selection input */
:deep(.v-field__clearable) {
  transition: none !important;
}
:deep(.v-input__details *) {
  transition: none !important;
}
/* Molstar container and target */
.molstar-container {
  width: 100%;
  height: calc(100vh - 128px);
  position: relative;
  display: block;
  overflow: hidden;
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}
.molstar-target {
  width: 100%;
  height: 100%;
  position: relative;
}
/* selection tab */
.tab-closed {
  width: 16px;
  height: 96px;
  margin-top: 0px;
  border-radius: 0 8px 8px 0;
}
.tab-open {
  width: 16px;
  margin-top: 0px;
}
/* Customize molstar plugin UI */
/* Hide logo that shows up when using plugin.clear() and no topology after */
:deep(.msp-logo) {
  display: none !important;
}
/* Hide the Home and State* buttons on left panel */
:deep(.msp-left-panel-controls-buttons button[title='Home']),
:deep(.msp-left-panel-controls-buttons button[title*='State']) {
  display: none !important;
}
/* Move the Help button to bottom so it is not blocked by selection tab */
:deep(.msp-left-panel-controls-buttons button[title*='Help']) {
  position: absolute !important;
  bottom: 32px !important;
}
/* Expand over app bar and sticky bar in fullscreen mode */
:deep(.msp-layout-expanded) {
  z-index: 3000 !important;
}
</style>
