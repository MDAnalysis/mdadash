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
          <v-icon icon="mdi-chart-timeline-variant" color="primary" />
        </template>
        <template v-slot:append>
          <v-btn
            :icon="isEnergiesExpanded ? 'mdi-chevron-up' : 'mdi-chevron-down'"
            variant="text"
          ></v-btn>
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
                      {{ energy.trend > 0 ? 'mdi-trending-up' : 'mdi-trending-down' }}
                    </v-icon>
                  </div>
                </v-fade-transition>
              </v-col>
            </v-row>
          </v-card-text>
        </div>
      </v-expand-transition>
    </v-card>
    <!-- TODO: rest of the dashboard -->
  </v-container>
</template>

<script setup>
import { ref, inject } from 'vue'

const timestepInfo = inject('timestepInfo')

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

const isEnergiesExpanded = ref(true)
</script>

<style scoped></style>
