import { config } from '@vue/test-utils'
import { createVuetify } from 'vuetify'
import { vi } from 'vitest'

globalThis.ResizeObserver =
  globalThis.ResizeObserver ||
  class {
    constructor(_callback) {}
    observe() {}
    unobserve() {}
    disconnect() {}
  }

vi.stubGlobal('visualViewport', {
  offsetLeft: 0,
  offsetTop: 0,
  pageLeft: 0,
  pageTop: 0,
  width: 1024,
  height: 768,
  scale: 1,
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  dispatchEvent: vi.fn(),
})

config.global.plugins.push(createVuetify())
