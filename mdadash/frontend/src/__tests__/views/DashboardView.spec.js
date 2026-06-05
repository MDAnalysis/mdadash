import { mount } from '@vue/test-utils'
import { expect, describe, it } from 'vitest'
import DashboardView from '@/views/DashboardView.vue'

const timestepInfo = {
  frame: 0,
  time: 0.2,
  step: 1,
  done: 0,
  energies: {
    temperature: 0,
    total_energy: 0,
    potential_energy: 0,
    van_der_walls_energy: 0,
    coulomb_energy: 0,
    bonds_energy: 0,
    angles_energy: 0,
    dihedrals_energy: 0,
    improper_dihedrals_energy: 0,
  },
}

describe('DashboardView.vue', () => {
  it('mounts', async () => {
    const wrapper = mount(DashboardView, {
      global: {
        provide: {
          timestepInfo,
        },
      },
    })
    expect(wrapper.exists()).toBe(true)
    // expand / hide energy items
    const vCardItems = wrapper.findAllComponents({ name: 'VCardItem' })
    const firstCardItem = vCardItems[0]
    await firstCardItem.trigger('click')
  })
})
