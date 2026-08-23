import { describe, expect, it } from 'vitest'

import { readGlobalCss } from './readGlobalCss'

describe('readGlobalCss', () => {
  it('inlines relative @import partials and keeps non-relative imports', () => {
    const css = readGlobalCss()

    // 非相对 @import（tailwindcss）不内联，保留原文交由 Tailwind/Lightning CSS 处理
    expect(css).toContain("@import 'tailwindcss'")
    // 相对 @import 的 partial 内容已内联（token 来自 tokens.css）
    expect(css).toContain('--md-primary')
    expect(css).toContain(":root[data-theme='light']")
    expect(css).not.toContain(":root[data-theme='dark']")
    // 所有相对 @import（./ 或 ../）均已内联，源码中不应残留未解析的入口
    expect(css).not.toMatch(/@import\s+['"]\.\.?\//)
  })
})
