import { afterEach, vi } from 'vitest'

const originalMatchMedia = window.matchMedia
const originalLocalStorage = window.localStorage
const matchMediaStub = (query: string) =>
  ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }) as MediaQueryList

if (typeof window.matchMedia !== 'function') {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: matchMediaStub,
  })
}

const createStorageStub = (): Storage => {
  const store = new Map<string, string>()
  return {
    get length() {
      return store.size
    },
    clear: vi.fn(() => store.clear()),
    getItem: vi.fn((key: string) => store.get(key) ?? null),
    key: vi.fn((index: number) => Array.from(store.keys())[index] ?? null),
    removeItem: vi.fn((key: string) => {
      store.delete(key)
    }),
    setItem: vi.fn((key: string, value: string) => {
      store.set(key, String(value))
    }),
  }
}

if (typeof window.localStorage?.getItem !== 'function') {
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    writable: true,
    value: createStorageStub(),
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
  } else {
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      writable: true,
      value: matchMediaStub,
    })
  }

  if (typeof originalLocalStorage?.getItem === 'function') {
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      writable: true,
      value: originalLocalStorage,
    })
  } else {
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      writable: true,
      value: createStorageStub(),
    })
  }
})
