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
            class="flex-grow-1"
          >
          </v-text-field>
          <!-- Buttons -->
          <div class="d-flex align-center">
            <!-- Add Notebook -->
            <v-btn color="primary" height="100%" @click="addNotebook"> Add Notebook </v-btn>
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
import { computed, ref, inject, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  mdiAlert,
  mdiContentDuplicate,
  mdiDeleteOutline,
  mdiDotsVertical,
  mdiMagnify,
  mdiPencil,
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

const notebookMenuItems = [
  { title: 'Edit', icon: mdiPencil },
  { title: 'Duplicate', icon: mdiContentDuplicate },
  { title: 'Delete', icon: mdiDeleteOutline },
]

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
</script>

<style scoped>
.notebook-item:not(:last-child) {
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
</style>
