<template>
  <v-container>
    <v-data-iterator
      :items="formattedAlerts"
      :search="search"
      :items-per-page="alertsPerPage"
      v-model:page="page"
    >
      <!-- Search -->
      <template v-slot:header>
        <v-text-field
          id="search"
          v-model="search"
          clearable
          hide-details
          placeholder="Search alerts..."
          :prepend-inner-icon="mdiMagnify"
          variant="solo"
        ></v-text-field>
      </template>
      <!-- No alerts -->
      <template v-slot:no-data>
        <v-list class="mt-4" elevation="1">
          <v-list-item>
            <v-list-item-title class="text-grey text-center py-4"> No alerts </v-list-item-title>
          </v-list-item>
        </v-list>
      </template>
      <!-- Alerts list -->
      <template v-slot:default>
        <v-list class="mt-4" elevation="1">
          <v-list-item v-for="(item, index) in paginatedAlerts" :key="item.id" class="alert-item">
            <template v-slot:prepend>
              <v-chip size="small" class="me-3">{{ getAbsoluteIndex(index) + 1 }}</v-chip>
            </template>
            <v-list-item-title class="text-wrap">{{ item.message }}</v-list-item-title>
            <template v-slot:append>
              <v-btn
                :icon="mdiDeleteOutline"
                variant="text"
                color="error"
                @click="deleteAlert(item.id)"
              ></v-btn>
            </template>
          </v-list-item>
        </v-list>
      </template>
      <!-- Page navigation -->
      <template v-slot:footer="{ pageCount }">
        <v-footer class="justify-space-between mt-4" v-if="alerts.length > 0" elevation="1">
          <div class="d-flex align-center">
            <span class="text-caption text-grey mr-2">Alerts per page:</span>
            <v-select
              v-model="alertsPerPage"
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
    <!-- Delete all alerts button -->
    <div class="mt-12 d-flex justify-center" v-if="alerts.length > 0">
      <v-btn
        color="error"
        :prepend-icon="mdiDeleteOutline"
        :disabled="alerts.length === 0"
        @click="confirmDeleteAll = true"
        style="height: 48px; width: 100%; max-width: 400px"
        class="text-body-1 font-weight-bold"
      >
        Delete All Alerts
      </v-btn>
    </div>
    <!-- Delete all alerts confirmation -->
    <!-- v8 ignore start -->
    <v-dialog v-model="confirmDeleteAll" max-width="400">
      <v-card title="Delete all alerts?">
        <v-card-text> Are you sure you want to delete all alerts? </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="confirmDeleteAll = false">Cancel</v-btn>
          <v-btn color="error" variant="flat" @click="deleteAllAlerts">Delete All</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
    <!-- v8 ignore stop -->
    <v-overlay :model-value="isLoading" contained class="align-center justify-center" persistent>
      <v-progress-circular indeterminate color="primary" size="64"></v-progress-circular>
    </v-overlay>
  </v-container>
</template>

<script setup>
import { socket } from '@/socket'
import { ref, computed, inject, onMounted, watch } from 'vue'
import { mdiDeleteOutline, mdiMagnify } from '@mdi/js'

const search = ref('')
const page = ref(1)
const alertsPerPage = ref(10)
const confirmDeleteAll = ref(false)
const isLoading = ref(false)
const settings = inject('settings')
const alertsCount = inject('alertsCount')
const updateAlertsCount = inject('updateAlertsCount')
const alerts = ref([])

watch(search, () => {
  page.value = 1
})

const formattedAlerts = computed(() => {
  return alerts.value.map((item) => ({
    id: item.id,
    message: `[Frame: ${item.tsinfo?.frame ?? '-'}, Time: ${item.tsinfo?.time?.toFixed(2) ?? '-'} ps, Step: ${item.tsinfo?.step ?? '-'}] ${item.message}`,
  }))
})

const filteredAlerts = computed(() => {
  if (!search.value) return formattedAlerts.value
  return formattedAlerts.value.filter((item) =>
    item.message.toLowerCase().includes(search.value.toLowerCase()),
  )
})

const paginatedAlerts = computed(() => {
  const start = (page.value - 1) * alertsPerPage.value
  const end = start + alertsPerPage.value
  return filteredAlerts.value.slice(start, end)
})

const getAbsoluteIndex = (localIndex) => {
  return (page.value - 1) * alertsPerPage.value + localIndex
}

const deleteAlert = (id) => {
  alerts.value = alerts.value.filter((alert) => alert.id !== id)
  updateAlertsCount(alertsCount.value - 1)
  socket.emit('delete_alert', id)
}

const deleteAllAlerts = () => {
  alerts.value = []
  confirmDeleteAll.value = false
  updateAlertsCount(0)
  socket.emit('delete_all_alerts')
}

onMounted(async () => {
  isLoading.value = true
  try {
    const response = await socket
      .timeout(settings.value.dashboard_config.ui_request_timeout * 1000)
      .emitWithAck('get_alerts')
    if (response) {
      alerts.value = response
    }
  } finally {
    isLoading.value = false
  }
})
</script>

<style scoped>
.alert-item:not(:last-child) {
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
</style>
