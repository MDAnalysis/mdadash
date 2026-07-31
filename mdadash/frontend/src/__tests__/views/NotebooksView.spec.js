import { nextTick, ref } from 'vue'
import { mount } from '@vue/test-utils'
import { beforeEach, expect, describe, it, vi } from 'vitest'
import NotebooksView from '@/views/NotebooksView.vue'
import { VBtn, VListItem } from 'vuetify/components'
import { mdiDotsVertical } from '@mdi/js'

const settings = ref({
  dashboard_config: {
    ui_request_timeout: 5,
  },
})

const mockPush = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
  useRoute: () => ({
    query: { uuid: 'uuid1' },
  }),
}))

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

const notebooks = [
  {
    uuid: 'uuid1',
    name: 'name1',
    description: 'desc1',
    run_on_launch: true,
  },
  {
    uuid: 'uuid2',
    name: 'name2',
    description: 'desc2',
    run_on_launch: false,
  },
]

describe('NotebooksView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('check mount', async () => {
    const wrapper = mount(NotebooksView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper).toBeDefined()
  })

  it('loads details', async () => {
    mockEmitWithAck.mockResolvedValueOnce(notebooks)
    const wrapper = mount(NotebooksView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.exists()).toBe(true)
    expect(mockTimeout).toHaveBeenNthCalledWith(1, 5000)
    expect(mockEmitWithAck).toHaveBeenNthCalledWith(1, 'notebooks:get_notebooks')
  })

  it('search', async () => {
    const wrapper = mount(NotebooksView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.exists()).toBe(true)
    wrapper.vm.notebooks = notebooks
    await nextTick()
    const search = wrapper.find('#search')
    search.setValue('name1')
    expect(wrapper.vm.filteredNotebooks.length).toStrictEqual(1)
  })

  it('pagination', async () => {
    const wrapper = mount(NotebooksView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.exists()).toBe(true)
    wrapper.vm.notebooks = notebooks
    await nextTick()
    // check no page change possible
    wrapper.vm.page = 2
    await nextTick()
    expect(wrapper.vm.page).toStrictEqual(1)
    // check items per page
    let components = wrapper.findAllComponents({ name: 'VSelect' })
    const itemsPerPage = components[0]
    itemsPerPage.setValue(20)
    expect(wrapper.vm.itemsPerPage).toStrictEqual(20)
  })

  it('add notebook', async () => {
    const wrapper = mount(NotebooksView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.exists()).toBe(true)
    mockEmitWithAck.mockResolvedValueOnce('uuid3')
    wrapper.vm.addNotebook()
    expect(mockTimeout).toHaveBeenNthCalledWith(2, 5000)
    expect(mockEmitWithAck).toHaveBeenNthCalledWith(2, 'notebooks:add_notebook')
  })

  it('notebook actions', async () => {
    const wrapper = mount(NotebooksView, {
      global: {
        provide: allProvides,
      },
    })
    expect(wrapper.exists()).toBe(true)
    wrapper.vm.notebooks = notebooks
    await nextTick()
    // check actions button
    const moreItemsBtn = wrapper.findAllComponents(VBtn).find((btn) => {
      return btn.html().includes(mdiDotsVertical)
    })
    expect(moreItemsBtn).toBeDefined()
    await moreItemsBtn.trigger('click')
    await nextTick()
    // click on first notebook
    const items = wrapper.findAllComponents(VListItem)
    const firstNotebook = items[0]
    firstNotebook.trigger('click')
    expect(mockPush).toHaveBeenNthCalledWith(1, { path: '/notebook', query: { uuid: 'uuid1' } })
    const menuItems = firstNotebook.findAllComponents(VListItem)
    // edit
    menuItems[0].trigger('click')
    expect(mockPush).toHaveBeenNthCalledWith(2, { path: '/notebook', query: { uuid: 'uuid1' } })
    // duplicate
    mockEmitWithAck.mockResolvedValueOnce('uuid3')
    menuItems[1].trigger('click')
    expect(mockTimeout).toHaveBeenNthCalledWith(2, 5000)
    expect(mockEmitWithAck).toHaveBeenNthCalledWith(2, 'notebooks:duplicate_notebook', 'uuid1')
    await nextTick()
    expect(mockPush).toHaveBeenNthCalledWith(3, { path: '/notebook', query: { uuid: 'uuid3' } })
    // delete - confirm
    menuItems[2].trigger('click')
    // delete - actual
    menuItems[2].trigger('click')
    expect(wrapper.vm.notebooks.length).toStrictEqual(1)
  })
})
