import { mount } from '@vue/test-utils'
import { expect, describe, it } from 'vitest'
import AlertsView from '@/views/AlertsView.vue'

describe('AlertsView.vue', () => {
  it('mounts', () => {
    const wrapper = mount(AlertsView)
    expect(wrapper.exists()).toBe(true)
  })

  it('renders the alerts page', () => {
    const wrapper = mount(AlertsView)

    const heading = wrapper.find('h1')
    expect(heading.exists()).toBe(true)
    expect(heading.text()).toBe('Alerts')
  })
})
