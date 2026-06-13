<template>
  <v-container class="bg-grey-lighten-5">
    <!-- Energies Card -->
    <v-card class="mb-6" elevation="1" v-show="timestepInfo.energies['temperature']">
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
        :is-draggable="true"
        :is-resizable="true"
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
          <v-card class="mb-6 h-100 d-flex flex-column" elevation="2">
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
import { ref, inject, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { GridLayout, GridItem } from 'grid-layout-plus'
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
} from '@mdi/js'

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
const layoutWidgets = ref([])
const selectedLayoutWidgets = ref([])
const isAddWidgetOpen = ref(false)
const isAddWidgetLoading = ref(true)
const addWidgetItems = ref([])
const addWidgetAutoCompleteRef = ref(null)
const widgetsGridKey = ref(0)
const widgetOutputs = ref({})
var displayedLayoutWidgets = ref([...layoutWidgets.value])

function setAddWidgetMenuState(value) {
  isAddWidgetOpen.value = value
}

function updateDisplayedLayoutWidgets(value) {
  displayedLayoutWidgets = value
}

const onAddWidgetSelected = (obj) => {
  // Add widget on the server side
  socket.emit('widgets:add_widget', obj.name, obj.description)
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
    const response = await socket.timeout(5000).emitWithAck('widgets:get_available_widgets')
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

function widgetFunction(item, action) {
  // Handle widget actions
  if (action['title'] == 'Delete') {
    socket.emit('widgets:remove_widget', item.i)
  }
}

function layoutUpdate() {
  // Update layout on the server side
  if (selectedLayoutWidgets.value.length == 0) {
    socket.emit('widgets:update_layout', displayedLayoutWidgets.value)
  }
}

onMounted(() => {
  socket.on('widgets:layout', async (data) => {
    // Update layoutWidgets only if it changed
    if (JSON.stringify(data) !== JSON.stringify(layoutWidgets.value)) {
      layoutWidgets.value = data
      // v8 ignore next
      if (selectedLayoutWidgets.value.length == 0) {
        displayedLayoutWidgets = ref([...layoutWidgets.value])
        widgetsGridKey.value++
      }
    }
  })
  socket.on('widgets:output', (data) => {
    // Update the widget outputs ref
    widgetOutputs.value[data['uuid']] = data['data']
  })
})

onBeforeUnmount(() => {
  socket.off('widgets:layout')
  socket.off('widgets:output')
})
</script>

<style scoped></style>
