import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'
import { createApp, nextTick } from 'vue'

import TypewriterEffect from '@/components/TypewriterEffect.vue'

import { readGlobalCss } from './readGlobalCss'

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
  // lookbehind 排除选择器子串误匹配（如 selector='body' 误匹配 '.n-spin-body'）
  const block = source.match(new RegExp(`(?<![\\w-])${selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*\\{([\\s\\S]*?)\\}`))
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
    // 阶段路由分区（含 stage.label aria-label）已抽离到 RoutingStagesPanel.vue（Slice 9）
    const stagesPanel = readSource('src/components/llm-settings/RoutingStagesPanel.vue')
    // 模型拉取弹窗（含各能力 aria-label）已抽离到 ModelPickerDialog.vue（Slice 12）
    const modelPicker = readSource('src/components/llm-settings/ModelPickerDialog.vue')

    expect(stagesPanel).toContain(':aria-label="`${stage.label} 模型路由`"')
    expect(modelPicker).toContain(':aria-label="`启用文本生成模型 ${modelName}`"')
    expect(modelPicker).toContain(':aria-label="`选择向量模型 ${modelName}`"')
    expect(modelPicker).not.toContain('aria-label="启用文本生成模型"')
    expect(modelPicker).not.toContain('aria-label="选择向量模型"')
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
      'src/assets/blueprint.css',
      'src/components/writing-desk/WDGenerateOutlineModal.vue',
      'src/components/writing-desk/workspace/ChapterGenerating.vue',
      'src/components/shared/MofengTable.vue',
      'src/components/shared/NovelDetailShell.vue',
      'src/components/admin/UserManagement.vue',
      'src/components/novel-detail/OverviewSection.vue',
      'src/components/novel-detail/ChaptersSection.vue',
      'src/components/novel-detail/CharactersSection.vue',
      'src/components/novel-detail/ForeshadowingSection.vue',
      'src/components/writing-desk/workspace/ChapterContent.vue',
    ]

    for (const path of auditedPaths) {
      const source = readSource(path)
      expect(source, path).not.toContain('transition-all')
      expect(source, path).not.toMatch(/transition:\s*all\b/)
    }
    // main.css 已按域拆分，审计断言改读入口 + partial 并集，避免读残壳假绿
    const globalCss = readGlobalCss()
    expect(globalCss).not.toContain('transition-all')
    expect(globalCss).not.toMatch(/transition:\s*all\b/)
  })

  it('keeps blueprint archive surfaces free of banned visual anti-patterns', () => {
    const auditedPaths = [
      'src/assets/blueprint.css',
      'src/components/shared/NovelDetailShell.vue',
      'src/components/novel-detail/OverviewSection.vue',
      'src/components/novel-detail/WorldSettingSection.vue',
      'src/components/novel-detail/CharactersSection.vue',
      'src/components/novel-detail/RelationshipsSection.vue',
      'src/components/novel-detail/ChapterOutlineSection.vue',
      'src/components/novel-detail/ChaptersSection.vue',
      'src/components/novel-detail/EmotionCurveSection.vue',
      'src/components/novel-detail/ForeshadowingSection.vue',
      'src/components/writing-desk/WDAssistantPanel.vue',
    ]

    for (const path of auditedPaths) {
      const source = readSource(path)
      expect(source, path).not.toContain('background-clip: text')
      expect(source, path).not.toContain('backdrop-filter')
      expect(source, path).not.toMatch(/border-(left|right):\s*(?:[2-9]|[1-9][0-9])px/)
    }
    const globalCss = readGlobalCss()
    expect(globalCss).not.toContain('background-clip: text')
    expect(globalCss).not.toContain('backdrop-filter')
    expect(globalCss).not.toMatch(/border-(left|right):\s*(?:[2-9]|[1-9][0-9])px/)
  })

  it('keeps shared pagination controls touch-safe', () => {
    const source = readSource('src/components/shared/MofengTable.vue')
    const paginationItemBlock = readCssBlock(source, ':deep(.n-pagination-item)')

    expect(paginationItemBlock).toContain('height: 44px')
    expect(paginationItemBlock).toContain('min-width: 44px')
    expect(paginationItemBlock).not.toContain('height: 28px')
    expect(paginationItemBlock).not.toContain('min-width: 28px')
  })

  it('keeps shared modal styling centralized and tokenized', () => {
    const modalSource = readSource('src/components/shared/GlobalModalContainer.vue')
    const globalCss = readGlobalCss()

    expect(modalSource).not.toMatch(/#[0-9a-fA-F]{3,8}\b/)
    expect(modalSource).not.toMatch(/rgba?\(/)
    expect(globalCss).not.toMatch(/\[data-theme='dark'\]\s+\.m3-ink-modal/)
  })

  it('keeps high-frequency loading motion off blur filters', () => {
    const auditedMotionPaths = [
      'src/views/InspirationMode.vue',
      'src/components/ConversationInput.vue',
      'src/components/writing-desk/workspace/ChapterGenerating.vue',
    ]

    for (const path of auditedMotionPaths) {
      const source = readSource(path)
      expect(source, path).not.toMatch(/filter:\s*blur/)
      expect(source, path).not.toMatch(/transition:\s*(?:[^;{}]|\n)*\bfilter\b(?:[^;{}]|\n)*;/)
    }
  })

  it('keeps high-frequency loading motion on transform and opacity only', () => {
    const auditedMotionPaths = [
      'src/views/InspirationMode.vue',
      'src/components/ConversationInput.vue',
      'src/components/writing-desk/workspace/ChapterGenerating.vue',
    ]

    for (const path of auditedMotionPaths) {
      const source = readSource(path)
      expect(source, path).not.toMatch(/@keyframes[\s\S]*?box-shadow\s*:/)
      expect(source, path).not.toMatch(/animation:\s*[^;]*(?:pulse|bloom)[^;]*infinite/)
    }
  })

  it('keeps app shell project dropdown controls semantic and touch-safe', () => {
    const source = readSource('src/components/shared/AppShell.vue')
    const css = readGlobalCss()
    const capsuleBlock = readCssBlock(css, '.app-shell__project-capsule')
    const dropdownItemBlock = readCssBlock(css, '.app-shell__dropdown-item')
    const dropdownActionBlock = readCssBlock(css, '.app-shell__dropdown-action')

    expect(source).toContain('<button')
    expect(source).toContain('type="button"')
    expect(source).toContain(':aria-expanded="isDropdownOpen"')
    expect(source).toContain('aria-controls="app-shell-project-menu"')
    expect(source).not.toContain('class="app-shell__dropdown-action" @click')
    expect(source).not.toContain('@click="isDropdownOpen = !isDropdownOpen"')
    expect(capsuleBlock).toContain('min-height: 44px')
    expect(dropdownItemBlock).toContain('min-height: 44px')
    expect(dropdownActionBlock).toContain('min-height: 44px')
  })

  it('keeps app shell decorative data urls out of the main css budget path', () => {
    const css = readGlobalCss()

    expect(css).not.toMatch(/\.app-shell__dropdown-item:hover\s*\{[^}]*?data:image/)
    expect(css).not.toMatch(/\.app-shell__project-welcome-message\s*\{[^}]*?data:image/)
  })

  it('keeps failed chapter recovery focused on the real retry action', () => {
    const source = readSource('src/components/writing-desk/workspace/ChapterFailed.vue')
    const buttonCount = source.match(/<button\b/g)?.length ?? 0

    expect(buttonCount).toBe(1)
    expect(source).toContain('@click="$emit(\'generateChapter\', chapterNumber)"')
    expect(source).toContain('重试生成本章')
    expect(source).not.toContain('换用备用模型')
    expect(source).not.toContain('缩短上下文后重试')
    expect(source).not.toContain('保存已生成片段')
    expect(source).not.toContain('保存片段')
  })

  it('uses real chapter generation traces before static node inspector fallback', () => {
    const apiSource = readSource('src/api/novel.ts')
    const generatingSource = readSource(
      'src/components/writing-desk/workspace/ChapterGenerating.vue',
    )
    // activeTrace/activeStepDetails 组装随 Slice 8 抽至 useChapterGenerationTrace，断言改读 composable 源码
    const traceSource = readSource('src/composables/useChapterGenerationTrace.ts')
    // currentComponentProps 装配随 composable 抽至 useChapterBodyProps，断言改读 composable 源码
    const bodyPropsSource = readSource('src/composables/useChapterBodyProps.ts')

    expect(apiSource).toContain('export interface ChapterGenerationTrace')
    expect(apiSource).toContain('generation_traces?: ChapterGenerationTrace[]')
    expect(apiSource).toContain('uses_llm: boolean')
    expect(bodyPropsSource).toContain('generationTraces: renderAsLocalGenerating')
    expect(bodyPropsSource).toContain('selectedChapter.value?.generation_traces ?? []')
    expect(generatingSource).toContain('generationTraces?: ChapterGenerationTrace[]')
    expect(traceSource).toContain('const activeTrace = computed')
    // traceMetadata 随 Slice 1 抽至 utils，composable import 后在 activeStepDetails 内调用
    expect(traceSource).toContain('traceMetadata')
  })

  it('does not show fabricated prompt or response content when a trace is missing', () => {
    // activeStepDetails 兜底文案随 Slice 8 抽至 useChapterGenerationTrace，断言改读 composable 源码
    const traceSource = readSource('src/composables/useChapterGenerationTrace.ts')

    expect(traceSource).toContain('该节点暂未收到真实运行记录。')
    expect(traceSource).not.toContain('姜沉河')
    expect(traceSource).not.toContain('AI导演剧情蓝图')
    expect(traceSource).not.toContain('商业擂台直播')
    expect(traceSource).not.toContain('主角“林拓”')
  })

  it('labels chapter trace details by action instead of pretending every node is an LLM call', () => {
    // 节点详情面板随 Slice 7 抽至 ChapterStepInspector.vue，展示文本随之迁移
    const inspectorSource = readSource(
      'src/components/writing-desk/workspace/ChapterStepInspector.vue',
    )
    // trace 格式化函数随 Slice 1 抽至 utils/generationTrace.ts，契约分两处校验
    const traceUtils = readSource('src/utils/generationTrace.ts')
    // activeStepDetails 组装随 Slice 8 抽至 useChapterGenerationTrace，traceUsesLlm/formatTraceActions 引用随之迁移
    const traceSource = readSource('src/composables/useChapterGenerationTrace.ts')

    expect(inspectorSource).toContain('输入材料')
    expect(inspectorSource).toContain('实际动作')
    expect(inspectorSource).toContain('产出结果')
    expect(inspectorSource).toContain('调用类型')
    expect(inspectorSource).toContain('LLM 调用：{{ activeStepDetails.llmUsage }}')
    expect(traceSource).toContain('traceUsesLlm')
    expect(traceSource).toContain('formatTraceActions')
    expect(traceUtils).toContain('formatModelCall')
    expect(inspectorSource).not.toContain('发送给 LLM 的输入 (Prompt)')
    expect(inspectorSource).not.toContain('LLM 生成的响应 (Response)')
    expect(inspectorSource).not.toContain('【系统 Prompt / 节点输入】')
  })

  it('keeps the overview blueprint page aligned with the shared archive vocabulary', () => {
    const overviewSource = readSource('src/components/novel-detail/OverviewSection.vue')
    // content-surface 的 classical 装订框已抽到 ShellContent 子组件
    const contentSource = readSource('src/components/novel-detail/ShellContent.vue')

    expect(overviewSource).toContain('archive-overview__summary-aside')
    expect(overviewSource).toContain('aria-label="蓝图资料状态"')
    expect(overviewSource).toContain('role="meter"')
    expect(overviewSource).toContain('archive-overview__readiness-card')
    expect(contentSource).toContain('detail-shell__content-surface--classical')
    expect(contentSource).not.toContain('detail-shell__content-surface--flat')
  })

  it('keeps the mobile chapter drawer out of the focus order when closed', () => {
    const source = readSource('src/components/novel-detail/ChaptersSection.vue')

    expect(source).toContain('<h2 class="sr-only">章节内容</h2>')
    expect(source).toContain(':aria-hidden="isChapterSidebarVisible ? undefined : \'true\'"')
    expect(source).toContain(':inert="!isChapterSidebarVisible"')
    expect(source).toContain(
      'const isChapterSidebarVisible = computed(() => isDesktopViewport.value || showChapterList.value)',
    )
    expect(source).toContain('aria-hidden="true"')
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
    const source = readGlobalCss()
    const darkPrimaryText = readCssCustomProperty(source, ":root[data-theme='dark']", '--md-primary')
    const darkBackground = readCssCustomProperty(source, ":root[data-theme='dark']", '--md-background')

    expect(contrastRatio(darkPrimaryText, darkBackground)).toBeGreaterThanOrEqual(4.5)
  })

  it('keeps dark vermilion text token contrast at WCAG AA level', () => {
    const source = readGlobalCss()
    const darkSecondaryText = readCssCustomProperty(source, ":root[data-theme='dark']", '--md-secondary-readable')
    const darkSurface = readCssCustomProperty(source, ":root[data-theme='dark']", '--md-surface')
    const darkBackground = readCssCustomProperty(source, ":root[data-theme='dark']", '--md-background')
    const loginSource = readSource('src/views/Login.vue')

    expect(contrastRatio(darkSecondaryText, darkSurface)).toBeGreaterThanOrEqual(4.5)
    expect(contrastRatio(darkSecondaryText, darkBackground)).toBeGreaterThanOrEqual(4.5)
    expect(loginSource).toContain('color: var(--md-secondary-readable)')
  })

  it('keeps typography roles centralized in design tokens', () => {
    const css = readGlobalCss()
    const mainSource = readSource('src/main.ts')
    const bodyBlock = readCssBlock(css, 'body')

    expect(readLightThemeCustomProperty(css, '--md-font-serif')).toContain("'Noto Serif SC'")
    expect(readLightThemeCustomProperty(css, '--md-font-sans')).toBe('var(--md-font-serif)')
    expect(readLightThemeCustomProperty(css, '--md-font-kai')).toBe('var(--md-font-serif)')
    expect(readLightThemeCustomProperty(css, '--md-font-family')).toBe('var(--md-font-serif)')
    expect(readLightThemeCustomProperty(css, '--md-font-display')).toBe('var(--md-font-serif)')
    expect(readLightThemeCustomProperty(css, '--md-font-label')).toBe('var(--md-font-serif)')
    expect(readLightThemeCustomProperty(css, '--md-font-mono')).toBe('var(--md-font-serif)')
    expect(bodyBlock).toContain('font-family: var(--md-font-family)')
    expect(css).not.toContain('var(--md-font-serif,')
    expect(css).not.toContain('var(--md-font-label,')
    expect(css).not.toContain('Noto Sans SC')
    expect(css).not.toContain('SentyGoldRogue')
    expect(mainSource).not.toContain('@fontsource/noto-sans-sc')
    expect(mainSource).toContain("@fontsource/noto-serif-sc/chinese-simplified-400.css")
    expect(mainSource).toContain("@fontsource/noto-serif-sc/chinese-simplified-600.css")
    expect(mainSource).not.toContain("@fontsource/noto-serif-sc/chinese-simplified-500.css")
    expect(mainSource).not.toContain("@fontsource/noto-serif-sc/chinese-simplified-700.css")
  })

  it('uses accessible semantic text tokens for light theme status copy', () => {
    const css = readGlobalCss()
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

  it('keeps version cards free of nested detail buttons inside radios', () => {
    const source = readSource('src/components/writing-desk/workspace/VersionSelector.vue')

    expect(source).toContain('role="radiogroup"')
    expect(source).toContain('role="radio"')
    expect(source).not.toContain('version-card__details-action')
    expect(source).not.toContain('version-card__actions')
  })

  it('announces version banners with live region semantics', () => {
    const source = readSource('src/components/writing-desk/workspace/VersionSelector.vue')

    expect(source).toContain('version-ready')
    expect(source).toContain('role="status"')
    expect(source).toContain('aria-live="polite"')
    expect(source).toContain('aria-atomic="true"')
    expect(source).toContain('version-notice')
    expect(source).toContain(':role="versionNotice.tone === \'error\' ? \'alert\' : \'status\'"')
    expect(source).toContain(':aria-live="versionNotice.tone === \'error\' ? \'assertive\' : \'polite\'"')
  })

  it('exposes project card progress as an accessible progressbar', () => {
    const source = readSource('src/components/ProjectCard.vue')

    expect(source).toContain('role="progressbar"')
    expect(source).toContain('aria-label="项目完成进度"')
    expect(source).toContain(':aria-valuenow="progress"')
    expect(source).toContain('const rawProgress = computed')
    expect(source).toContain('const progress = computed(() => Math.max(0, Math.min(100, rawProgress.value)))')
  })

  it('keeps workspace loading states announced and visually stable', () => {
    const source = readSource('src/views/NovelWorkspace.vue')

    expect(source).toContain(':aria-busy="projectsLoading"')
    expect(source).not.toContain('class="app-page workspace-page" :aria-busy="projectsLoading"')
    expect(source).toContain('role="status"')
    expect(source).toContain('aria-live="polite"')
    expect(source).toContain('workspace-hero--loading')
    expect(source).toContain('workspace-hero__loading-line')
  })

  it('announces blueprint generation progress to assistive technology', () => {
    const source = readSource('src/components/BlueprintConfirmation.vue')

    expect(source).toContain('role="status"')
    expect(source).toContain('aria-live="polite"')
    expect(source).toContain('role="progressbar"')
    expect(source).toContain(':aria-valuenow="Math.round(progress)"')
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
