import { mount } from '@vue/test-utils'
import { beforeEach, expect, describe, it, vi } from 'vitest'
import { ref } from 'vue'
import { Codemirror } from 'vue-codemirror'
import NotebookCell from '@/components/NotebookCell.vue'

const settings = ref({
  dashboard_config: {
    ui_request_timeout: 5,
  },
})

const allProvides = {
  settings,
}

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

const kbEvent = (wrapper, key, modifiers = {}) => {
  const cmContent = wrapper.find('.cm-content')
  const event = new KeyboardEvent('keydown', {
    key: key,
    code: key,
    ctrlKey: Boolean(modifiers.ctrl),
    shiftKey: Boolean(modifiers.shift),
    metaKey: Boolean(modifiers.meta),
    bubbles: true,
    cancelable: true,
  })
  cmContent.element.dispatchEvent(event)
}

describe('NotebookCell.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('check mount', async () => {
    const wrapper = mount(NotebookCell, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper).toBeDefined()
  })

  it('check props', async () => {
    const wrapper = mount(NotebookCell, {
      global: {
        provide: allProvides,
      },
      props: {
        showDrag: true,
        showDelete: true,
        addCell: true,
        hint: 'hint',
      },
    })
    expect(wrapper).toBeDefined()
  })

  it('check buttons', async () => {
    const wrapper = mount(NotebookCell, {
      global: {
        provide: allProvides,
      },
      props: {
        showDrag: true,
        showDelete: true,
        addCell: true,
        hint: 'hint',
        code: 'x = 5',
      },
    })
    expect(wrapper).toBeDefined()
    const actionsWrapper = wrapper.findComponent({ name: 'VCardActions' })
    await actionsWrapper.trigger('dblclick')
    const buttons = wrapper.findAllComponents({ name: 'VBtn' })
    mockEmitWithAck.mockResolvedValueOnce([
      { type: 'text', content: 'text' },
      { type: 'error', content: 'error' },
      { type: 'image', content: 'image' },
    ])
    for (const button of buttons) {
      await button.trigger('click')
    }
  })

  it('check kb events', async () => {
    const wrapper = mount(NotebookCell, {
      global: {
        provide: allProvides,
      },
      props: {
        id: 'id',
        modelValue: 'code',
      },
    })
    expect(wrapper).toBeDefined()
    kbEvent(wrapper, 'Enter', { ctrl: true })
    expect(mockEmitWithAck).toHaveBeenNthCalledWith(
      1,
      'cell_run',
      JSON.stringify({ cell_id: 'id', code: 'code' }),
    )
    kbEvent(wrapper, 'Enter', { meta: true })
    kbEvent(wrapper, 'Enter', { shift: true })
  })

  it('check codemirror', async () => {
    const wrapper = mount(NotebookCell, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper).toBeDefined()
    const cm = wrapper.findComponent(Codemirror)
    await cm.vm.$emit('update:modelValue', 'newCode')
    expect(wrapper.vm.code).toBe('newCode')
  })
})
