import { mount } from '@vue/test-utils'
import { beforeEach, expect, describe, it, vi } from 'vitest'
import { ref } from 'vue'
import { socket } from '@/socket'
import { flushPromises } from '@vue/test-utils'
import WidgetView from '@/views/WidgetView.vue'

const settings = ref({
  dashboard_config: {
    ui_request_timeout: 5,
  },
})

const allProvides = {
  settings,
}

vi.mock('vue-router', () => ({
  useRoute: () => ({
    query: { uuid: 'uuid1' },
  }),
}))

let socketListeners = {}
const widgetDetails = {
  uuid: 'uuid1',
  name: 'name1',
  description: 'desc1',
  inputs: [
    {
      attribute: 'selection',
      name: 'Selection',
      description: 'MDAnalysis selection phrase',
      type: 'str',
      validations: ['required'],
      value: 'resid 1',
    },
    {
      attribute: 'empty_str',
      name: 'Invalid empty input',
      type: 'str',
      validations: ['required'],
    },
    {
      attribute: 'maxlen',
      name: 'Max values',
      description: 'Max values to show in plot',
      type: 'int',
      value: 0,
      error: 'Invalid value',
    },
    {
      attribute: 'x_type',
      name: 'X-axis',
      type: 'toggle',
      options: [
        { name: 'Step', value: 'step' },
        { name: 'Time', value: 'time' },
      ],
      value: 'step',
    },
    {
      attribute: '_analysis_mode',
      name: 'Analysis mode',
      description: 'The mode to run this analysis widget',
      type: 'select',
      items: ['per-frame', 'batch'],
    },
  ],
}

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

describe('WidgetView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('mounts and unmounts', () => {
    const wrapper = mount(WidgetView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.exists()).toBe(true)
    expect(socket.on).toHaveBeenCalledWith('widget:details', expect.any(Function))
    expect(socket.on).toHaveBeenCalledWith('widgets:output', expect.any(Function))
    // unmount
    wrapper.unmount()
    expect(socket.off).toHaveBeenCalledWith('widget:details')
    expect(socket.off).toHaveBeenCalledWith('widgets:output')
  })

  it('name and desc', async () => {
    const wrapper = mount(WidgetView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.exists()).toBe(true)
    const name = wrapper.find('#name')
    expect(name).toBeDefined()
    name.setValue('name1')
    const description = wrapper.find('#description')
    expect(description).toBeDefined()
    description.setValue('desc1')
    expect(mockEmit).toHaveBeenCalledWith('widget:name_desc_change', {
      uuid: 'uuid1',
      name: 'name1',
      description: 'desc1',
    })
  })

  it('inputs and output card', async () => {
    const wrapper = mount(WidgetView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.exists()).toBe(true)
    const inputsCard = wrapper.find('#inputs')
    const inputsCardItem = inputsCard.findComponent({ name: 'VCardItem' })
    expect(inputsCardItem).toBeDefined()
    await inputsCardItem.trigger('click')
    const outputCard = wrapper.find('#output')
    const ouputCardItem = outputCard.findComponent({ name: 'VCardItem' })
    expect(ouputCardItem).toBeDefined()
    await ouputCardItem.trigger('click')
  })

  it('loads details and output', async () => {
    mockEmitWithAck.mockResolvedValueOnce(widgetDetails)
    const wrapper = mount(WidgetView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.exists()).toBe(true)
    expect(mockTimeout).toHaveBeenNthCalledWith(1, 5000)
    expect(mockEmitWithAck).toHaveBeenNthCalledWith(1, 'widget:get_details', 'uuid1')
    // update widget details
    await socketListeners['widget:details'](widgetDetails)
    expect(wrapper.vm.widgetDetails).toStrictEqual(widgetDetails)
    // update widget output
    await socketListeners['widgets:output']({
      uuid: 'uuid1',
      data: { 'image/png': 'image_data' },
    })
    await flushPromises() // needed for v-img to show up
    // check v-img now exists in widget card
    let components = wrapper.findAllComponents({ name: 'VImg' })
    expect(components[0]).toBeDefined()
    // ignore details and output for other uuid's
    await socketListeners['widget:details']({ uuid: 'other' })
    expect(wrapper.vm.widgetDetails).toStrictEqual(widgetDetails)
    await socketListeners['widgets:output']({ uuid: 'other' })
    // check input change
    const selection = wrapper.find('[data-attribute="selection"]')
    selection.find('input').setValue('protein')
    expect(wrapper.vm.widgetDetails.inputs[0].value).toStrictEqual('protein')
    expect(mockEmit).toHaveBeenCalledWith('widget:input_change', {
      uuid: 'uuid1',
      attribute: 'selection',
      value: 'protein',
    })
    // check toggle btn click
    const x_type = wrapper.find('[data-attribute="x_type"]')
    x_type.trigger('click')
    expect(mockEmit).toHaveBeenCalledWith('widget:input_change', {
      uuid: 'uuid1',
      attribute: 'x_type',
      value: 'step',
    })
    // check select from dropdown
    const mode = wrapper.findComponent('[data-attribute="_analysis_mode"]')
    await mode.vm.$emit('update:modelValue', 'batch')
    // check invalid input update
    const maxlen = wrapper.find('[data-attribute="maxlen"]')
    maxlen.find('input').setValue(100)
    maxlen.trigger('blur')
    expect(mockEmit).toHaveBeenCalledWith('widget:input_change', {
      uuid: 'uuid1',
      attribute: 'maxlen',
      value: 100,
    })
  })
})
