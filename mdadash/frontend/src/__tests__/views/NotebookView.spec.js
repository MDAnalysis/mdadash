import { ref } from 'vue'
import { mount } from '@vue/test-utils'
import { beforeEach, expect, describe, it, vi } from 'vitest'
import NotebookView from '@/views/NotebookView.vue'

const settings = ref({
  dashboard_config: {
    ui_request_timeout: 5,
  },
})

const allProvides = {
  settings,
}

const mockPush = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
  useRoute: () => ({
    query: { uuid: 'uuid1' },
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

const notebook = {
  uuid: 'uuid1',
  name: 'name1',
  description: 'description1',
  run_on_launch: true,
  cells: [
    {
      id: 'id1',
      code: 'code1',
    },
  ],
}

describe('NotebookView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('check mount', async () => {
    const wrapper = mount(NotebookView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper).toBeDefined()
  })

  it('loads details', async () => {
    mockEmitWithAck.mockResolvedValueOnce(notebook)
    const wrapper = mount(NotebookView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.exists()).toBe(true)
    expect(mockTimeout).toHaveBeenNthCalledWith(1, 5000)
    expect(mockEmitWithAck).toHaveBeenNthCalledWith(1, 'notebooks:get_notebook', 'uuid1')
  })

  it('name and desc', async () => {
    const wrapper = mount(NotebookView, {
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
    expect(mockEmit).toHaveBeenCalledWith('notebook:name_desc_change', 'uuid1', 'name1', 'desc1')
    // check run_on_launch toggle
    wrapper.vm.onRunOnLaunchToggle()
    expect(mockEmit).toHaveBeenCalledWith('notebook:run_on_launch', 'uuid1', true)
  })

  it('check events', async () => {
    const wrapper = mount(NotebookView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.exists()).toBe(true)
    wrapper.vm.notebook = notebook
    // update cells
    wrapper.vm.updateCells()
    expect(mockEmit).toHaveBeenCalledWith('notebook:update_cells', 'uuid1', notebook.cells)
    // cell change
    wrapper.vm.onCellChange('id1', 0)
    expect(mockEmit).toHaveBeenCalledWith('notebook:cell_change', 'uuid1', 'id1', 'code1')
    // cell add
    wrapper.vm.onCellAdd(0)
    expect(notebook.cells.length).toStrictEqual(2)
    // cell move
    wrapper.vm.onCellMove(0, -1)
    wrapper.vm.onCellMove(0, 1)
    expect(mockEmit).toHaveBeenCalledWith('notebook:update_cells', 'uuid1', notebook.cells)
    // cell drag
    wrapper.vm.onCellDrag()
    expect(mockEmit).toHaveBeenCalledWith('notebook:update_cells', 'uuid1', notebook.cells)
    // cell delete
    wrapper.vm.onCellDelete(1)
    expect(notebook.cells.length).toStrictEqual(1)
    // cell delete first
    wrapper.vm.onCellDelete(0)
    expect(notebook.cells.length).toStrictEqual(1)
    // focus next - add new cell
    wrapper.vm.focusNext(0)
    expect(notebook.cells.length).toStrictEqual(2)
    // focus next 0 -> 1
    wrapper.vm.focusNext(0)
    expect(notebook.cells.length).toStrictEqual(2)
    // delete notebook - confirm
    wrapper.vm.onDeleteNotebook()
    expect(wrapper.vm.confirmDelete).toBeTruthy()
    // delete notebook - actual
    wrapper.vm.onDeleteNotebook()
    expect(mockTimeout).toHaveBeenNthCalledWith(2, 5000)
    expect(mockEmitWithAck).toHaveBeenNthCalledWith(2, 'notebooks:remove_notebook', 'uuid1')
  })
})
