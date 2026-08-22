import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

const readSource = (relativePath: string) =>
  readFileSync(resolve(process.cwd(), relativePath), 'utf8')

describe('NovelDetailShell heading semantics', () => {
  it('uses a single semantic page title level and preserves detail shell structure', () => {
    const source = readSource('src/components/shared/NovelDetailShell.vue')

    expect(source).toContain('<ShellTopbar')
    expect(source.replace(/\s+/g, ' ')).toContain('<ShellTopbar :title="formattedTitle"')
    // topbar 的标题 h1 + 返回/写作台按钮已抽到 ShellTopbar 子组件（{{ title }} 由父 :title="formattedTitle" 传入）
    const topbarSource = readSource('src/components/novel-detail/ShellTopbar.vue')
    const normalizedTopbarSource = topbarSource.replace(/\s+/g, ' ')
    expect(normalizedTopbarSource).toContain(
      '<h1 class="detail-shell__title md-title-large truncate" style="color: var(--md-on-surface)"',
    )
    expect(topbarSource).toContain('{{ title }}')
    expect(topbarSource).toContain('detail-shell__back-button')
    expect(topbarSource).toContain('detail-shell__write-button')
    expect(topbarSource).toContain('detail-shell__write-label-full')
    expect(topbarSource).toContain('detail-shell__write-label-compact')
    expect(topbarSource.match(/<h1\b/g)).toHaveLength(1)
    // overview-strip 的标题 h2 已抽到 OverviewStrip 子组件（{{ title }} 由父 :title="formattedTitle" 传入）
    const overviewStripSource = readSource('src/components/novel-detail/OverviewStrip.vue')
    expect(overviewStripSource).toContain('<h2>{{ title }}</h2>')
  })

  it('keeps detail sections addressable and admin project data real', () => {
    const shellSource = readSource('src/components/shared/NovelDetailShell.vue')
    const navigationSource = readSource('src/composables/useShellSectionNavigation.ts')
    const adminQuerySource = readSource('src/queries/admin.ts')

    expect(navigationSource).toContain("{ key: 'chapters', label: '章节正文' }")
    expect(navigationSource).toContain('void router.push({ query: { ...route.query, section } })')
    expect(navigationSource).toContain('() => route.query.section')
    expect(adminQuerySource).toContain('export function useAdminNovelDetailQuery')
    expect(shellSource).toContain('useAdminNovelDetailQuery')
    expect(shellSource).toContain('adminProjectQuery.data.value')
  })
})
