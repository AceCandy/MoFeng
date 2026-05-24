import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

const readSource = (relativePath: string) =>
  readFileSync(resolve(process.cwd(), relativePath), 'utf8')

describe('NovelDetailShell heading semantics', () => {
  it('uses a single semantic page title level and preserves detail shell structure', () => {
    const source = readSource('src/components/shared/NovelDetailShell.vue')
    const normalizedSource = source.replace(/\s+/g, ' ')

    expect(source).not.toContain('<h1')
    expect(normalizedSource).toContain(
      '<h2 class="detail-shell__title md-title-large truncate" style="color: var(--md-on-surface)"',
    )
    expect(source).toContain('{{ formattedTitle }}')
    expect(source).toContain('detail-shell__back-button')
    expect(source).toContain('detail-shell__write-button')
    expect(source).toContain('detail-shell__write-label-full')
    expect(source).toContain('detail-shell__write-label-compact')
    expect(source).toContain('<h2>{{ formattedTitle }}</h2>')
  })
})
