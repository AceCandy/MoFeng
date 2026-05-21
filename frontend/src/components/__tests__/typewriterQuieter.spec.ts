import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'
import { createApp, nextTick } from 'vue'

import TypewriterEffect from '@/components/TypewriterEffect.vue'

const readSource = (relativePath: string) =>
  readFileSync(resolve(process.cwd(), relativePath), 'utf8')

describe('TypewriterEffect quieter regression', () => {
  it('mounts and shows the full brand title immediately as an h1', async () => {
    const host = document.createElement('div')
    document.body.appendChild(host)
    const app = createApp(TypewriterEffect, { text: '墨风' })

    try {
      app.mount(host)
      await nextTick()

      const heading = host.querySelector('h1')

      expect(heading).not.toBeNull()
      expect(host.textContent?.trim()).toBe('墨风')
    } finally {
      app.unmount()
      host.remove()
    }
  })

  it('removes the typewriter timer and caret animation from source', () => {
    const source = readSource('src/components/TypewriterEffect.vue')

    expect(source).not.toContain('setInterval')
    expect(source).not.toContain('blink-caret')
    expect(source).not.toContain('border-right')
  })
})
