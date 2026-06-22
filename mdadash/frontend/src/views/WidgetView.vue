<template>
  <v-container>
    <!-- Widget name -->
    <v-text-field
      id="name"
      class="mb-4 mt-2"
      label="Name"
      variant="outlined"
      hint="Widget name"
      persistent-hint
      v-model="widgetDetails.name"
      control-variant="default"
      @change="handleNameDescChange"
    ></v-text-field>

    <!-- Widget description -->
    <v-text-field
      id="description"
      class="mb-4 mt-2"
      label="Description"
      variant="outlined"
      hint="Widget description"
      persistent-hint
      v-model="widgetDetails.description"
      control-variant="default"
      @change="handleNameDescChange"
    ></v-text-field>

    <!-- Inputs card -->
    <v-card id="inputs" class="mb-6" elevation="1">
      <v-card-item
        title="Inputs"
        class="cursor-pointer"
        @click="isInputsExpanded = !isInputsExpanded"
      >
        <template v-slot:append>
          <v-btn :icon="isInputsExpanded ? mdiChevronUp : mdiChevronDown" variant="text"></v-btn>
        </template>
      </v-card-item>
      <v-divider />
      <v-expand-transition>
        <div v-show="isInputsExpanded">
          <v-form class="pa-4">
            <v-row v-for="input in widgetDetails.inputs" :key="input.attribute">
              <v-col cols="12">
                <span v-if="input.type === 'toggle'">
                  {{ input.name }}
                </span>
                <!-- Input -->
                <component
                  :is="componentMap[input.type]"
                  v-model="input.value"
                  :data-attribute="input.attribute"
                  :label="input.name"
                  variant="outlined"
                  :hint="input.description"
                  :persistent-hint="!!input.description"
                  hide-details="auto"
                  v-bind="propsMap[input.type]"
                  control-variant="hidden"
                  @change="(e) => handleInputChange(input)"
                  @blur="input.error && handleInputChange(input)"
                  @click="input.type === 'toggle' && handleInputChange(input)"
                  @update:model-value="input.type === 'select' && handleInputChange(input)"
                  :rules="addRules(input.validations)"
                  :error-messages="input.error"
                  :items="input.items || []"
                >
                  <template v-if="input.type === 'toggle'" #default>
                    <v-btn v-for="opt in input.options" :key="opt.value" :value="opt.value">
                      {{ opt.name }}
                    </v-btn>
                  </template>
                </component>
              </v-col>
            </v-row>
          </v-form>
        </div>
      </v-expand-transition>
    </v-card>

    <!-- Output card -->
    <v-card id="output" class="mb-6" elevation="1">
      <v-card-item
        title="Output"
        class="cursor-pointer"
        @click="isOutputExpanded = !isOutputExpanded"
      >
        <template v-slot:append>
          <v-btn :icon="isOutputExpanded ? mdiChevronUp : mdiChevronDown" variant="text"></v-btn>
        </template>
      </v-card-item>
      <v-divider />
      <v-expand-transition>
        <div v-show="isOutputExpanded">
          <!-- Widget output -->
          <!-- Image -->
          <v-img
            :aspect-ratio="16 / 9"
            v-if="widgetOutput?.['image/png']"
            :src="`data:image/png;base64,${widgetOutput['image/png']}`"
          ></v-img>
        </div>
      </v-expand-transition>
    </v-card>
    <v-overlay :model-value="isLoading" contained class="align-center justify-center" persistent>
      <v-progress-circular indeterminate color="primary" size="64"></v-progress-circular>
    </v-overlay>
  </v-container>
</template>

<script setup>
import { socket } from '@/socket'
import { useRoute } from 'vue-router'
import { ref, onMounted, onBeforeUnmount, inject } from 'vue'
import { mdiChevronDown, mdiChevronUp } from '@mdi/js'
import { VTextField, VSelect, VNumberInput, VSwitch, VBtnToggle } from 'vuetify/components'

const route = useRoute()
const uuid = route.query.uuid
const settings = inject('settings')
const isOutputExpanded = ref(true)
const isInputsExpanded = ref(true)
const widgetOutput = ref({})
const widgetDetails = ref({})
const isLoading = ref(false)

const componentMap = {
  str: VTextField,
  int: VNumberInput,
  float: VTextField,
  bool: VSwitch,
  select: VSelect,
  toggle: VBtnToggle,
}

const propsMap = {
  str: {},
  int: {},
  float: { type: 'number', hideSpinButtons: true },
  bool: { density: 'compact', color: 'primary' },
  select: {},
  toggle: { mandatory: 'true', color: 'primary', class: 'd-flex align-center', rounded: '1' },
}

const validationRules = {
  required: (v) => !!v || 'This input is required',
}

const addRules = (rules) => {
  if (!rules) return []
  return rules.map((r) => validationRules[r]).filter(Boolean)
}

function handleNameDescChange() {
  socket.emit('widget:name_desc_change', {
    uuid,
    name: widgetDetails.value.name,
    description: widgetDetails.value.description,
  })
}

function handleInputChange(input) {
  socket.emit('widget:input_change', {
    uuid,
    attribute: input.attribute,
    value: input.value,
  })
}

onMounted(async () => {
  socket.on('widget:details', (data) => {
    if (data['uuid'] == uuid) {
      widgetDetails.value = data
    }
  })
  socket.on('widgets:output', (data) => {
    if (data['uuid'] == uuid) {
      widgetOutput.value = data['data']
    }
  })
  isLoading.value = true
  try {
    const response = await socket
      .timeout(settings.value.dashboard_config.ui_request_timeout)
      .emitWithAck('widget:get_details', uuid)
    if (response) {
      widgetDetails.value = response
    }
  } finally {
    isLoading.value = false
  }
})

onBeforeUnmount(() => {
  socket.off('widget:details')
  socket.off('widgets:output')
})
</script>
