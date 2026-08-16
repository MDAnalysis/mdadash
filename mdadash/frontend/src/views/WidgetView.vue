<template>
  <v-container>
    <!-- Widget actions -->
    <v-row class="justify-end d-flex ga-0">
      <!-- Docs link -->
      <v-btn
        v-if="widgetDetails.doclink"
        :href="widgetDetails.doclink"
        target="_blank"
        rel="noopener noreferrer"
        :icon="mdiBookOpenVariantOutline"
        variant="text"
        v-tooltip:bottom="'Documentation'"
      ></v-btn>
      <!-- Duplicate -->
      <v-btn
        :icon="mdiContentDuplicate"
        variant="text"
        @click="onDuplicateWidget"
        v-tooltip:bottom="'Duplicate'"
      ></v-btn>
      <!-- Delete -->
      <v-btn
        :icon="mdiDeleteOutline"
        variant="text"
        color="error"
        @click="onDeleteWidget"
        v-tooltip:bottom="'Delete'"
      ></v-btn>
    </v-row>
    <!-- Widget notes (if any) -->
    <v-alert
      v-if="widgetDetails.notes"
      class="mb-6 text-pre-line"
      closable
      :text="widgetDetails.notes"
      type="info"
      variant="tonal"
    ></v-alert>

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
          <v-btn
            :icon="isInputsExpanded ? mdiUnfoldLessHorizontal : mdiUnfoldMoreHorizontal"
            variant="text"
          ></v-btn>
        </template>
      </v-card-item>
      <v-divider />
      <v-expand-transition>
        <div v-show="isInputsExpanded">
          <v-form class="pa-4" @submit.prevent>
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
          <v-btn
            :icon="isOutputExpanded ? mdiUnfoldLessHorizontal : mdiUnfoldMoreHorizontal"
            variant="text"
          ></v-btn>
        </template>
      </v-card-item>
      <v-divider />
      <v-expand-transition>
        <div v-show="isOutputExpanded">
          <!-- Widget outputs -->
          <v-card-text class="flex-grow-1 overflow-y-auto py-0">
            <div v-for="(item, index) in widgetOutput" :key="index" class="mb-4">
              <pre v-if="item.type === 'text'" class="text-pre-wrap">{{ item.content }}</pre>
              <v-alert
                v-if="item.type === 'error'"
                type="error"
                variant="tonal"
                density="compact"
                class="text-caption"
              >
                {{ item.content }}
              </v-alert>
              <v-img
                :aspect-ratio="16 / 9"
                v-else-if="item.type === 'image'"
                :src="'data:image/jpeg;base64,' + item.content"
                max-width="100%"
                contain
                class="rounded"
              ></v-img>
            </div>
          </v-card-text>
        </div>
      </v-expand-transition>
    </v-card>
    <!-- Delete widget confirmation -->
    <!-- v8 ignore start -->
    <v-dialog v-model="confirmDelete" max-width="400">
      <v-card title="Delete Widget?">
        <template v-slot:prepend>
          <v-icon :icon="mdiAlert" color="warning"></v-icon>
        </template>
        <v-card-text> Are you sure you want to delete this Widget? </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="confirmDelete = false">Cancel</v-btn>
          <v-btn color="error" variant="flat" @click="onDeleteWidget">Delete</v-btn>
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
import { useRoute, useRouter } from 'vue-router'
import { ref, onMounted, onBeforeUnmount, inject, watch } from 'vue'
import {
  mdiAlert,
  mdiBookOpenVariantOutline,
  mdiContentDuplicate,
  mdiDeleteOutline,
  mdiUnfoldLessHorizontal,
  mdiUnfoldMoreHorizontal,
} from '@mdi/js'
import { VTextField, VSelect, VNumberInput, VSwitch, VBtnToggle } from 'vuetify/components'
import NotebookCell from '@/components/NotebookCell.vue'

const route = useRoute()
const router = useRouter()
let uuid = route.query.uuid
const settings = inject('settings')
const isOutputExpanded = ref(true)
const isInputsExpanded = ref(true)
const widgetOutput = ref({})
const widgetDetails = ref({})
const isLoading = ref(false)
const confirmDelete = ref(false)

const componentMap = {
  str: VTextField,
  int: VNumberInput,
  float: VTextField,
  bool: VSwitch,
  select: VSelect,
  toggle: VBtnToggle,
  cell: NotebookCell,
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

const handleKeydown = (event) => {
  if (event.key === 'Enter') {
    onDeleteWidget()
  }
}

watch(confirmDelete, (newVal) => {
  if (newVal) {
    document.addEventListener('keydown', handleKeydown)
  } else {
    document.removeEventListener('keydown', handleKeydown)
  }
})

const onDeleteWidget = async () => {
  confirmDelete.value = !confirmDelete.value
  if (!confirmDelete.value) {
    await socket
      .timeout(settings.value.dashboard_config.ui_request_timeout * 1000)
      .emitWithAck('widgets:remove_widget', uuid)
    router.push({ path: '/' })
  }
}

const onDuplicateWidget = async () => {
  const response = await socket
    .timeout(settings.value.dashboard_config.ui_request_timeout * 1000)
    .emitWithAck(
      'widgets:duplicate_widget',
      0,
      uuid,
      widgetDetails.value.name,
      widgetDetails.value.description,
    )
  if (response) {
    router.push({
      path: '/widget',
      query: { uuid: response.uuid },
    })
  }
}

const loadWidgetDetails = async (widget_uuid) => {
  isLoading.value = true
  try {
    const response = await socket
      .timeout(settings.value.dashboard_config.ui_request_timeout * 1000)
      .emitWithAck('widget:get_details', widget_uuid)
    if (response) {
      uuid = widget_uuid
      widgetDetails.value = response
    } else {
      router.push({ path: '/' })
    }
  } finally {
    isLoading.value = false
  }
}

watch(
  () => route.query.uuid,
  (newUuid) => {
    loadWidgetDetails(newUuid)
  },
)

onMounted(async () => {
  // v8 ignore next
  if (history.state?.widgetOutput) {
    widgetOutput.value = history.state.widgetOutput
    // remove so that refresh doesn't load old value
    delete history.state.widgetOutput
    history.replaceState(history.state, '')
  }
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
  loadWidgetDetails(uuid)
})

onBeforeUnmount(() => {
  socket.off('widget:details')
  socket.off('widgets:output')
  document.removeEventListener('keydown', handleKeydown)
})
</script>
