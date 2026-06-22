<template>
  <v-container>
    <!-- Dashboard Configuration -->
    <v-card id="dashboard-configuration" class="mb-6" elevation="1">
      <v-form>
        <v-card-item
          title="Dashboard Configuration"
          subtitle="Configuration settings for the dashboard"
          class="cursor-pointer"
          @click="isDCExpanded = !isDCExpanded"
        >
          <template v-slot:prepend>
            <v-icon :icon="mdiViewDashboard" color="primary" />
          </template>
          <template v-slot:append>
            <v-btn :icon="isDCExpanded ? mdiChevronUp : mdiChevronDown" variant="text"></v-btn>
          </template>
        </v-card-item>
        <v-expand-transition>
          <div v-show="isDCExpanded">
            <v-divider />
            <v-card-text class="pa-4">
              <v-switch v-model="settings.dashboard_config.show_session_info" color="primary">
                <template v-slot:label>
                  <div class="d-flex flex-column">
                    <div>Show Session Info</div>
                    <div class="text-caption text-grey">Show session info card in dashboard</div>
                  </div>
                </template>
              </v-switch>

              <v-switch v-model="settings.dashboard_config.show_energies" color="primary">
                <template v-slot:label>
                  <div class="d-flex flex-column">
                    <div>Show Energies</div>
                    <div class="text-caption text-grey">
                      Show energies card (when available) in dashboard
                    </div>
                  </div>
                </template>
              </v-switch>
            </v-card-text>
          </div>
        </v-expand-transition>
      </v-form>
    </v-card>

    <!-- Universe Configuration -->
    <v-card id="universe-configuration" class="mb-6" elevation="1">
      <v-form :disabled="runningState.connected">
        <v-card-item
          title="Universe Configuration"
          subtitle="Configuration settings for the universe"
          class="cursor-pointer"
          @click="isUCExpanded = !isUCExpanded"
        >
          <template v-slot:prepend>
            <v-icon :icon="mdiEarth" color="primary" />
          </template>
          <template v-slot:append>
            <v-btn :icon="isUCExpanded ? mdiChevronUp : mdiChevronDown" variant="text"></v-btn>
          </template>
        </v-card-item>
        <v-expand-transition>
          <div v-show="isUCExpanded">
            <v-divider />
            <v-card-text class="pa-4">
              <v-text-field
                label="Topology"
                variant="outlined"
                v-model="settings.universe_configs[0].topology"
                readonly
                class="text-medium-emphasis mb-4"
                hint="Topology filename (read-only)"
                persistent-hint
              ></v-text-field>

              <v-text-field
                label="Trajectory"
                variant="outlined"
                v-model="settings.universe_configs[0].trajectory"
                readonly
                class="text-medium-emphasis mb-4"
                hint="Trajectory URL (read-only)"
                persistent-hint
              ></v-text-field>
              <v-number-input
                class="mb-4"
                label="socket_bufsize"
                placeholder="System default"
                persistent-placeholder
                variant="outlined"
                v-model="settings.universe_configs[0].socket_bufsize"
                control-variant="default"
                :min="8192"
                :max="262144"
                :step="1024"
                hint="Size of the socket buffer in bytes. Default is to use the system default"
                persistent-hint
              ></v-number-input>

              <v-number-input
                class="mb-4"
                label="buffer_size"
                variant="outlined"
                v-model="settings.universe_configs[0].buffer_size"
                control-variant="hidden"
                hint="IMDFrameBuffer will be filled with as many IMDFrame fit in buffer_size bytes [10MB]"
                persistent-hint
              ></v-number-input>

              <v-number-input
                class="mb-4"
                label="timeout"
                variant="outlined"
                v-model="settings.universe_configs[0].timeout"
                control-variant="default"
                hint="Timeout for the socket in seconds [5]"
                persistent-hint
                :min="0"
                :max="30"
                :step="1"
              ></v-number-input>

              <v-select
                class="mb-4"
                v-model="settings.universe_configs[0].continue_after_disconnect"
                label="continue_after_disconnect"
                :items="[
                  { title: 'True', value: true },
                  { title: 'False', value: false },
                  { title: 'None', value: null },
                ]"
                hint="Continue simulation after disconnect"
                persistent-hint
              ></v-select>

              <v-number-input
                class="mb-4"
                label="Step"
                variant="outlined"
                v-model="settings.universe_configs[0].step"
                :min="1"
                control-variant="default"
                hint="frame(s) during iteration"
                persistent-hint
              ></v-number-input>

              <v-number-input
                class="mb-0"
                label="Total simulation steps"
                variant="outlined"
                v-model="settings.universe_configs[0].total_steps"
                control-variant="hidden"
                hint="Configuring this will enable showing % completion"
                persistent-hint
              ></v-number-input>

              <!-- Key value pairs -->
              <div class="d-flex flex-column">
                <v-label class="mt-4">Additional keyword arguments</v-label>
              </div>
              <v-row
                v-for="(arg, index) in settings.universe_configs[0].kwargs"
                :key="index"
                class="mt-4"
              >
                <v-col>
                  <v-text-field
                    v-model="arg[0]"
                    label="Name"
                    variant="outlined"
                    density="compact"
                    hide-details
                  ></v-text-field>
                </v-col>
                <v-col>
                  <v-text-field
                    v-model="arg[1]"
                    label="Value"
                    variant="outlined"
                    density="compact"
                    hide-details
                  ></v-text-field>
                </v-col>
                <v-col>
                  <v-btn
                    :icon="mdiDelete"
                    color="error"
                    variant="text"
                    @click="removeKwarg(index)"
                    :disabled="runningState.connected"
                  ></v-btn>
                </v-col>
              </v-row>
              <!-- Add kwarg -->
              <v-btn
                :prepend-icon="mdiPlus"
                class="mt-2"
                color="primary"
                variant="tonal"
                :disabled="runningState.connected"
                @click="addKwarg"
              >
                Add kwarg
              </v-btn>
            </v-card-text>
          </div>
        </v-expand-transition>
      </v-form>
    </v-card>
  </v-container>
</template>

<script setup>
import { ref, inject, watch } from 'vue'
import { socket } from '@/socket'
import {
  mdiViewDashboard,
  mdiChevronUp,
  mdiChevronDown,
  mdiDelete,
  mdiEarth,
  mdiPlus,
} from '@mdi/js'

const runningState = inject('runningState')
const settings = inject('settings')
const origSettings = inject('origSettings')

const isDCExpanded = ref(true)
const isUCExpanded = ref(true)

const addKwarg = () => {
  settings.value.universe_configs[0].kwargs.push(['', ''])
}

const removeKwarg = (index) => {
  settings.value.universe_configs[0].kwargs.splice(index, 1)
}

/* v8 ignore start */
let debounceTimeoutId = null
const debounceUpdate = (callback, delay = 750) => {
  clearTimeout(debounceTimeoutId)
  debounceTimeoutId = setTimeout(callback, delay)
}

watch(
  () => settings,
  () => {
    if (!origSettings.value) return
    debounceUpdate(() => {
      const currentValues = JSON.parse(JSON.stringify(settings.value))
      if (JSON.stringify(currentValues) === JSON.stringify(origSettings.value)) return
      socket.emit('update:settings', currentValues)
    })
  },
  { deep: true },
)
/* v8 ignore stop */
</script>
