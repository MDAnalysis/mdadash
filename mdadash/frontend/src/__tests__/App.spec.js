import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import * as components from 'vuetify/components'
import { routes } from '@/router/index.js'
import { socket } from '@/socket'
import App from '../App.vue'
import {
  mdiBellOutline,
  mdiDotsVertical,
  mdiLanConnect,
  mdiLanDisconnect,
  mdiPause,
  mdiPlay,
  mdiViewDashboard,
} from '@mdi/js'

const { VAppBar, VBtn } = components

let socketListeners = {}

vi.mock('@/socket', () => ({
  socket: {
    emit: vi.fn(),
    on: vi.fn((event, callback) => {
      socketListeners[event] = callback
    }),
    off: vi.fn((event) => {
      delete socketListeners[event]
    }),
  },
}))

const router = createRouter({
  history: createMemoryHistory(),
  routes: routes,
})

describe('App', () => {
  it('mounts and unmounts', async () => {
    // mount
    const wrapper = mount(App, {
      global: {
        plugins: [router],
      },
    })
    expect(socket.on).toHaveBeenCalledWith('connect', expect.any(Function))
    expect(socket.on).toHaveBeenCalledWith('disconnect', expect.any(Function))
    expect(socket.on).toHaveBeenCalledWith('runningState', expect.any(Function))
    expect(socket.on).toHaveBeenCalledWith('timestepInfo', expect.any(Function))
    expect(socket.on).toHaveBeenCalledWith('settings', expect.any(Function))
    // unmount
    wrapper.unmount()
    expect(socket.off).toHaveBeenCalledWith('connect')
    expect(socket.off).toHaveBeenCalledWith('disconnect')
    expect(socket.off).toHaveBeenCalledWith('runningState')
    expect(socket.off).toHaveBeenCalledWith('timestepInfo')
    expect(socket.off).toHaveBeenCalledWith('settings')
  })

  it('app bar connectivity', async () => {
    const wrapper = mount(App, {
      global: {
        plugins: [router],
      },
    })
    expect(wrapper.exists()).toBe(true)
    const appBar = wrapper.findComponent(VAppBar)
    expect(appBar.exists()).toBe(true)
    // test dashboard server connectivity
    await socketListeners['connect']({})
    expect(wrapper.vm.socketConnected).toStrictEqual(true)
    await socketListeners['disconnect']({})
    expect(wrapper.vm.socketConnected).toStrictEqual(false)
    // click connect button
    const connectBtn = appBar.findAllComponents(VBtn).find((btn) => {
      return btn.html().includes(mdiLanConnect)
    })
    expect(connectBtn).toBeDefined()
    await connectBtn.trigger('click')
    expect(connectBtn.attributes('disabled')).toBeDefined()
    expect(socket.emit).toHaveBeenCalledWith('connect_to_simulations')
    window.alert = () => {}
    await socketListeners['runningState']({
      pending: false,
      connected: true,
      running: false,
      message: 'ok',
    })
    await socketListeners['timestepInfo']({ energies: {} })
    await socketListeners['settings']({ universe_configs: [{}] })
    // click resume button
    const resumeBtn = appBar.findAllComponents(VBtn).find((btn) => {
      return btn.html().includes(mdiPlay)
    })
    expect(resumeBtn).toBeDefined()
    await resumeBtn.trigger('click')
    expect(socket.emit).toHaveBeenCalledWith('resume_simulations')
    await socketListeners['runningState']({ pending: false, connected: true, running: true })
    // click pause button
    const pauseBtn = appBar.findAllComponents(VBtn).find((btn) => {
      return btn.html().includes(mdiPause)
    })
    expect(pauseBtn).toBeDefined()
    await pauseBtn.trigger('click')
    expect(socket.emit).toHaveBeenCalledWith('pause_simulations')
    await socketListeners['runningState']({ pending: false, connected: true, running: false })
    // click disconnect button
    const disconnectBtn = appBar.findAllComponents(VBtn).find((btn) => {
      return btn.html().includes(mdiLanDisconnect)
    })
    expect(disconnectBtn).toBeDefined()
    await disconnectBtn.trigger('click')
    // click on cancel
    const cancelBtn = appBar.findAllComponents(VBtn).find((btn) => {
      return btn.html().includes('Cancel')
    })
    expect(cancelBtn).toBeDefined()
    await cancelBtn.trigger('click')
    // click on confirm
    await disconnectBtn.trigger('click')
    const confirmBtn = appBar.findAllComponents(VBtn).find((btn) => {
      return btn.html().includes('Disconnect')
    })
    expect(confirmBtn).toBeDefined()
    await confirmBtn.trigger('click')
  })

  it('app bar navigation', async () => {
    const wrapper = mount(App, {
      global: {
        plugins: [router],
      },
    })
    expect(wrapper.exists()).toBe(true)
    const appBar = wrapper.findComponent(VAppBar)
    expect(appBar.exists()).toBe(true)
    // click on alerts
    const alertsBtn = appBar.findAllComponents(VBtn).find((btn) => {
      return btn.html().includes(mdiBellOutline)
    })
    expect(alertsBtn).toBeDefined()
    await alertsBtn.trigger('click')
    // click on dashboard icon
    const dashboardBtn = appBar.findAllComponents(VBtn).find((btn) => {
      return btn.html().includes(mdiViewDashboard)
    })
    expect(dashboardBtn).toBeDefined()
    await dashboardBtn.trigger('click')
    const moreItemsBtn = appBar.findAllComponents(VBtn).find((btn) => {
      return btn.html().includes(mdiDotsVertical)
    })
    expect(moreItemsBtn).toBeDefined()
    await moreItemsBtn.trigger('click')
  })
})
