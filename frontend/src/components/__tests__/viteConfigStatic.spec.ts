import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

const readSource = (relativePath: string) =>
  readFileSync(resolve(process.cwd(), relativePath), 'utf8')

describe('vite config startup contracts', () => {
  it('loads Vue DevTools only after the Node localStorage shim is installed', () => {
    const source = readSource('vite.config.ts')

    expect(source).not.toMatch(/^import\s+vueDevTools\s+from\s+['"]vite-plugin-vue-devtools['"]/m)
    expect(source).toContain("await import('vite-plugin-vue-devtools')")
    expect(source.indexOf('globalThis.localStorage')).toBeLessThan(
      source.indexOf("await import('vite-plugin-vue-devtools')"),
    )
  })
})
