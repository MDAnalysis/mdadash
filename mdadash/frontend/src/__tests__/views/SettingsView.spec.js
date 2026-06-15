import { mount } from '@vue/test-utils'
import { expect, describe, it } from 'vitest'
import * as components from 'vuetify/components'
import { ref } from 'vue'
import SettingsView from '@/views/SettingsView.vue'
import { mdiDelete, mdiPlus } from '@mdi/js'

const { VBtn } = components

const runningState = { pending: false, connected: false, running: false }

const settings = ref({
  dashboard_config: {
    show_session_info: true,
    show_energies: true,
  },
  universe_configs: [
    {
      topology: null,
      trajectory: null,
      socket_bufsize: null,
      buffer_size: 10000000,
      timeout: 5,
      continue_after_disconnect: null,
      step: 1,
      total_steps: null,
      kwargs: [['n1', 'v1']],
    },
  ],
})

const allProvides = {
  runningState,
  settings,
  origSettings: settings,
}

describe('SettingsView.vue', () => {
  it('mounts', async () => {
    const wrapper = mount(SettingsView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.exists()).toBe(true)
  })

  it('update and test dashboard config values', async () => {
    const wrapper = mount(SettingsView, {
      global: {
        provide: allProvides,
      },
    })
    // expand / hide dashboard config settings
    const dcCard = wrapper.find('#dashboard-configuration')
    expect(dcCard).toBeDefined()
    const dcCardItem = dcCard.findComponent({ name: 'VCardItem' })
    expect(dcCardItem).toBeDefined()
    await dcCardItem.trigger('click')
    // update dashboard config values
    const form = dcCard.findComponent({ name: 'VForm' })
    expect(form.exists()).toBe(true)
    const dataMap = {
      VSwitch: true,
    }
    const keys = Object.keys(dataMap)
    for (const name of keys) {
      const inputs = form.findAllComponents({ name })
      for (const input of inputs) {
        await input.setValue(dataMap[name])
      }
    }
  })

  it('update and test universe config values', async () => {
    const wrapper = mount(SettingsView, {
      global: {
        provide: allProvides,
      },
    })
    // expand / hide universe config settings
    const ucCard = wrapper.find('#universe-configuration')
    expect(ucCard).toBeDefined()
    const ucCardItem = ucCard.findComponent({ name: 'VCardItem' })
    expect(ucCardItem).toBeDefined()
    await ucCardItem.trigger('click')
    // update universe config values
    const form = ucCard.findComponent({ name: 'VForm' })
    expect(form.exists()).toBe(true)
    const dataMap = {
      VTextField: '',
      VNumberInput: 0,
      VCheckbox: true,
      VSelect: '',
    }
    const keys = Object.keys(dataMap)
    for (const name of keys) {
      const inputs = form.findAllComponents({ name })
      for (const input of inputs) {
        await input.setValue(dataMap[name])
      }
    }
    // add kwarg
    const addKwargBtn = wrapper.findAllComponents(VBtn).find((btn) => {
      return btn.html().includes(mdiPlus)
    })
    expect(addKwargBtn).toBeDefined()
    await addKwargBtn.trigger('click')
    // remove kwarg
    const removeKwargBtn = wrapper.findAllComponents(VBtn).find((btn) => {
      return btn.html().includes(mdiDelete)
    })
    expect(removeKwargBtn).toBeDefined()
    await removeKwargBtn.trigger('click')
  })
})
