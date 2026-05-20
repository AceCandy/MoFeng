import { afterEach, vi } from 'vitest'

const originalMatchMedia = window.matchMedia

if (typeof window.matchMedia !== 'function') {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: (query: string) =>
      ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }) as MediaQueryList,
  })
}

afterEach(() => {
  vi.restoreAllMocks()

  if (typeof originalMatchMedia === 'function') {
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      writable: true,
      value: originalMatchMedia,
    })
    return
  }

  delete (window as Partial<Window>).matchMedia
})
