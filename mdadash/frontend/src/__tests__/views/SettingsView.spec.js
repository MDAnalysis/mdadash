import { mount } from '@vue/test-utils'
import { expect, describe, it } from 'vitest'
import * as components from 'vuetify/components'
import { ref } from 'vue'
import SettingsView from '@/views/SettingsView.vue'
import { mdiDelete, mdiPlus } from '@mdi/js'

const { VBtn } = components

const runningState = { pending: false, connected: false, running: false }

const settings = ref({
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

describe('SettingsView.vue', () => {
  it('mounts', async () => {
    const wrapper = mount(SettingsView, {
      global: {
        provide: {
          runningState,
          settings,
          origSettings: settings,
        },
      },
    })
    expect(wrapper.exists()).toBe(true)
  })

  it('update the settings page', async () => {
    const wrapper = mount(SettingsView, {
      global: {
        provide: {
          runningState,
          settings,
          origSettings: settings,
        },
      },
    })
    // expand / hide universe config settings
    const vCardItems = wrapper.findAllComponents({ name: 'VCardItem' })
    const firstCardItem = vCardItems[0]
    await firstCardItem.trigger('click')
    // update universe config values
    const form = wrapper.findComponent({ name: 'VForm' })
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
