import { nextTick, ref } from 'vue'
import { mount } from '@vue/test-utils'
import { beforeEach, expect, describe, it, vi } from 'vitest'
import AlertsView from '@/views/AlertsView.vue'

const settings = ref({
  dashboard_config: {
    ui_request_timeout: 5,
  },
})

const alertsCount = ref(0)

const updateAlertsCount = () => {}

const allProvides = {
  settings,
  alertsCount,
  updateAlertsCount,
}

const alerts = [
  {
    id: 0,
    message: 'alert 0',
    tsinfo: {
      frame: 0,
      step: 0,
      time: 0,
    },
  },
  {
    id: 1,
    message: 'alert 1',
  },
]

let socketListeners = {}
const { mockEmitWithAck, mockTimeout, mockOn, mockOff, mockEmit } = vi.hoisted(() => {
  const emitWithAck = vi.fn()
  const timeout = vi.fn().mockImplementation(() => ({ emitWithAck }))
  const emit = vi.fn()
  const on = vi.fn((event, callback) => {
    socketListeners[event] = callback
  })
  const off = vi.fn((event) => {
    delete socketListeners[event]
  })
  return {
    mockOn: on,
    mockOff: off,
    mockEmit: emit,
    mockTimeout: timeout,
    mockEmitWithAck: emitWithAck,
  }
})

vi.mock('@/socket', () => {
  return {
    socket: {
      on: mockOn,
      off: mockOff,
      emit: mockEmit,
      timeout: mockTimeout,
      emitWithAck: mockEmitWithAck,
    },
  }
})

describe('AlertsView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('mounts', () => {
    const wrapper = mount(AlertsView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.exists()).toBe(true)
  })

  it('renders', async () => {
    mockEmitWithAck.mockResolvedValueOnce(alerts)
    const wrapper = mount(AlertsView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.exists()).toBe(true)
    await nextTick()
    // check no: of alerts
    expect(wrapper.vm.alerts.length).toStrictEqual(2)
    // check no page change possible
    wrapper.vm.page = 2
    await nextTick()
    expect(wrapper.vm.page).toStrictEqual(1)
    // check alerts per page
    let components = wrapper.findAllComponents({ name: 'VSelect' })
    const alertsPerPage = components[0]
    alertsPerPage.setValue(20)
    expect(wrapper.vm.alertsPerPage).toStrictEqual(20)
  })

  it('search', async () => {
    mockEmitWithAck.mockResolvedValueOnce(alerts)
    const wrapper = mount(AlertsView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.exists()).toBe(true)
    await nextTick()
    const search = wrapper.find('#search')
    search.setValue('alert')
    expect(wrapper.vm.filteredAlerts.length).toStrictEqual(2)
  })

  it('delete', async () => {
    mockEmitWithAck.mockResolvedValueOnce(alerts)
    const wrapper = mount(AlertsView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.exists()).toBe(true)
    await nextTick()
    let components = wrapper.findAllComponents({ name: 'VBtn' })
    // delete 1st alert
    const deleteFirstAlert = components[0]
    deleteFirstAlert.trigger('click')
    expect(mockEmit).toHaveBeenCalledWith('delete_alert', 0)
    // delete all alerts
    const deleteAllAlerts = components[components.length - 1]
    deleteAllAlerts.trigger('click')
    wrapper.vm.deleteAllAlerts()
    expect(mockEmit).toHaveBeenCalledWith('delete_all_alerts')
  })
})
