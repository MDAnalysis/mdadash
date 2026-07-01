import { mount } from '@vue/test-utils'
import { beforeEach, expect, describe, it, vi } from 'vitest'
import DashboardView from '@/views/DashboardView.vue'
import { socket } from '@/socket'
import { nextTick, ref } from 'vue'
import { flushPromises } from '@vue/test-utils'

const timestepInfo = {
  frame: 0,
  time: 0.2,
  step: 1,
  done: 0,
  energies: {
    temperature: { value: 0, trend: 0 },
    total_energy: { value: 0, trend: -1 },
    potential_energy: { value: 0, trend: 1 },
    van_der_walls_energy: { value: 0, trend: 0 },
    coulomb_energy: { value: 0, trend: 0 },
    bonds_energy: { value: 0, trend: 0 },
    angles_energy: { value: 0, trend: 0 },
    dihedrals_energy: { value: 0, trend: 0 },
    improper_dihedrals_energy: { value: 0, trend: 0 },
  },
}

const settings = ref({
  dashboard_config: {
    show_session_info: true,
    show_energies: true,
    ui_request_timeout: 5,
  },
})

const allProvides = {
  timestepInfo,
  settings,
}

const widgetsList = [
  { name: 'name1', description: 'desc1' },
  { name: 'name2', description: 'desc2' },
]

const widgetsLayout = [
  {
    x: 0,
    y: 0,
    w: 12,
    h: 14,
    i: 'uuid1',
    name: 'name1',
    description: 'desc1',
  },
  {
    x: 0,
    y: 0,
    w: 12,
    h: 14,
    i: 'uuid2',
    name: 'name2',
    description: 'desc2',
  },
]

const mockPush = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
  useRoute: () => ({
    params: { uuid: 'uuid' },
  }),
}))

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

const KeepAliveDashboardView = {
  components: { DashboardView },
  setup() {
    return { isVisible: ref(true) }
  },
  template: '<KeepAlive><DashboardView v-if="isVisible" /></KeepAlive>',
}

describe('DashboardView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('activate and deactivate', async () => {
    const wrapper = mount(KeepAliveDashboardView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.findComponent(DashboardView).exists()).toBe(true)
    // onActivated
    expect(socket.on).toHaveBeenCalledWith('sessionInfo', expect.any(Function))
    expect(socket.on).toHaveBeenCalledWith('widgets:layout', expect.any(Function))
    expect(socket.on).toHaveBeenCalledWith('widgets:output', expect.any(Function))
    await socketListeners['sessionInfo']({ time: true, energies: false })
    // onDeactivated
    wrapper.vm.isVisible = false
    await nextTick()
    expect(socket.off).toHaveBeenCalledWith('sessionInfo')
    expect(socket.off).toHaveBeenCalledWith('widgets:layout')
    expect(socket.off).toHaveBeenCalledWith('widgets:output')
  })

  it('has energies card', async () => {
    const wrapper = mount(KeepAliveDashboardView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.findComponent(DashboardView).exists()).toBe(true)
    const dashboard = wrapper.findComponent(DashboardView)
    expect(dashboard.exists()).toBe(true)
    const energiesCard = dashboard.find('#energies')
    const energiesCardItem = energiesCard.findComponent({ name: 'VCardItem' })
    expect(energiesCardItem).toBeDefined()
    await energiesCardItem.trigger('click')
  })

  it('test add widget', async () => {
    const wrapper = mount(KeepAliveDashboardView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.findComponent(DashboardView).exists()).toBe(true)
    const dashboard = wrapper.findComponent(DashboardView)
    expect(dashboard.exists()).toBe(true)
    // click add widgets button
    const addWidgetsBtn = dashboard.find('#add-widget-btn')
    expect(addWidgetsBtn).toBeDefined()
    dashboard.vm.setAddWidgetMenuState(true)
    mockEmitWithAck
      .mockResolvedValueOnce({ widgets: widgetsList })
      .mockResolvedValueOnce({ uuid: 'uuid1' })
    await addWidgetsBtn.trigger('click')
    await nextTick()
    expect(mockTimeout).toHaveBeenNthCalledWith(1, 5000)
    expect(mockEmitWithAck).toHaveBeenNthCalledWith(1, 'widgets:get_available_widgets')
    await nextTick()
    // check the list of widgets
    expect(dashboard.vm.addWidgetItems).toStrictEqual([
      { name: 'name1', description: 'desc1' },
      { name: 'name2', description: 'desc2' },
    ])
    // select a widget from list
    const components = dashboard.findAllComponents({ name: 'VAutocomplete' })
    const autocomplete = components[1]
    expect(autocomplete).toBeDefined()
    await autocomplete.vm.$emit('update:modelValue', { name: 'name1', description: 'desc1' })
    expect(mockEmitWithAck).toHaveBeenNthCalledWith(2, 'widgets:add_widget', 0, 'name1', 'desc1')
    // check page moves to widget view
    expect(mockPush).toHaveBeenCalledWith({
      path: '/widget',
      query: {
        uuid: 'uuid1',
      },
    })
    dashboard.vm.setAddWidgetMenuState(false)
    // check that widget layout was sent by server
    await socketListeners['widgets:layout'](widgetsLayout)
    // check that the layout is updated
    expect(dashboard.vm.layoutWidgets).toStrictEqual(widgetsLayout)
    expect(dashboard.vm.displayedLayoutWidgets).toStrictEqual(widgetsLayout)
    // handleAddWidgetClick - not open - for coverage
    dashboard.vm.handleAddWidgetClick(false)
    // check that same widget layout sent by server causes no update
    let prevLayoutWidgets = dashboard.vm.layoutWidgets
    await socketListeners['widgets:layout'](widgetsLayout)
    expect(dashboard.vm.layoutWidgets).toStrictEqual(prevLayoutWidgets)
  })

  it('test add widget search', async () => {
    const wrapper = mount(KeepAliveDashboardView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.findComponent(DashboardView).exists()).toBe(true)
    const dashboard = wrapper.findComponent(DashboardView)
    expect(dashboard.exists()).toBe(true)
    // search using invalid query
    let ret = dashboard.vm.customAddWidgetFilter('value', null, {
      raw: { name: 'name1', description: 'desc1' },
    })
    expect(ret).toBe(undefined)
    // search by name
    ret = dashboard.vm.customAddWidgetFilter('value', 'name1', {
      raw: { name: 'name1', description: 'desc1' },
    })
    expect(ret).toBe(true)
    // search by description
    ret = dashboard.vm.customAddWidgetFilter('value', 'desc1', {
      raw: { name: 'name1', description: 'desc1' },
    })
    expect(ret).toBe(true)
    // search not matching
    ret = dashboard.vm.customAddWidgetFilter('value', 'query', {
      raw: {},
    })
    expect(ret).toBe(false)
  })

  it('test grid filtering', async () => {
    const wrapper = mount(KeepAliveDashboardView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.findComponent(DashboardView).exists()).toBe(true)
    const dashboard = wrapper.findComponent(DashboardView)
    expect(dashboard.exists()).toBe(true)
    // create test layout
    dashboard.vm.layoutWidgets = widgetsLayout
    dashboard.vm.displayedLayoutWidgets = ref(widgetsLayout)
    // click Filter Widgets
    const components = dashboard.findAllComponents({ name: 'VAutocomplete' })
    const autocomplete = components[0]
    expect(autocomplete).toBeDefined()
    autocomplete.vm.menu = true
    // check all widgets show up when no filtering
    await autocomplete.vm.$emit('update:modelValue', [])
    expect(dashboard.vm.displayedLayoutWidgets).toStrictEqual(widgetsLayout)
    // check specific widget filtering
    dashboard.vm.selectedLayoutWidgets = ['uuid1']
    await autocomplete.vm.$emit('update:modelValue', ['uuid1'])
    expect(dashboard.vm.displayedLayoutWidgets).toStrictEqual([widgetsLayout[0]])
  })

  it('test layout change', async () => {
    const wrapper = mount(KeepAliveDashboardView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.findComponent(DashboardView).exists()).toBe(true)
    const dashboard = wrapper.findComponent(DashboardView)
    expect(dashboard.exists()).toBe(true)
    // create test layout
    dashboard.vm.layoutWidgets = widgetsLayout
    dashboard.vm.displayedLayoutWidgets = ref(widgetsLayout)
    // check layout model updation
    dashboard.vm.updateDisplayedLayoutWidgets(ref(widgetsLayout))
    expect(dashboard.vm.displayedLayoutWidgets).toStrictEqual(widgetsLayout)
    // check updated layout sent to server
    dashboard.vm.layoutUpdate()
    expect(mockEmit).toHaveBeenCalledWith('widgets:update_layout', widgetsLayout)
    // check layout update not sent when filtered
    dashboard.vm.selectedLayoutWidgets = ['uuid1']
    dashboard.vm.layoutUpdate()
    expect(mockEmit).not.toHaveBeenCalledWith('widgets:update_layout')
    // trigger selectstart event and check it is prevented
    // this prevents text selection etc when resizing grid items
    const components = dashboard.findAllComponents({ name: 'GridLayout' })
    const event = new Event('selectstart', {
      bubbles: true,
      cancelable: true,
    })
    await components[0].element.dispatchEvent(event)
    expect(event.defaultPrevented).toBe(true)
  })

  it('test widget outputs', async () => {
    const wrapper = mount(KeepAliveDashboardView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.findComponent(DashboardView).exists()).toBe(true)
    const dashboard = wrapper.findComponent(DashboardView)
    expect(dashboard.exists()).toBe(true)
    // create test layout
    dashboard.vm.layoutWidgets = widgetsLayout
    dashboard.vm.displayedLayoutWidgets = ref(widgetsLayout)
    //wrapper.vm.updateDisplayedLayoutWidgets(ref(widgetsLayout))
    let components = dashboard.findAllComponents({ name: 'VImg' })
    expect(components[0]).toBe(undefined)
    // send widget output from server
    await socketListeners['widgets:output']({
      uuid: 'uuid1',
      data: { 'image/png': 'image_data' },
    })
    await flushPromises() // needed for v-img to show up
    // check v-img now exists in widget card
    components = dashboard.findAllComponents({ name: 'VImg' })
    expect(components[0]).toBeDefined()
  })

  it('test widget actions', async () => {
    const wrapper = mount(KeepAliveDashboardView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.findComponent(DashboardView).exists()).toBe(true)
    const dashboard = wrapper.findComponent(DashboardView)
    expect(dashboard.exists()).toBe(true)
    // create test layout
    dashboard.vm.layoutWidgets = widgetsLayout
    dashboard.vm.displayedLayoutWidgets = ref(widgetsLayout)
    await flushPromises()
    // get first grid item
    let components = dashboard.findAllComponents({ name: 'GridItem' })
    const widgetGridItem = components[0]
    // double click on the card for edit
    components = widgetGridItem.findAllComponents({ name: 'VCard' })
    const card = components[0]
    card.trigger('dblclick')
    expect(mockPush).toHaveBeenCalledWith({
      path: '/widget',
      query: {
        uuid: 'uuid1',
      },
    })
    components = widgetGridItem.findAllComponents({ name: 'VBtn' })
    // click on the widget action button
    const actionBtn = components[0]
    expect(actionBtn).toBeDefined()
    await actionBtn.trigger('click')
    components = widgetGridItem.findAllComponents({ name: 'VListItem' })
    // check there are three actions
    expect(components.length).toBe(3)
    // click on edit
    components[0].trigger('click')
    // click on duplicate
    mockEmitWithAck.mockResolvedValueOnce({ uuid: 'uuid2' })
    components[1].trigger('click')
    await nextTick()
    expect(mockTimeout).toHaveBeenCalledWith(5000)
    expect(mockEmitWithAck).toHaveBeenCalledWith(
      'widgets:duplicate_widget',
      0,
      'uuid1',
      'name1',
      'desc1',
    )
    // check page moves to widget view
    expect(mockPush).toHaveBeenCalledWith({
      path: '/widget',
      query: {
        uuid: 'uuid2',
      },
    })
    // click on the delete action
    components[2].trigger('click')
    // check remove widget sent to server
    expect(mockEmit).toHaveBeenCalledWith('widgets:remove_widget', 'uuid1')
  })

  it('test display presets', async () => {
    const wrapper = mount(KeepAliveDashboardView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.findComponent(DashboardView).exists()).toBe(true)
    const dashboard = wrapper.findComponent(DashboardView)
    expect(dashboard.exists()).toBe(true)
    // create test layout
    dashboard.vm.layoutWidgets = widgetsLayout
    dashboard.vm.displayedLayoutWidgets = ref(widgetsLayout)
    await flushPromises()
    // check preset values
    let components = dashboard.findAllComponents({ name: 'VSelect' })
    const gridPresetSelect = components[0]
    gridPresetSelect.vm.$slots.item({ item: dashboard.vm.gridPresetIconItems })
    expect(gridPresetSelect).toBeDefined()
    // col 1
    await gridPresetSelect.setValue(dashboard.vm.gridPresetIcons.col1)
    expect(dashboard.vm.gridEditable).toBe(false)
    // check save layout as default
    dashboard.vm.saveLayoutAsDefault()
    expect(dashboard.vm.gridEditable).toBe(true)
    expect(mockEmit).toHaveBeenCalledWith('widgets:update_layout', expect.anything())
    // rest of cols
    await gridPresetSelect.setValue(dashboard.vm.gridPresetIcons.col2)
    expect(dashboard.vm.gridEditable).toBe(false)
    await gridPresetSelect.setValue(dashboard.vm.gridPresetIcons.col3)
    expect(dashboard.vm.gridEditable).toBe(false)
    await gridPresetSelect.setValue(dashboard.vm.gridPresetIcons.editable)
    expect(dashboard.vm.gridEditable).toBe(true)
  })
})
