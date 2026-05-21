import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'
import { createApp, nextTick } from 'vue'

import TypewriterEffect from '@/components/TypewriterEffect.vue'

const readSource = (relativePath: string) =>
  readFileSync(resolve(process.cwd(), relativePath), 'utf8')

const readJson = <T>(relativePath: string): T =>
  JSON.parse(readSource(relativePath)) as T

const readCssCustomProperty = (source: string, selector: string, property: string) => {
  const block = source.match(new RegExp(`${selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*\\{([\\s\\S]*?)\\}`))
  const value = block?.[1].match(new RegExp(`${property}\\s*:\\s*([^;]+);`))?.[1]?.trim()
  if (!value) {
    throw new Error(`Missing ${property} in ${selector}`)
  }
  return value
}

const readLightThemeCustomProperty = (source: string, property: string) => {
  const block = source.match(/:root,\s*:root\[data-theme='light'\]\s*\{([\s\S]*?)\}/)
  const value = block?.[1].match(new RegExp(`${property}\\s*:\\s*([^;]+);`))?.[1]?.trim()
  if (!value) {
    throw new Error(`Missing ${property} in light theme`)
  }
  return value
}

const readCssBlock = (source: string, selector: string) => {
  const block = source.match(new RegExp(`${selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*\\{([\\s\\S]*?)\\}`))
  if (!block) {
    throw new Error(`Missing ${selector} block`)
  }
  return block[1]
}

const parseHexColor = (value: string) => {
  const normalized = value.trim()
  const match = normalized.match(/^#([0-9a-fA-F]{6})$/)
  if (!match) {
    throw new Error(`Expected hex color, got ${value}`)
  }

  return [
    Number.parseInt(match[1].slice(0, 2), 16),
    Number.parseInt(match[1].slice(2, 4), 16),
    Number.parseInt(match[1].slice(4, 6), 16),
  ] as const
}

const relativeLuminance = ([red, green, blue]: readonly number[]) => {
  const channel = (value: number) => {
    const normalized = value / 255
    return normalized <= 0.03928
      ? normalized / 12.92
      : ((normalized + 0.055) / 1.055) ** 2.4
  }

  return 0.2126 * channel(red) + 0.7152 * channel(green) + 0.0722 * channel(blue)
}

const contrastRatio = (foreground: string, background: string) => {
  const foregroundLuminance = relativeLuminance(parseHexColor(foreground))
  const backgroundLuminance = relativeLuminance(parseHexColor(background))
  const lighter = Math.max(foregroundLuminance, backgroundLuminance)
  const darker = Math.min(foregroundLuminance, backgroundLuminance)
  return (lighter + 0.05) / (darker + 0.05)
}

describe('UI audit regressions', () => {
  it('gives model routing controls unique accessible names', () => {
    const source = readSource('src/components/llm-settings/PersonalModelRouting.vue')

    expect(source).toContain(':aria-label="`${stage.label} 模型路由`"')
    expect(source).toContain(':aria-label="`启用文本生成模型 ${modelName}`"')
    expect(source).toContain(':aria-label="`选择向量模型 ${modelName}`"')
    expect(source).not.toContain('aria-label="启用文本生成模型"')
    expect(source).not.toContain('aria-label="选择向量模型"')
  })

  it('labels fallback blueprint editing textarea', () => {
    const source = readSource('src/components/BlueprintEditModal.vue')

    expect(source).toContain(':aria-label="`编辑${title ? ` ${title}` : \'内容\'}`"')
  })

  it('keeps blueprint editor destructive controls at touch-safe size', () => {
    const editorPaths = [
      'src/components/ChapterOutlineEditor.vue',
      'src/components/RelationshipsEditor.vue',
      'src/components/FactionsEditor.vue',
      'src/components/KeyLocationsEditor.vue',
    ]

    for (const path of editorPaths) {
      const source = readSource(path)
      expect(source).toContain('blueprint-editor__delete-button')
    }
  })

  it('does not use transition-all in audited UI surfaces', () => {
    const auditedPaths = [
      'src/components/BlueprintEditModal.vue',
      'src/components/CustomAlert.vue',
      'src/components/writing-desk/WDGenerateOutlineModal.vue',
      'src/components/novel-detail/ChaptersSection.vue',
      'src/components/novel-detail/CharactersSection.vue',
      'src/components/novel-detail/ForeshadowingSection.vue',
      'src/components/writing-desk/workspace/ChapterContent.vue',
    ]

    for (const path of auditedPaths) {
      const source = readSource(path)
      expect(source, path).not.toContain('transition-all')
    }
  })

  it('keeps auth footer links touch-safe', () => {
    const loginSource = readSource('src/views/Login.vue')
    const registerSource = readSource('src/views/Register.vue')

    expect(loginSource).toContain('login-link__cta')
    expect(registerSource).toContain('register-link__cta')
    expect(loginSource).toContain('md-btn md-btn-text md-ripple')
    expect(registerSource).toContain('md-btn md-btn-text md-ripple')
  })

  it('avoids layout-property animation in character dna panels', () => {
    const source = readSource('src/components/CharactersEditorEnhanced.vue')

    expect(source).toContain('opacity 0.2s ease-out')
    expect(source).toContain('transform 0.2s ease-out')
    expect(source).not.toContain('max-height 0.3s ease')
  })

  it('keeps dark primary text token contrast at WCAG AA level', () => {
    const source = readSource('src/assets/main.css')
    const darkPrimaryText = readCssCustomProperty(source, ":root[data-theme='dark']", '--md-primary')
    const darkBackground = readCssCustomProperty(source, ":root[data-theme='dark']", '--md-background')

    expect(contrastRatio(darkPrimaryText, darkBackground)).toBeGreaterThanOrEqual(4.5)
  })

  it('uses accessible semantic text tokens for light theme status copy', () => {
    const css = readSource('src/assets/main.css')
    const lightSurface = readLightThemeCustomProperty(css, '--md-surface')
    const errorContainer = readLightThemeCustomProperty(css, '--md-error-container')
    const warningContainer = readLightThemeCustomProperty(css, '--md-warning-container')
    const successContainer = readLightThemeCustomProperty(css, '--md-success-container')
    const errorText = readLightThemeCustomProperty(css, '--md-error-text')
    const warningText = readLightThemeCustomProperty(css, '--md-warning-text')
    const successText = readLightThemeCustomProperty(css, '--md-success-text')

    expect(contrastRatio(errorText, lightSurface)).toBeGreaterThanOrEqual(4.5)
    expect(contrastRatio(errorText, errorContainer)).toBeGreaterThanOrEqual(4.5)
    expect(contrastRatio(warningText, lightSurface)).toBeGreaterThanOrEqual(4.5)
    expect(contrastRatio(warningText, warningContainer)).toBeGreaterThanOrEqual(4.5)
    expect(contrastRatio(successText, lightSurface)).toBeGreaterThanOrEqual(4.5)
    expect(contrastRatio(successText, successContainer)).toBeGreaterThanOrEqual(4.5)

    const chaptersSource = readSource('src/components/novel-detail/ChaptersSection.vue')
    const settingsSource = readSource('src/components/admin/SettingsManagement.vue')

    expect(chaptersSource).toContain('text-[var(--md-warning-text)]')
    expect(chaptersSource).toContain('text-[var(--md-error-text)]')
    expect(chaptersSource).toContain('text-[var(--md-success-text)]')
    const compareNewBlock = readCssBlock(settingsSource, '.compare-new')
    const compareSameBlock = readCssBlock(settingsSource, '.compare-same')
    const compareErrorBlock = readCssBlock(settingsSource, '.compare-error')

    expect(compareNewBlock).toContain('var(--md-warning-text)')
    expect(compareSameBlock).toContain('var(--md-success-text)')
    expect(compareErrorBlock).toContain('var(--md-error-text)')
    expect(chaptersSource).not.toContain('text-[var(--md-warning)]')
    expect(chaptersSource).not.toContain('text-[var(--md-error)]')
    expect(chaptersSource).not.toContain('text-[var(--md-success)]')
    expect(compareNewBlock).not.toContain('var(--md-warning);')
    expect(compareSameBlock).not.toContain('var(--md-success);')
    expect(compareErrorBlock).not.toContain('var(--md-error);')
  })

  it('uses the readable primary token for workspace eyebrow labels', () => {
    const source = readSource('src/views/NovelWorkspace.vue')
    const eyebrowBlock = source.match(/\.workspace-eyebrow\s*\{[\s\S]*?\}/)?.[0] ?? ''

    expect(eyebrowBlock).toContain('color: var(--md-primary);')
    expect(eyebrowBlock).not.toContain('color: var(--md-primary-dark);')
  })

  it('keeps project title buttons touch-safe', () => {
    const source = readSource('src/components/ProjectCard.vue')
    const titleButtonBlock = source.match(/\.project-card__title-button\s*\{[\s\S]*?\}/)?.[0] ?? ''

    expect(titleButtonBlock).toContain('min-height: 44px')
    expect(titleButtonBlock).toContain('padding:')
  })

  it('renders complete typewriter text immediately when reduced motion is preferred', async () => {
    window.matchMedia = ((query: string) =>
      ({
        matches: query.includes('prefers-reduced-motion'),
        media: query,
        onchange: null,
        addEventListener: () => {},
        removeEventListener: () => {},
        addListener: () => {},
        removeListener: () => {},
        dispatchEvent: () => false,
      }) as MediaQueryList) as typeof window.matchMedia

    const host = document.createElement('div')
    document.body.appendChild(host)
    const app = createApp(TypewriterEffect, { text: '墨风' })

    try {
      app.mount(host)
      await nextTick()

      expect(host.textContent?.trim()).toBe('墨风')
    } finally {
      app.unmount()
      host.remove()
    }
  })

  it('connects auth form errors to their fields', () => {
    const loginSource = readSource('src/views/Login.vue')
    const registerSource = readSource('src/views/Register.vue')

    expect(loginSource).toContain('id="login-error"')
    expect(loginSource).toContain(':aria-invalid="Boolean(error)"')
    expect(loginSource).toContain(':aria-describedby="error ? \'login-error\' : undefined"')

    expect(registerSource).toContain('id="register-error"')
    expect(registerSource).toContain(':aria-invalid="Boolean(error)"')
    expect(registerSource).toContain(':aria-describedby="error ? \'register-error\' : undefined"')
  })

  it('keeps bundle budget below the warning threshold', () => {
    const packageJson = readJson<{ scripts: Record<string, string> }>('package.json')

    expect(packageJson.scripts['build:budget']).toContain('BUNDLE_BUDGET_WARN_JS_TOTAL_GZIP_KB=430')
  })

  it('keeps emotion curve rendering off the Chart.js runtime path', () => {
    const source = readSource('src/components/novel-detail/EmotionCurveSection.vue')

    expect(source).not.toContain("import('@/lib/chartLine')")
    expect(source).not.toContain('chartCanvas')
    expect(source).toContain('emotion-curve-svg')
  })
})
