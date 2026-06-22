<template>
  <v-container class="bg-grey-lighten-5">
    <!-- Session Info -->
    <v-card
      class="mb-6"
      elevation="1"
      v-show="settings.dashboard_config?.show_session_info && Object.keys(sessionInfo).length > 0"
    >
      <v-card-item title="Session Info">
        <v-card-text class="pt-2 pb-2 cursor-default">
          <v-card-text class="d-flex flex-wrap ga-2 pa-0">
            <v-chip v-for="item in sessionInfoItems" :key="item.label" variant="outlined" label>
              <v-icon start :color="sessionInfo[item.key] ? 'success' : 'error'">
                {{ sessionInfo[item.key] ? mdiCheck : mdiClose }}
              </v-icon>
              {{ item.label }}
            </v-chip>
          </v-card-text>
        </v-card-text>
      </v-card-item>
    </v-card>

    <!-- Energies Card -->
    <v-card
      id="energies"
      class="mb-6"
      elevation="1"
      v-show="settings.dashboard_config?.show_energies && sessionInfo.energies"
    >
      <v-card-item
        title="Energies"
        subtitle="Live simulation energies"
        class="cursor-pointer"
        @click="isEnergiesExpanded = !isEnergiesExpanded"
      >
        <template v-slot:prepend>
          <v-icon :icon="mdiChartTimelineVariant" color="primary" />
        </template>
        <template v-slot:append>
          <v-btn :icon="isEnergiesExpanded ? mdiChevronUp : mdiChevronDown" variant="text"></v-btn>
        </template>
      </v-card-item>
      <v-expand-transition>
        <div v-show="isEnergiesExpanded">
          <v-divider />
          <v-card-text class="pa-0">
            <v-row no-gutters>
              <!-- Loop through energies -->
              <v-col
                v-for="(energy, index) in energies"
                :key="index"
                cols="6"
                sm="4"
                md="4"
                class="pa-4 border-sm"
              >
                <div class="text-medium-emphasis">{{ energy.label }}</div>
                <v-fade-transition mode="out-in">
                  <div
                    :key="timestepInfo.energies[energy.key]"
                    class="text-body-large font-weight-bold text-primary d-flex align-center"
                  >
                    {{ timestepInfo.energies[energy.key]?.toFixed(2) ?? '-' }}
                    {{ 'units' in energy ? energy.units : 'kJ/mol' }}
                    <v-icon
                      v-if="energy.trend"
                      :color="energy.trend > 0 ? 'success' : 'error'"
                      size="small"
                      class="ms-2"
                    >
                      {{ energy.trend > 0 ? mdiTrendingUp : mdiTrendingDown }}
                    </v-icon>
                  </div>
                </v-fade-transition>
              </v-col>
            </v-row>
          </v-card-text>
        </div>
      </v-expand-transition>
    </v-card>

    <!-- Filter Widgets and Add Widget -->
    <div class="d-flex align-center gap-4 mb-4">
      <div>
        <v-select
          id="grid-preset"
          width="56"
          class="custom-v-select-field-height"
          v-model="gridPresetIcon"
          :items="gridPresetIconItems"
          item-value="icon"
          variant="solo"
          hide-details
          menu-icon=""
          @update:model-value="handleGridPresetChange"
          v-tooltip="{ text: 'Arrange grid', location: 'left' }"
        >
          <template #selection>
            <v-icon :icon="gridPresetIcon" size="large"></v-icon>
          </template>
          <template #item="{ props, item }">
            <div
              v-bind="props"
              class="v-list-item v-list-item--link d-flex justify-center align-center py-2 px-3"
            >
              <v-icon :icon="item.icon"></v-icon>
              <!-- v8 ignore start -->
              <v-tooltip activator="parent">
                {{ item.desc }}
              </v-tooltip>
              <!-- v8 ignore stop -->
            </div>
            <v-divider v-if="item.name != 'col3'"></v-divider>
          </template>
        </v-select>
      </div>
      <!-- Filter Widgets -->
      <v-sheet elevation="1" width="100%" rounded>
        <v-autocomplete
          clearable
          persistent-clear
          chips
          multiple
          closable-chips
          label="Filter Widgets"
          variant="outlined"
          :items="layoutWidgets"
          item-title="name"
          item-value="i"
          v-model="selectedLayoutWidgets"
          hide-details
          style="flex-grow: 1"
          no-data-text="No widgets added"
          @update:model-value="onWidgetsGridFilter"
        >
          <template #item="{ props, item }">
            <v-list-item v-bind="props" :title="item.name">
              <template #prepend></template>
            </v-list-item>
          </template>
        </v-autocomplete>
      </v-sheet>

      <!-- Add Widget -->
      <div class="text-center">
        <v-btn
          id="add-widget-btn"
          color="primary"
          class="flex-shrink-0"
          height="56"
          elevation="1"
          @click="handleAddWidgetClick"
        >
          Add Widget
        </v-btn>

        <!-- Using :model-value and @update:model-value instead of
         v-model to get coverage (see vitest-dev/vitest#9053) -->
        <v-menu
          :model-value="isAddWidgetOpen"
          @update:model-value="setAddWidgetMenuState"
          activator="#add-widget-btn"
          :close-on-content-click="false"
          :transition="false"
        >
          <v-card width="350">
            <!-- Loading spinner -->
            <div v-if="isAddWidgetLoading" class="d-flex justify-center align-center py-4">
              <v-progress-circular indeterminate color="primary"></v-progress-circular>
              <span class="ms-2 text-caption text-grey">Loading Widgets...</span>
            </div>

            <!-- Add widgets - items -->
            <v-autocomplete
              v-else
              :menu="isAddWidgetOpen"
              @update:menu="setAddWidgetMenuState"
              :items="addWidgetItems"
              item-title="name"
              label="Search Widgets..."
              :custom-filter="customAddWidgetFilter"
              return-object
              ref="addWidgetAutoCompleteRef"
              v-focus-input
              hide-details
              variant="solo"
              class="border"
              @update:model-value="onAddWidgetSelected"
              :loading="isAddWidgetLoading"
            >
              <!-- custom template to show both name and description -->
              <template #item="{ props, item }">
                <v-list-item
                  v-bind="props"
                  :title="item.name"
                  :subtitle="item.description"
                  lines="two"
                ></v-list-item>
                <v-divider class="my-0"></v-divider>
              </template>
            </v-autocomplete>
          </v-card>
        </v-menu>
      </div>
    </div>

    <!-- Widgets Grid Layout -->
    <!-- Using :layout and @update:layout instead of v-model:layout
     to get coverage (see vitest-dev/vitest#9053) -->
    <div style="margin: -10px">
      <grid-layout
        :layout="displayedLayoutWidgets"
        @update:layout="updateDisplayedLayoutWidgets"
        :key="widgetsGridKey"
        :row-height="30"
        :is-draggable="gridEditable"
        :is-resizable="gridEditable"
        :responsive="false"
        @selectstart.prevent
      >
        <grid-item
          v-for="item in displayedLayoutWidgets"
          :key="item.i"
          :x="item.x"
          :y="item.y"
          :w="item.w"
          :h="item.h"
          :i="item.i"
          @moved="layoutUpdate"
          @resized="layoutUpdate"
        >
          <v-card
            class="mb-6 h-100 d-flex flex-column"
            elevation="2"
            @dblclick="widgetFunction(item, { title: 'Edit' })"
          >
            <v-card-item :title="item.name" :subtitle="item.description">
              <template v-slot:append>
                <v-menu>
                  <template v-slot:activator="{ props }">
                    <v-btn
                      :icon="mdiDotsVertical"
                      variant="text"
                      size="small"
                      color="medium-emphasis"
                      v-bind="props"
                    ></v-btn>
                  </template>
                  <!-- Widget actions -->
                  <v-list>
                    <v-list-item
                      v-for="(action, i) in widgetMenuItems"
                      :key="i"
                      @click="widgetFunction(item, action)"
                    >
                      <template v-slot:prepend>
                        <v-icon
                          :icon="action.icon"
                          :color="action.icon == mdiDelete ? 'error' : 'undefined'"
                        ></v-icon>
                      </template>
                      <v-list-item-title>{{ action.title }}</v-list-item-title>
                    </v-list-item>
                  </v-list>
                </v-menu>
              </template>
            </v-card-item>
            <v-divider />
            <!-- Widget output -->
            <!-- Image -->
            <v-img
              class="flex-grow-1"
              contain
              height="0"
              v-if="widgetOutputs[item.i]?.['image/png']"
              :src="`data:image/png;base64,${widgetOutputs[item.i]['image/png']}`"
            ></v-img>
          </v-card>
        </grid-item>
      </grid-layout>
    </div>

    <!-- TODO: rest of the dashboard -->
  </v-container>
</template>

<script setup>
import { socket } from '@/socket'
import { computed, ref, inject, nextTick, onActivated, onDeactivated, h } from 'vue'
import { GridLayout, GridItem } from 'grid-layout-plus'
import { useRouter } from 'vue-router'
import {
  mdiChartTimelineVariant,
  mdiChevronDown,
  mdiChevronUp,
  mdiContentDuplicate,
  mdiDelete,
  mdiDotsVertical,
  mdiPencil,
  mdiTrendingDown,
  mdiTrendingUp,
  mdiCheck,
  mdiClose,
} from '@mdi/js'

const gridPresetIcons = {
  editable: () =>
    h('svg', { viewBox: '0 0 24 24' }, [
      h('path', {
        d: 'M21 13.1C20.9 13.1 20.7 13.2 20.6 13.3L19.6 14.3L21.7 16.4L22.7 15.4C22.9 15.2 22.9 14.8 22.7 14.6L21.4 13.3C21.3 13.2 21.2 13.1 21 13.1M19.1 14.9L13 20.9V23H15.1L21.2 16.9L19.1 14.9M21 3H13V9H21V3M19 7H15V5H19V7M13 18.06V11H21V11.1C20.24 11.1 19.57 11.5 19.19 11.89L18.07 13H15V16.07L13 18.06M11 3H3V13H11V3M9 11H5V5H9V11M11 20.06V15H3V21H11V20.06M9 19H5V17H9V19Z',
        stroke: '#000000',
        'stroke-width': 0.1,
      }),
    ]),
  col1: () =>
    h('svg', { viewBox: '0 0 24 24' }, [
      h('path', {
        d: 'M6 5C6 4.44772 6.44772 4 7 4H17C17.5523 4 18 4.44772 18 5V19C18 19.5523 17.5523 20 17 20H7C6.44772 20 6 19.5523 6 19V5Z',
        fill: 'none',
        stroke: '#000000',
        'stroke-width': 2,
      }),
    ]),
  col2: () =>
    h('svg', { viewBox: '0 0 24 24' }, [
      h('path', {
        d: 'M8,2 C9.65685425,2 11,3.34314575 11,5 L11,19 C11,20.6568542 9.65685425,22 8,22 L5,22 C3.34314575,22 2,20.6568542 2,19 L2,5 C2,3.34314575 3.34314575,2 5,2 L8,2 Z M19,2 C20.6568542,2 22,3.34314575 22,5 L22,19 C22,20.6568542 20.6568542,22 19,22 L16,22 C14.3431458,22 13,20.6568542 13,19 L13,5 C13,3.34314575 14.3431458,2 16,2 L19,2 Z M8,4 L5,4 C4.44771525,4 4,4.44771525 4,5 L4,19 C4,19.5522847 4.44771525,20 5,20 L8,20 C8.55228475,20 9,19.5522847 9,19 L9,5 C9,4.44771525 8.55228475,4 8,4 Z M19,4 L16,4 C15.4477153,4 15,4.44771525 15,5 L15,19 C15,19.5522847 15.4477153,20 16,20 L19,20 C19.5522847,20 20,19.5522847 20,19 L20,5 C20,4.44771525 19.5522847,4 19,4 Z',
        fill: '#000000',
      }),
    ]),
  col3: () =>
    h('svg', { viewBox: '0 0 24 24' }, [
      h('path', {
        d: 'M6.23694 3.0004C7.20344 3.0004 7.98694 3.7839 7.98694 4.7504V19.2504C7.98694 20.2169 7.20344 21.0004 6.23694 21.0004H3.73694C2.77044 21.0004 1.98694 20.2169 1.98694 19.2504V4.7504C1.98694 3.83223 2.69405 3.07921 3.59341 3.0062L3.73694 3.0004H6.23694ZM20.263 3.0004C21.2295 3.0004 22.013 3.7839 22.013 4.7504V19.2504C22.013 20.2169 21.2295 21.0004 20.263 21.0004H17.763C16.7965 21.0004 16.013 20.2169 16.013 19.2504V4.7504C16.013 3.7839 16.7965 3.0004 17.763 3.0004H20.263ZM13.2369 2.99957C14.2034 2.99957 14.9869 3.78307 14.9869 4.74957V19.2496C14.9869 20.2161 14.2034 20.9996 13.2369 20.9996H10.7369C9.77044 20.9996 8.98694 20.2161 8.98694 19.2496V4.74957C8.98694 3.78307 9.77044 2.99957 10.7369 2.99957H13.2369ZM6.23694 4.5004H3.73694L3.67962 4.50701C3.56917 4.53292 3.48694 4.63206 3.48694 4.7504V19.2504C3.48694 19.3885 3.59887 19.5004 3.73694 19.5004H6.23694C6.37501 19.5004 6.48694 19.3885 6.48694 19.2504V4.7504C6.48694 4.61233 6.37501 4.5004 6.23694 4.5004ZM20.263 4.5004H17.763C17.6249 4.5004 17.513 4.61233 17.513 4.7504V19.2504C17.513 19.3885 17.6249 19.5004 17.763 19.5004H20.263C20.4011 19.5004 20.513 19.3885 20.513 19.2504V4.7504C20.513 4.61233 20.4011 4.5004 20.263 4.5004ZM13.2369 4.49957H10.7369C10.5989 4.49957 10.4869 4.6115 10.4869 4.74957V19.2496C10.4869 19.3876 10.5989 19.4996 10.7369 19.4996H13.2369C13.375 19.4996 13.4869 19.3876 13.4869 19.2496V4.74957C13.4869 4.6115 13.375 4.49957 13.2369 4.49957Z',
        fill: '#000000',
      }),
    ]),
}
const gridPresetIcon = ref(gridPresetIcons.editable)
const gridPresetIconItems = ref([
  { name: 'editable', icon: gridPresetIcons.editable, desc: 'Default' },
  { name: 'col1', icon: gridPresetIcons.col1, desc: 'One column' },
  { name: 'col2', icon: gridPresetIcons.col2, desc: 'Two columns' },
  { name: 'col3', icon: gridPresetIcons.col3, desc: 'Three columns' },
])
const gridEditable = ref(true)

const router = useRouter()

const sessionInfoItems = [
  { label: 'Time', key: 'time' },
  { label: 'Energies', key: 'energies' },
  { label: 'Box', key: 'box' },
  { label: 'Coordinates', key: 'positions' },
  { label: 'Wrapped', key: 'wrapped_coords' },
  { label: 'Velocities', key: 'velocities' },
  { label: 'Forces', key: 'forces' },
]

const energies = [
  { label: 'Absolute temperature', key: 'temperature', units: 'K', trend: 1 },
  { label: 'Total energy', key: 'total_energy', trend: -1 },
  { label: 'Potential energy', key: 'potential_energy', trend: 1 },
  { label: 'Van der Waals energy', key: 'van_der_walls_energy', trend: 1 },
  { label: 'Coulomb interaction energy', key: 'coulomb_energy', trend: 1 },
  { label: 'Bonds energy', key: 'bonds_energy', trend: -1 },
  { label: 'Angles energy', key: 'angles_energy', trend: 0 },
  { label: 'Dihedrals energy', key: 'dihedrals_energy', trend: 1 },
  { label: 'Improper dihedrals energy', key: 'improper_dihedrals_energy', trend: 1 },
]

const widgetMenuItems = [
  { title: 'Edit', icon: mdiPencil },
  { title: 'Duplicate', icon: mdiContentDuplicate },
  { title: 'Delete', icon: mdiDelete },
]

const isEnergiesExpanded = ref(true)
const timestepInfo = inject('timestepInfo')
const settings = inject('settings')
const sessionInfo = ref({})
const layoutWidgets = ref([])
const selectedLayoutWidgets = ref([])
const isAddWidgetOpen = ref(false)
const isAddWidgetLoading = ref(true)
const addWidgetItems = ref([])
const addWidgetAutoCompleteRef = ref(null)
const widgetsGridKey = ref(0)
const widgetOutputs = ref({})
var displayedLayoutWidgets = ref([...layoutWidgets.value])

const displayedLayoutWidgetsByPosition = computed(() => {
  return [...displayedLayoutWidgets.value].sort((a, b) => {
    if (a.y !== b.y) {
      return a.y - b.y
    }
    return a.x - b.x
  })
})

const handleGridPresetChange = (newPreset) => {
  let x = () => 0
  let w = 12
  let h = 14
  if (newPreset === gridPresetIcons.editable) {
    if (selectedLayoutWidgets.value.length == 0) {
      gridEditable.value = true
      displayedLayoutWidgets = ref([...layoutWidgets.value])
      return
    }
  } else if (newPreset === gridPresetIcons.col2) {
    x = (index) => (index % 2) * 6
    w = 6
    h = 11
  } else if (newPreset === gridPresetIcons.col3) {
    x = (index) => (index % 3) * 4
    w = 4
    h = 9
  }
  gridEditable.value = false
  displayedLayoutWidgets.value = displayedLayoutWidgetsByPosition.value.map((item, index) => ({
    ...item,
    x: x(index),
    y: 0,
    w: w,
    h: h,
  }))
  widgetsGridKey.value++
}

function setAddWidgetMenuState(value) {
  isAddWidgetOpen.value = value
}

function updateDisplayedLayoutWidgets(value) {
  displayedLayoutWidgets = value
}

const onAddWidgetSelected = async (obj) => {
  // Add widget on the server side
  const response = await socket
    .timeout(settings.value.dashboard_config.ui_request_timeout)
    .emitWithAck('widgets:add_widget', 0, obj.name, obj.description)
  router.push({
    path: '/widget',
    query: { uuid: response.uuid },
  })
}

const onWidgetsGridFilter = () => {
  // Filter grid elements based on user selections
  if (selectedLayoutWidgets.value.length == 0) {
    displayedLayoutWidgets = ref([...layoutWidgets.value])
  } else {
    displayedLayoutWidgets.value = layoutWidgets.value
      .filter((item) => selectedLayoutWidgets.value.includes(item.i))
      .map((item) => ({ ...item, x: 0, y: 0, w: 12, h: 14 }))
  }
  handleGridPresetChange(gridPresetIcon.value)
  widgetsGridKey.value++
}

const customAddWidgetFilter = (value, query, item) => {
  // Filter widgets list based on name or description
  if (query) {
    const searchText = query.toLowerCase()
    return (
      (item.raw.name || '').toLowerCase().includes(searchText) ||
      (item.raw.description || '').toLowerCase().includes(searchText)
    )
  }
}

const vFocusInput = {
  // Custom focus input needed for autocomplete elements
  mounted: (el) => {
    el.querySelector('input').focus()
  },
}

async function handleAddWidgetClick(isOpen) {
  if (!isOpen) return
  try {
    // Get list of available widgets
    const response = await socket
      .timeout(settings.value.dashboard_config.ui_request_timeout)
      .emitWithAck('widgets:get_available_widgets')
    addWidgetItems.value = response['widgets']
  } catch (error) {
    // v8 ignore next
    console.log(error)
  } finally {
    isAddWidgetLoading.value = false
    // Focus on the 'Search Widgets' autocomplete item
    await nextTick()
    // v8 ignore next
    if (addWidgetAutoCompleteRef.value) {
      setTimeout(() => {
        const nativeInput = addWidgetAutoCompleteRef.value.$el.querySelector('input')
        if (nativeInput) {
          nativeInput.focus()
        }
      }, 50)
    }
  }
}

async function widgetFunction(item, action) {
  // Handle widget actions
  if (action['title'] == 'Delete') {
    socket.emit('widgets:remove_widget', item.i)
  } else if (action['title'] == 'Edit') {
    router.push({
      path: '/widget',
      query: { uuid: item.i },
    })
  } else {
    // (action['title'] == 'Duplicate')
    const response = await socket
      .timeout(settings.value.dashboard_config.ui_request_timeout)
      .emitWithAck('widgets:duplicate_widget', 0, item.i, item.name, item.description)
    router.push({
      path: '/widget',
      query: { uuid: response.uuid },
    })
  }
}

function layoutUpdate() {
  // Update layout on the server side
  if (selectedLayoutWidgets.value.length == 0) {
    socket.emit('widgets:update_layout', displayedLayoutWidgets.value)
  }
}

onActivated(() => {
  socket.emit('dashboard:activated')
  socket.on('sessionInfo', (data) => {
    sessionInfo.value = data
  })
  socket.on('widgets:layout', async (data) => {
    // Update layoutWidgets only if it changed
    if (JSON.stringify(data) !== JSON.stringify(layoutWidgets.value)) {
      layoutWidgets.value = data
      // v8 ignore next
      if (selectedLayoutWidgets.value.length == 0) {
        displayedLayoutWidgets = ref([...layoutWidgets.value])
        handleGridPresetChange(gridPresetIcon.value)
        widgetsGridKey.value++
      }
    }
  })
  socket.on('widgets:output', (data) => {
    // Update the widget outputs ref
    widgetOutputs.value[data['uuid']] = data['data']
  })
})

onDeactivated(() => {
  socket.off('sessionInfo')
  socket.off('widgets:layout')
  socket.off('widgets:output')
})
</script>

<style scoped>
/* These are required to force v-select height to 56px */
.custom-v-select-field-height :deep(.v-field) {
  --v-input-control-height: 56px !important;
  min-height: 56px !important;
  height: 56px !important;
}

.custom-v-select-field-height :deep(.v-field__input) {
  min-height: 56px !important;
  height: 56px !important;
  padding-top: 0px !important;
  padding-bottom: 0px !important;
  align-items: center;
}
</style>
