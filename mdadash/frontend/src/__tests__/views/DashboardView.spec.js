import { mount } from '@vue/test-utils'
import { expect, describe, it, vi } from 'vitest'
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

const settings = {
  dashboard_config: {
    show_session_info: true,
    show_energies: true,
  },
}

const sessionInfo = {
  time: true,
  energies: false,
}

const allProvides = {
  timestepInfo,
  sessionInfo,
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
    timeout: vi.fn().mockImplementation(() => ({
      emitWithAck: vi.fn().mockResolvedValue({
        widgets: widgetsList,
      }),
    })),
  },
}))

describe('DashboardView.vue', () => {
  it('mounts and unmounts', async () => {
    const wrapper = mount(DashboardView, {
      global: {
        provide: allProvides,
      },
    })
    expect(socket.on).toHaveBeenCalledWith('widgets:layout', expect.any(Function))
    expect(socket.on).toHaveBeenCalledWith('widgets:output', expect.any(Function))
    wrapper.unmount()
    expect(socket.off).toHaveBeenCalledWith('widgets:layout')
    expect(socket.off).toHaveBeenCalledWith('widgets:output')
  })

  it('has energies card', async () => {
    const wrapper = mount(DashboardView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.exists()).toBe(true)
    const energiesCard = wrapper.find('#energies')
    const energiesCardItem = energiesCard.findComponent({ name: 'VCardItem' })
    expect(energiesCardItem).toBeDefined()
    await energiesCardItem.trigger('click')
  })

  it('test add widget', async () => {
    const wrapper = mount(DashboardView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.exists()).toBe(true)
    // click add widgets button
    const addWidgetsBtn = wrapper.find('#add-widget-btn')
    expect(addWidgetsBtn).toBeDefined()
    wrapper.vm.setAddWidgetMenuState(true)
    await addWidgetsBtn.trigger('click')
    await nextTick()
    // check the list of widgets
    expect(wrapper.vm.addWidgetItems).toStrictEqual([
      { name: 'name1', description: 'desc1' },
      { name: 'name2', description: 'desc2' },
    ])
    // select a widget from list
    const components = wrapper.findAllComponents({ name: 'VAutocomplete' })
    const autocomplete = components[1]
    expect(autocomplete).toBeDefined()
    await autocomplete.vm.$emit('update:modelValue', { name: 'name1', description: 'desc1' })
    // check that add widget got sent to server
    expect(socket.emit).toHaveBeenCalledWith('widgets:add_widget', 'name1', 'desc1')
    wrapper.vm.setAddWidgetMenuState(false)
    // check that widget layout was sent by server
    await socketListeners['widgets:layout'](widgetsLayout)
    // check that the layout is updated
    expect(wrapper.vm.layoutWidgets).toStrictEqual(widgetsLayout)
    expect(wrapper.vm.displayedLayoutWidgets).toStrictEqual(widgetsLayout)
    // handleAddWidgetClick - not open - for coverage
    wrapper.vm.handleAddWidgetClick(false)
    // check that same widget layout sent by server causes no update
    let prevLayoutWidgets = wrapper.vm.layoutWidgets
    await socketListeners['widgets:layout'](widgetsLayout)
    expect(wrapper.vm.layoutWidgets).toStrictEqual(prevLayoutWidgets)
  })

  it('test add widget search', async () => {
    const wrapper = mount(DashboardView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.exists()).toBe(true)
    // search using invalid query
    let ret = wrapper.vm.customAddWidgetFilter('value', null, {
      raw: { name: 'name1', description: 'desc1' },
    })
    expect(ret).toBe(undefined)
    // search by name
    ret = wrapper.vm.customAddWidgetFilter('value', 'name1', {
      raw: { name: 'name1', description: 'desc1' },
    })
    expect(ret).toBe(true)
    // search by description
    ret = wrapper.vm.customAddWidgetFilter('value', 'desc1', {
      raw: { name: 'name1', description: 'desc1' },
    })
    expect(ret).toBe(true)
    // search not matching
    ret = wrapper.vm.customAddWidgetFilter('value', 'query', {
      raw: {},
    })
    expect(ret).toBe(false)
  })

  it('test grid filtering', async () => {
    const wrapper = mount(DashboardView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.exists()).toBe(true)
    // create test layout
    wrapper.vm.layoutWidgets = widgetsLayout
    wrapper.vm.displayedLayoutWidgets = ref(widgetsLayout)
    // click Filter Widgets
    const components = wrapper.findAllComponents({ name: 'VAutocomplete' })
    const autocomplete = components[0]
    expect(autocomplete).toBeDefined()
    autocomplete.vm.menu = true
    // check all widgets show up when no filtering
    await autocomplete.vm.$emit('update:modelValue', [])
    expect(wrapper.vm.displayedLayoutWidgets).toStrictEqual(widgetsLayout)
    // check specific widget filtering
    wrapper.vm.selectedLayoutWidgets = ['uuid1']
    await autocomplete.vm.$emit('update:modelValue', ['uuid1'])
    expect(wrapper.vm.displayedLayoutWidgets).toStrictEqual([widgetsLayout[0]])
  })

  it('test layout change', async () => {
    const wrapper = mount(DashboardView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.exists()).toBe(true)
    // create test layout
    wrapper.vm.layoutWidgets = widgetsLayout
    wrapper.vm.displayedLayoutWidgets = ref(widgetsLayout)
    // check layout model updation
    wrapper.vm.updateDisplayedLayoutWidgets(ref(widgetsLayout))
    expect(wrapper.vm.displayedLayoutWidgets).toStrictEqual(widgetsLayout)
    // check updated layout sent to server
    wrapper.vm.layoutUpdate()
    expect(socket.emit).toHaveBeenCalledWith('widgets:update_layout', widgetsLayout)
    // check layout update not sent when filtered
    wrapper.vm.selectedLayoutWidgets = ['uuid1']
    wrapper.vm.layoutUpdate()
    expect(socket.emit).not.toHaveBeenCalledWith('widgets:update_layout')
    // trigger selectstart event and check it is prevented
    // this prevents text selection etc when resizing grid items
    const components = wrapper.findAllComponents({ name: 'GridLayout' })
    const event = new Event('selectstart', {
      bubbles: true,
      cancelable: true,
    })
    await components[0].element.dispatchEvent(event)
    expect(event.defaultPrevented).toBe(true)
  })

  it('test widget outputs', async () => {
    const wrapper = mount(DashboardView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.exists()).toBe(true)
    // create test layout
    wrapper.vm.layoutWidgets = widgetsLayout
    wrapper.vm.displayedLayoutWidgets = ref(widgetsLayout)
    //wrapper.vm.updateDisplayedLayoutWidgets(ref(widgetsLayout))
    let components = wrapper.findAllComponents({ name: 'VImg' })
    expect(components[0]).toBe(undefined)
    // send widget output from server
    await socketListeners['widgets:output']({
      uuid: 'uuid1',
      data: { 'image/png': 'image_data' },
    })
    await flushPromises() // needed for v-img to show up
    // check v-img now exists in widget card
    components = wrapper.findAllComponents({ name: 'VImg' })
    expect(components[0]).toBeDefined()
  })

  it('test widget actions', async () => {
    const wrapper = mount(DashboardView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.exists()).toBe(true)
    // create test layout
    wrapper.vm.layoutWidgets = widgetsLayout
    wrapper.vm.displayedLayoutWidgets = ref(widgetsLayout)
    await flushPromises()
    // get first grid item
    let components = wrapper.findAllComponents({ name: 'GridItem' })
    const widgetGridItem = components[0]
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
    components[1].trigger('click')
    // click on the delete action
    components[2].trigger('click')
    // check remove widget sent to server
    expect(socket.emit).toHaveBeenCalledWith('widgets:remove_widget', 'uuid1')
  })
})
