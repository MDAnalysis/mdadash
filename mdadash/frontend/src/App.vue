<template>
  <v-app>
    <v-app-bar color="primary" elevation="1" scroll-behavior="hide">
      <v-btn :icon="mdiViewDashboard" @click="$router.push('/')"></v-btn>
      <v-app-bar-title>{{ appBarTitle }}</v-app-bar-title>

      <!-- app bar icons -->
      <template v-slot:append>
        <div class="d-flex align-center">
          <!-- Pause / Resume icons -->
          <div v-if="runningState.connected" class="d-flex align-center">
            <!-- Show Pause icon if running -->
            <v-btn
              :disabled="runningState.pending"
              v-if="runningState.running"
              icon
              @click="handlePause"
            >
              <v-icon :icon="mdiPause" size="large"></v-icon>
              <v-tooltip activator="parent" location="bottom">Pause</v-tooltip>
            </v-btn>
            <!-- Show Resume icon if paused -->
            <v-btn :disabled="runningState.pending" v-else icon @click="handleResume">
              <v-icon :icon="mdiPlay" size="large"></v-icon>
              <v-tooltip activator="parent" location="bottom">Resume</v-tooltip>
            </v-btn>
          </div>

          <!-- Connect / Disconnect icons -->
          <v-btn :disabled="runningState.pending" icon @click="handleConnectDisconnect">
            <v-icon
              :icon="runningState.connected ? mdiLanDisconnect : mdiLanConnect"
              size="large"
            ></v-icon>
            <v-tooltip activator="parent" location="bottom">
              {{ runningState.connected ? 'Disconnect' : 'Connect' }}
            </v-tooltip>
          </v-btn>

          <!-- Disconnect Confirmation Dialog -->
          <!-- v8 ignore start -->
          <v-dialog v-model="showConfirm" max-width="400">
            <v-card :prepend-icon="mdiAlert" title="Confirm">
              <v-card-text>Are you sure you want to disconnect from the simulation?</v-card-text>
              <v-card-actions>
                <v-spacer></v-spacer>
                <!-- Cancel Button -->
                <v-btn variant="text" @click="showConfirm = false">Cancel</v-btn>
                <!-- Confirm Button -->
                <v-btn color="error" variant="elevated" @click="confirmDisconnect">
                  Disconnect
                </v-btn>
              </v-card-actions>
            </v-card>
          </v-dialog>
          <!-- v8 ignore stop -->
          <!-- Alerts icon -->
          <v-spacer></v-spacer>
          <v-menu offset-y min-width="300">
            <template v-slot:activator="{ props }">
              <v-btn icon v-bind="props">
                <v-badge
                  color="error"
                  width="24"
                  height="24"
                  :content="alertsUnreadCount"
                  :model-value="alertsUnreadCount > 0"
                >
                  <v-icon :icon="mdiBellOutline" size="large"></v-icon>
                </v-badge>
              </v-btn>
            </template>
            <v-list lines="two">
              <v-list-subheader>Recent Alerts</v-list-subheader>
              <!-- v8 ignore start -->
              <v-list-item
                v-for="alert in recentAlerts"
                :key="alert.id"
                :title="alert.title"
                :subtitle="alert.time"
              >
                <template v-slot:append>
                  <v-btn
                    :icon="mdiCheckCircleOutline"
                    variant="text"
                    color="success"
                    @click.stop="removeAlert(alert.id)"
                  ></v-btn>
                </template>
              </v-list-item>
              <v-divider v-if="recentAlerts.length > 0"></v-divider>
              <!-- v8 ignore stop -->
              <v-list-item v-if="recentAlerts.length === 0" title="No new alerts"></v-list-item>
              <v-divider></v-divider>
              <!-- view all alerts -->
              <v-list-item
                title="View All Alerts"
                text-color="primary"
                class="text-center"
                to="/alerts"
              ></v-list-item>
            </v-list>
          </v-menu>
          <v-divider vertical inset class="mx-2"></v-divider>

          <!-- App bar overflow items -->
          <v-menu>
            <template v-slot:activator="{ props }">
              <v-btn :icon="mdiDotsVertical" size="large" v-bind="props"></v-btn>
            </template>
            <v-list>
              <v-list-item v-for="(item, i) in appBarMenuItems" :key="i" :to="item.path">
                <template v-slot:prepend>
                  <v-icon :icon="item.icon"></v-icon>
                </template>
                <v-list-item-title>{{ item.name }}</v-list-item-title>
              </v-list-item>
            </v-list>
          </v-menu>
        </div>
      </template>
    </v-app-bar>

    <!--Sticky bar-->
    <v-app-bar :color="stickyBarColor" flat order="1" elevation="1">
      <v-toolbar-title class="text-center ml-0">
        <div class="d-flex align-center justify-center">
          <div class="d-flex flex-column align-center">
            <span class="text-grey-darken-1">Frame:</span>
            <span class="font-weight-bold">{{ timestepInfo.frame ?? '-' }}</span>
          </div>

          <v-divider vertical inset class="mx-4" thickness="2"></v-divider>

          <div class="d-flex flex-column align-center">
            <span class="text-grey-darken-1">Time:</span>
            <span class="font-weight-bold"> {{ timestepInfo.time?.toFixed(2) ?? '-' }} ps </span>
          </div>

          <v-divider vertical inset class="mx-4" thickness="2"></v-divider>

          <div class="d-flex flex-column align-center">
            <span class="text-grey-darken-1">Step:</span>
            <span class="font-weight-bold">{{ timestepInfo.step ?? '-' }}</span>
          </div>

          <v-divider vertical inset class="mx-4" thickness="2"></v-divider>

          <div class="d-flex flex-column align-center">
            <span class="text-grey-darken-1">Done:</span>
            <span class="font-weight-bold"> {{ timestepInfo.done?.toFixed(2) ?? '-' }} % </span>
          </div>
        </div>
      </v-toolbar-title>
    </v-app-bar>

    <!-- Main content -->
    <v-main class="bg-grey-lighten-5">
      <router-view v-slot="{ Component }">
        <keep-alive :exclude="['WidgetView']">
          <component :is="Component" />
        </keep-alive>
      </router-view>
    </v-main>
  </v-app>
</template>

<script setup>
import { socket } from '@/socket'
import { useRoute } from 'vue-router'
import { ref, computed, onMounted, onBeforeUnmount, provide } from 'vue'
import {
  mdiAlert,
  mdiBellOutline,
  mdiCheckCircleOutline,
  mdiCog,
  mdiDotsVertical,
  mdiLanConnect,
  mdiLanDisconnect,
  mdiPause,
  mdiPlay,
  mdiViewDashboard,
  mdiViewDashboardOutline,
} from '@mdi/js'

const route = useRoute()
const appBarTitle = computed(() => route.meta.title)
const appBarMenuItems = [
  { name: 'Dashboard', icon: mdiViewDashboardOutline, path: '/' },
  { name: 'Settings', icon: mdiCog, path: '/settings' },
]
const runningState = ref({
  pending: false,
  connected: false,
  running: false,
})
const showConfirm = ref(false)
const recentAlerts = ref([])
const alertsUnreadCount = 0

function handlePause() {
  runningState.value.pending = true
  socket.emit('pause_simulations')
}

function handleResume() {
  runningState.value.pending = true
  socket.emit('resume_simulations')
}

function handleConnectDisconnect() {
  if (runningState.value.connected) {
    showConfirm.value = true
  } else {
    runningState.value.pending = true
    socket.emit('connect_to_simulations')
  }
}

function confirmDisconnect() {
  showConfirm.value = false
  runningState.value.pending = true
  socket.emit('disconnect_from_simulations')
}

// v8 ignore next
const removeAlert = (id) => {
  recentAlerts.value = recentAlerts.value.filter((alert) => alert.id !== id)
}

const stickyBarColor = computed(() => {
  if (!runningState.value.connected) return 'red-lighten-5'
  if (!runningState.value.running) return 'amber-lighten-5'
  return 'green-lighten-5'
})

const timestepInfo = ref({
  energies: {},
})

const settings = ref({
  dashboard_config: {
    ui_request_timeout: 5000,
  },
  universe_configs: [{}],
})
const origSettings = ref(null)

onMounted(() => {
  socket.on('runningState', (data) => {
    runningState.value = data
    if (data.message) {
      // Temporarily show error in alert
      alert('ERROR: ' + data.message)
    }
  })
  socket.on('timestepInfo', (data) => {
    timestepInfo.value = data
  })
  socket.on('settings', (data) => {
    settings.value = JSON.parse(JSON.stringify(data))
    origSettings.value = JSON.parse(JSON.stringify(data))
  })
})

onBeforeUnmount(() => {
  socket.off('runningState')
  socket.off('timestepInfo')
  socket.off('settings')
})

provide('runningState', runningState)
provide('timestepInfo', timestepInfo)
provide('settings', settings)
provide('origSettings', origSettings)
</script>

<style scoped></style>
