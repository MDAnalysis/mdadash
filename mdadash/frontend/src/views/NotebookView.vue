<template>
  <v-container>
    <!-- Notebook actions -->
    <v-row class="justify-end d-flex ga-0">
      <!-- Keyboard shortcuts -->
      <v-menu
        id="kbShortcuts"
        v-model="kbShortcutsOpen"
        :close-on-content-click="false"
        location="bottom end"
      >
        <template #activator="{ props }">
          <v-btn
            :icon="mdiKeyboardOutline"
            v-bind="props"
            variant="text"
            v-tooltip="{
              text: 'Keyboard shortcuts',
              location: 'bottom',
              disabled: kbShortcutsOpen,
            }"
          />
        </template>
        <v-card class="pa-4 border" elevation="3">
          <v-card-title class="d-flex align-center px-0 pt-0 font-weight-bold">
            Keyboard shortcuts
          </v-card-title>
          <v-divider class="mb-3"></v-divider>
          <v-card-text class="pa-0">
            <ul class="pl-4">
              <li class="mb-2"><strong>Ctrl / Cmd + Enter</strong>: Run cell</li>
              <li class="mb-2">
                <strong>Shift + Enter</strong>: Run cell and advance to next cell
              </li>
            </ul>
          </v-card-text>
        </v-card>
      </v-menu>
      <!-- v8 ignore start -->
      <!-- Import -->
      <input
        type="file"
        ref="fileInput"
        accept=".ipynb"
        style="display: none"
        @change="handleFileImport($event, importAction)"
      />
      <v-menu id="import" v-model="importOpen" :close-on-content-click="false">
        <template #activator="{ props }">
          <v-btn
            :icon="mdiImport"
            v-bind="props"
            variant="text"
            v-tooltip="{
              text: 'Import',
              location: 'bottom',
              disabled: importOpen,
            }"
          />
        </template>
        <v-list>
          <v-list-item
            v-for="(option, index) in importOptions"
            :key="index"
            @click="onImport(option.action)"
          >
            <v-list-item-title>{{ option.title }}</v-list-item-title>
          </v-list-item>
        </v-list>
      </v-menu>
      <!-- Export -->
      <v-btn :icon="mdiExport" variant="text" @click="onExport" v-tooltip:bottom="'Export'"></v-btn>
      <!-- v8 ignore stop -->
      <!-- Run on Launch -->
      <v-tooltip
        :text="notebook.run_on_launch ? 'Disable run on launch' : 'Enable run on launch'"
        location="bottom"
      >
        <template v-slot:activator="{ props }">
          <v-btn
            v-bind="props"
            :icon="mdiRun"
            variant="text"
            :color="notebook.run_on_launch ? 'primary' : 'grey'"
            @click="onRunOnLaunchToggle"
          />
        </template>
      </v-tooltip>
      <!-- Delete -->
      <v-btn
        :icon="mdiDeleteOutline"
        variant="text"
        color="error"
        @click="onDeleteNotebook"
        v-tooltip:bottom="'Delete Notebook'"
      ></v-btn>
    </v-row>
    <!-- Notebook name -->
    <v-text-field
      id="name"
      class="mb-4 mt-2"
      label="Name"
      variant="outlined"
      hint="Notebook name"
      persistent-hint
      v-model="notebook.name"
      control-variant="default"
      @change="onNameDescChange"
    ></v-text-field>
    <!-- Notebook description -->
    <v-text-field
      id="description"
      class="mb-4 mt-2"
      label="Description"
      variant="outlined"
      hint="Notebook description"
      persistent-hint
      v-model="notebook.description"
      control-variant="default"
      @change="onNameDescChange"
    ></v-text-field>
    <!-- Notebook cells -->
    <!-- v8 ignore start -->
    <draggable
      v-model="notebook.cells"
      item-key="id"
      handle=".drag-handle"
      ghost-class="ghost-cell"
      :force-fallback="true"
      drag-class="cell-dragging"
      @end="onCellDrag"
    >
      <template #item="{ element: cell, index }">
        <NotebookCell
          :key="cell.id"
          v-model="cell.code"
          v-model:type="cell.type"
          :id="cell.id"
          :label="`[${index}]`"
          :show-drag="true"
          :show-type="true"
          :show-move="true"
          :show-delete="true"
          :show-add-cell="true"
          @move-up="onCellMove(index, -1)"
          @move-down="onCellMove(index, 1)"
          @delete-cell="onCellDelete(index)"
          @add-cell="onCellAdd(index)"
          @change="onCellChange(cell.id, index)"
          @focus-next="focusNext(index)"
        />
      </template>
    </draggable>
    <!-- Delete notebook confirmation -->
    <v-dialog v-model="confirmDelete" max-width="400">
      <v-card title="Delete Notebook?">
        <template v-slot:prepend>
          <v-icon :icon="mdiAlert" color="warning"></v-icon>
        </template>
        <v-card-text> Are you sure you want to delete this Notebook? </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="confirmDelete = false">Cancel</v-btn>
          <v-btn color="error" variant="flat" @click="onDeleteNotebook">Delete</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
    <!-- v8 ignore stop -->
    <!-- Loading overlay -->
    <v-overlay :model-value="isLoading" contained class="align-center justify-center" persistent>
      <v-progress-circular indeterminate color="primary" size="64"></v-progress-circular>
    </v-overlay>
  </v-container>
</template>

<script setup>
import { socket } from '@/socket'
import { inject, ref, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import draggable from 'vuedraggable'
import NotebookCell from '@/components/NotebookCell.vue'
import {
  mdiAlert,
  mdiDeleteOutline,
  mdiExport,
  mdiImport,
  mdiKeyboardOutline,
  mdiRun,
} from '@mdi/js'

const route = useRoute()
const router = useRouter()
const settings = inject('settings')
const isLoading = ref(false)
const uuid = route.query.uuid
const notebook = ref({})
const confirmDelete = ref(false)
const kbShortcutsOpen = ref(false)
const fileInput = ref(null)
const importOpen = ref(false)
const importAction = ref('null')
const importOptions = ref([
  { title: 'Append cells', action: 'append' },
  { title: 'Overwrite cells', action: 'overwrite' },
])

function onNameDescChange() {
  socket.emit('notebook:name_desc_change', uuid, notebook.value.name, notebook.value.description)
}

function updateCells() {
  socket.emit('notebook:update_cells', uuid, notebook.value.cells)
}

const onCellChange = (id, index) => {
  const cell = notebook.value.cells[index]
  socket.emit('notebook:cell_change', uuid, id, cell.code, cell.type)
}

const onCellDelete = (index) => {
  if (notebook.value.cells.length <= 1) {
    updateCells()
    return
  }
  notebook.value.cells.splice(index, 1)
  updateCells()
}

const onCellAdd = async (index) => {
  const id = crypto.randomUUID()
  const newCell = {
    id,
    code: '',
    type: 'python',
  }
  notebook.value.cells.splice(index + 1, 0, newCell)
  updateCells()
  focusCell(id)
}

const onCellMove = (index, direction) => {
  const newIndex = index + direction
  if (newIndex < 0 || newIndex >= notebook.value.cells.length) {
    return
  }
  const [currentCell] = notebook.value.cells.splice(index, 1)
  notebook.value.cells.splice(newIndex, 0, currentCell)
  updateCells()
}

const onCellDrag = () => {
  updateCells()
}

const focusCell = async (id) => {
  await nextTick()
  const element = document.getElementById(id)
  element?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  const editorArea = element?.querySelector('.cm-content')
  editorArea?.focus()
}

const focusNext = (index) => {
  if (index < notebook.value.cells.length - 1) {
    focusCell(notebook.value.cells[index + 1].id)
  } else {
    onCellAdd(index)
  }
}

const onRunOnLaunchToggle = async () => {
  notebook.value.run_on_launch = !notebook.value.run_on_launch
  socket.emit('notebook:run_on_launch', uuid, notebook.value.run_on_launch)
}

const handleKeydown = (event) => {
  if (event.key === 'Enter') {
    onDeleteNotebook()
  }
}

watch(confirmDelete, (newVal) => {
  if (newVal) {
    document.addEventListener('keydown', handleKeydown)
  } else {
    document.removeEventListener('keydown', handleKeydown)
  }
})

const onDeleteNotebook = async () => {
  confirmDelete.value = !confirmDelete.value
  if (!confirmDelete.value) {
    try {
      await socket
        .timeout(settings.value.dashboard_config.ui_request_timeout * 1000)
        .emitWithAck('notebooks:remove_notebook', uuid)
      router.push({ path: '/notebooks' })
    } catch (error) {
      // v8 ignore next
      console.log(error)
    }
  }
}

// v8 ignore next
const onImport = async (action) => {
  importOpen.value = false
  importAction.value = action
  if (fileInput.value) {
    fileInput.value.click()
  }
}

// v8 ignore next
const handleFileImport = async (event, action) => {
  const target = event.target
  const file = target.files[0]
  if (!file) {
    target.value = ''
    return
  }
  isLoading.value = true
  const reader = new FileReader()
  reader.onload = async (e) => {
    const fileContent = e.target.result
    try {
      await socket
        .timeout(settings.value.dashboard_config.ui_request_timeout * 1000)
        .emitWithAck('notebook:import_notebook', uuid, fileContent, action)
      loadNotebook(uuid)
    } catch (error) {
      // v8 ignore next
      console.log(error)
    } finally {
      target.value = ''
      isLoading.value = false
    }
  }
  reader.onerror = () => {
    target.value = ''
    isLoading.value = false
  }
  reader.readAsText(file)
}

// v8 ignore next
const onExport = async () => {
  try {
    const content = await socket
      .timeout(settings.value.dashboard_config.ui_request_timeout * 1000)
      .emitWithAck('notebook:export_notebook', uuid)
    const blob = new Blob([content], { type: 'application/x-ipynb+json' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', notebook.value.name + '.ipynb')
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  } catch (error) {
    // v8 ignore next
    console.log(error)
  }
}

const loadNotebook = async (uuid) => {
  isLoading.value = true
  try {
    const response = await socket
      .timeout(settings.value.dashboard_config.ui_request_timeout * 1000)
      .emitWithAck('notebooks:get_notebook', uuid)
    if (response) {
      notebook.value = {
        ...response,
        cells: response.cells.map((cell) => ({
          ...cell,
          type: cell.type ?? 'python',
        })),
      }
    } else {
      router.push({ path: '/notebooks' })
    }
  } catch (error) {
    // v8 ignore next
    console.log(error)
  } finally {
    isLoading.value = false
  }
}

onMounted(async () => {
  loadNotebook(uuid)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.ghost-cell {
  opacity: 0.4;
  border: 2px dashed #666;
}
</style>

<style>
/* hide tooltips when dragging cells */
body:has(.cell-dragging) .v-tooltip {
  display: none !important;
}
</style>
