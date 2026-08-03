<template>
  <v-container>
    <v-data-iterator
      :items="notebooks"
      :search="search"
      :items-per-page="itemsPerPage"
      v-model:page="page"
    >
      <!-- Search -->
      <template v-slot:header>
        <div class="d-flex align-stretch w-100 mb-4">
          <v-text-field
            id="search"
            v-model="search"
            clearable
            hide-details
            placeholder="Search Notebooks..."
            :prepend-inner-icon="mdiMagnify"
            variant="solo"
            class="flex-grow-1 elevation-1"
          >
          </v-text-field>
          <!-- Buttons -->
          <div class="d-flex align-center ga-1">
            <!-- New -->
            <v-btn color="primary" height="100%" @click="addNotebook">
              <v-icon :icon="mdiPlus" class="me-2"></v-icon>
              New
            </v-btn>
            <!-- Clone Widget -->
            <div class="text-center">
              <v-btn
                id="clone-widget-btn"
                color="primary"
                class="flex-shrink-0"
                height="56"
                elevation="1"
                @click="handleCloneWidgetClick"
              >
                <v-icon :icon="mdiContentDuplicate" class="me-2"></v-icon>
                Clone Widget
              </v-btn>
              <v-menu
                :model-value="isCloneWidgetOpen"
                @update:model-value="setCloneWidgetMenuState"
                activator="#clone-widget-btn"
                :close-on-content-click="false"
                :transition="false"
              >
                <v-card width="350">
                  <!-- Loading spinner -->
                  <div v-if="isCloneWidgetLoading" class="d-flex justify-center align-center py-4">
                    <v-progress-circular indeterminate color="primary"></v-progress-circular>
                    <span class="ms-2 text-caption text-grey">Loading Widgets...</span>
                  </div>
                  <!-- Clone widgets - items -->
                  <v-autocomplete
                    v-else
                    :menu="isCloneWidgetOpen"
                    :menu-props="{ maxWidth: '100%' }"
                    :list-props="{ class: 'py-0' }"
                    @update:menu="setCloneWidgetMenuState"
                    :items="cloneWidgetItems"
                    item-title="name"
                    label="Search Widgets..."
                    :custom-filter="customCloneWidgetFilter"
                    return-object
                    ref="cloneWidgetAutoCompleteRef"
                    hide-details
                    variant="solo"
                    class="border"
                    @update:model-value="onCloneWidgetSelected"
                    :loading="isCloneWidgetLoading"
                    clearable
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
        </div>
      </template>
      <!-- No Notebooks -->
      <template v-slot:no-data>
        <v-list class="mt-4" elevation="1">
          <v-list-item>
            <v-list-item-title class="text-grey text-center py-4"> No Notebooks </v-list-item-title>
          </v-list-item>
        </v-list>
      </template>
      <!-- Notebooks list -->
      <template v-slot:default>
        <v-list class="py-0" elevation="1" lines="two">
          <v-list-item
            v-for="(item, index) in paginatedNotebooks"
            :key="item.uuid"
            :title="item.name"
            :subtitle="item.description"
            link
            class="user-select-none notebook-item py-4"
            @click="notebookFunction(item, { title: 'Edit' })"
          >
            <!-- Index -->
            <template v-slot:prepend>
              <span class="mr-4">{{ getAbsoluteIndex(index) + 1 }}.</span>
            </template>
            <!-- Actions -->
            <template v-slot:append>
              <v-icon :icon="mdiRun" :color="item.run_on_launch ? 'primary' : 'grey'"></v-icon>
              <v-menu>
                <template v-slot:activator="{ props }">
                  <v-btn
                    :icon="mdiDotsVertical"
                    variant="text"
                    size="small"
                    color="grey-lighten-1"
                    v-bind="props"
                    @click.stop
                  ></v-btn>
                </template>
                <v-list density="compact" class="py-0">
                  <v-list-item
                    v-for="(action, i) in notebookMenuItems"
                    :key="i"
                    @click="notebookFunction(item, action)"
                  >
                    <template v-slot:prepend>
                      <v-icon
                        :icon="action.icon"
                        :color="action.icon == mdiDeleteOutline ? 'error' : 'undefined'"
                      ></v-icon>
                    </template>
                    <v-list-item-title>{{ action.title }}</v-list-item-title>
                  </v-list-item>
                </v-list>
              </v-menu>
            </template>
          </v-list-item>
        </v-list>
      </template>
      <!-- Page navigation -->
      <template v-slot:footer="{ pageCount }">
        <v-footer class="justify-space-between mt-4" v-if="notebooks.length > 0" elevation="1">
          <div class="d-flex align-center">
            <span class="text-caption text-grey mr-2">Items per page:</span>
            <v-select
              v-model="itemsPerPage"
              :items="[10, 20, 50]"
              density="compact"
              hide-details
              variant="outlined"
            ></v-select>
          </div>
          <!-- v8 ignore start -->
          <v-pagination
            v-model="page"
            :length="pageCount"
            density="comfortable"
            total-visible="5"
          ></v-pagination>
          <!-- v8 ignore stop -->
        </v-footer>
      </template>
    </v-data-iterator>
    <!-- Delete notebook confirmation -->
    <!-- v8 ignore start -->
    <v-dialog v-model="confirmDelete" max-width="400">
      <v-card title="Delete Notebook?">
        <template v-slot:prepend>
          <v-icon :icon="mdiAlert" color="warning"></v-icon>
        </template>
        <v-card-text>
          Are you sure you want to delete Notebook '{{ deleteItem.name }}'?
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="confirmDelete = false">Cancel</v-btn>
          <v-btn
            color="error"
            variant="flat"
            @click="notebookFunction(deleteItem, { title: 'Delete' })"
            >Delete</v-btn
          >
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
import { computed, ref, inject, nextTick, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  mdiAlert,
  mdiContentDuplicate,
  mdiDeleteOutline,
  mdiDotsVertical,
  mdiMagnify,
  mdiPencil,
  mdiPlus,
  mdiRun,
} from '@mdi/js'

const router = useRouter()
const search = ref('')
const page = ref(1)
const itemsPerPage = ref(10)
const isLoading = ref(false)
const settings = inject('settings')
const notebooks = ref([])
const confirmDelete = ref(false)
const deleteItem = ref()

const isCloneWidgetOpen = ref(false)
const isCloneWidgetLoading = ref(true)
const cloneWidgetItems = ref([])
const cloneWidgetAutoCompleteRef = ref(null)

const notebookMenuItems = [
  { title: 'Edit', icon: mdiPencil },
  { title: 'Duplicate', icon: mdiContentDuplicate },
  { title: 'Delete', icon: mdiDeleteOutline },
]

function setCloneWidgetMenuState(value) {
  isCloneWidgetOpen.value = value
}

const onCloneWidgetSelected = async (obj) => {
  const uuid = await socket
    .timeout(settings.value.dashboard_config.ui_request_timeout * 1000)
    .emitWithAck('notebooks:clone_widget', obj.name, obj.description, obj.class_name)
  router.push({
    path: '/notebook',
    query: { uuid: uuid },
  })
}

const customCloneWidgetFilter = (value, query, item) => {
  // Filter widgets list based on name or description
  if (query) {
    const searchText = query.toLowerCase()
    return (
      (item.raw.name || '').toLowerCase().includes(searchText) ||
      (item.raw.description || '').toLowerCase().includes(searchText)
    )
  }
}

async function handleCloneWidgetClick(isOpen) {
  if (!isOpen) return
  try {
    // Get list of clonable widgets
    const widgets = await socket
      .timeout(settings.value.dashboard_config.ui_request_timeout * 1000)
      .emitWithAck('notebooks:get_clonable_widgets')
    cloneWidgetItems.value = widgets
  } catch (error) {
    // v8 ignore next
    console.log(error)
  } finally {
    isCloneWidgetLoading.value = false
    // Focus on the 'Search Widgets' autocomplete item
    await nextTick()
    // v8 ignore next
    if (cloneWidgetAutoCompleteRef.value) {
      cloneWidgetAutoCompleteRef.value.focus()
      setTimeout(() => {
        const nativeInput = cloneWidgetAutoCompleteRef.value?.$el.querySelector('input')
        if (nativeInput) {
          nativeInput.focus()
        }
      }, 50)
    }
  }
}

const filteredNotebooks = computed(() => {
  if (!search.value) return notebooks.value
  return notebooks.value.filter((item) => {
    const searchTerm = search.value.toLowerCase()
    return (
      item.name?.toLowerCase().includes(searchTerm) ||
      item.description?.toLowerCase().includes(searchTerm)
    )
  })
})

const paginatedNotebooks = computed(() => {
  const start = (page.value - 1) * itemsPerPage.value
  const end = start + itemsPerPage.value
  return filteredNotebooks.value.slice(start, end)
})

const getAbsoluteIndex = (localIndex) => {
  return (page.value - 1) * itemsPerPage.value + localIndex
}

const addNotebook = async () => {
  const uuid = await socket
    .timeout(settings.value.dashboard_config.ui_request_timeout * 1000)
    .emitWithAck('notebooks:add_notebook')
  router.push({
    path: '/notebook',
    query: { uuid: uuid },
  })
}

const handleKeydown = (event) => {
  if (event.key === 'Enter') {
    notebookFunction(deleteItem.value, { title: 'Delete' })
  }
}

watch(confirmDelete, (newVal) => {
  if (newVal) {
    document.addEventListener('keydown', handleKeydown)
  } else {
    document.removeEventListener('keydown', handleKeydown)
  }
})

async function notebookFunction(item, action) {
  if (action['title'] == 'Delete') {
    confirmDelete.value = !confirmDelete.value
    if (confirmDelete.value) {
      deleteItem.value = item
    } else {
      notebooks.value = notebooks.value.filter((notebook) => notebook.uuid !== item.uuid)
      socket.emit('notebooks:remove_notebook', item.uuid)
    }
  } else if (action['title'] == 'Edit') {
    router.push({
      path: '/notebook',
      query: { uuid: item.uuid },
    })
  } else {
    // (action['title'] == 'Duplicate')
    const new_uuid = await socket
      .timeout(settings.value.dashboard_config.ui_request_timeout * 1000)
      .emitWithAck('notebooks:duplicate_notebook', item.uuid)
    router.push({
      path: '/notebook',
      query: { uuid: new_uuid },
    })
  }
}

onMounted(async () => {
  isLoading.value = true
  try {
    const response = await socket
      .timeout(settings.value.dashboard_config.ui_request_timeout * 1000)
      .emitWithAck('notebooks:get_notebooks')
    if (response) {
      notebooks.value = response
    }
  } finally {
    isLoading.value = false
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.notebook-item:not(:last-child) {
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
</style>
