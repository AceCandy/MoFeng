import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

import { readGlobalCss } from './readGlobalCss'

const readSource = (relativePath: string) =>
  readFileSync(resolve(process.cwd(), relativePath), 'utf8')

const readJson = <T>(relativePath: string): T =>
  JSON.parse(readSource(relativePath)) as T

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
    const modelPicker = readSource('src/components/llm-settings/ModelPickerPanel.vue')

    expect(stagesPanel).toContain(':aria-label="`${stage.label} 模型路由`"')
    expect(stagesPanel).toContain(':aria-label="`${node.label} 模型路由`"')
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

  it('locks the app to the single warm-paper theme', () => {
    const indexSource = readSource('index.html')
    const runtimeSource = `${readSource('src/main.ts')}\n${readSource('src/components/shared/AppShell.vue')}`
    const globalCss = readGlobalCss()

    expect(indexSource).toMatch(/<html[^>]*data-theme="light"/)
    expect(runtimeSource).not.toMatch(/mofeng-theme-preference|prefers-color-scheme|theme-changed|matchMedia\(|dataset\.theme/)
    expect(globalCss).toContain('color-scheme: light')
    expect(globalCss).not.toContain('--md-night-')
    expect(globalCss).not.toMatch(/\[data-theme\s*=\s*['"]dark['"]\]/)
    expect(globalCss).not.toMatch(/\.dark(?:\s|[),>{:.#\[])/)
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
    expect(source).toContain(":aria-controls=\"isDropdownOpen ? 'app-shell-project-menu' : undefined\"")
    expect(source).not.toContain('class="app-shell__dropdown-action" @click')
    expect(source).not.toContain('@click="isDropdownOpen = !isDropdownOpen"')
    expect(capsuleBlock).toContain('min-height: 44px')
    expect(dropdownItemBlock).toContain('min-height: 44px')
    expect(dropdownActionBlock).toContain('min-height: 44px')
  })

  it('keeps the account menu keyboard accessible', () => {
    const source = readSource('src/components/shared/AppShell.vue')

    expect(source).toContain('ref="userTagTriggerRef"')
    expect(source).toContain(':aria-expanded="isUserDropdownOpen"')
    expect(source).toContain('aria-controls="app-shell-user-menu"')
    expect(source).toContain('@keydown.esc.stop.prevent="closeUserDropdown(true)"')
    expect(source).toContain('id="app-shell-user-menu"')
    expect(source).toContain('<span class="item-title">AI 设置</span>')
    expect(source).toContain('<span class="item-title">账户与安全</span>')
    expect(source).toContain('<span class="item-title">管理后台</span>')
    expect(source).not.toContain('<span class="item-title">提示词用量</span>')
    expect(source.indexOf('app-shell__user-dropdown-divider')).toBeLessThan(source.indexOf('账户与安全'))
    expect(source.indexOf('账户与安全')).toBeLessThan(source.indexOf('退出登录'))
    expect(source).not.toContain('showSettingsModal')
    expect(source).not.toContain('<SettingsView')
    expect(source).not.toContain('href="javascript:void(0)"')
    expect(source).not.toContain('role="button"')
  })

  it('keeps primary routes and inspiration stages semantically identified', () => {
    const routerSource = readSource('src/router/index.ts')
    const workspaceSource = readSource('src/views/NovelWorkspace.vue')
    const inspirationSource = readSource('src/views/InspirationMode.vue')
    const confirmationSource = readSource('src/components/BlueprintConfirmation.vue')
    const settingsSource = readSource('src/views/SettingsView.vue')
    const writingChapterMetaSource = readSource(
      'src/components/writing-desk/workspace/ChapterMeta.vue',
    )

    expect(workspaceSource).toContain('<h1>{{ continueProject')
    expect(inspirationSource).toContain('<h1 class="md-label-large inspiration-chat__title">')
    expect(confirmationSource).toContain('<h1 class="blueprint-confirm__title">')
    expect(settingsSource).toContain('<h1>AI 设置</h1>')
    expect(writingChapterMetaSource).toContain(
      '<h1 class="md-title-large font-semibold writing-workspace__chapter-no">',
    )
    expect(routerSource).toContain("meta: { layout: 'auth', label: '登录' }")
    expect(routerSource).toContain("meta: { layout: 'auth', label: '注册' }")
    expect(routerSource).toContain('router.afterEach((to) => {')
    expect(routerSource).toContain("document.title = to.meta.label ? `${to.meta.label} · 墨风` : '墨风'")
  })

  it('keeps retired seal language out of audited surfaces', () => {
    const loginSource = readSource('src/views/Login.vue')
    const workspaceSource = readSource('src/views/NovelWorkspace.vue')
    const sidebarSource = readSource('src/components/writing-desk/WDSidebar.vue')
    const overviewSource = readSource('src/components/novel-detail/OverviewSection.vue')

    expect(loginSource).not.toContain('<span aria-hidden="true">印</span>')
    expect(workspaceSource).toContain('<span>项目进度</span>')
    expect(workspaceSource).not.toContain('workspace-hero__progress-seal')
    expect(sidebarSource).not.toContain('writing-sidebar__status-seal')
    expect(sidebarSource).not.toContain('ChapterSealState')
    expect(overviewSource).toContain("toneText: props.data?.one_sentence_summary ? '完成' : '待补'")
    expect(overviewSource).not.toMatch(/toneText: .*\? '成' : '待'/)
  })

  it('keeps app shell navigation branding and copy concise', () => {
    const source = readSource('src/components/shared/AppShell.vue')

    expect(source).toContain('<p class="app-shell__brand-title">墨風</p>')
    expect(source).not.toContain('app-shell__brand-mark')
    expect(source).not.toContain('AI 小说创作中控台')
    expect(source).toContain(": '选择书卷' }}")
    expect(source).toContain('笔底生墨，风动砚海。阁主，吾静待汝执笔。')
    expect(source).not.toContain('app-shell__task-label')
    expect(source).toContain('class="app-shell__task-icon"')
    expect(source).toContain('class="app-shell__task-count"')
    expect(source).toContain('class="app-shell__task-status-dot"')
    expect(source).not.toContain("return '!'")
    expect(source).toContain(':aria-label="taskButtonLabel"')
  })

  it('keeps task reminders scoped to running and unread terminal states', () => {
    const source = readSource('src/components/shared/AppShell.vue')

    expect(source).toContain("const taskReadStoragePrefix = 'mofeng-task-read:'")
    expect(source).toContain('authStore.user?.id')
    expect(source).toContain("task.status === 'running'")
    expect(source).toContain("task.status === 'succeeded' && !viewedCompletedTaskIds.value.has(task.id)")
    expect(source).toContain("task.status === 'failed' && !viewedCompletedTaskIds.value.has(task.id)")
    expect(source).toContain("if (unviewedFailedTasks.value.length > 0) return 'failed'")
    expect(source).toContain("if (!taskReadStorageKey.value) return null")
    expect(source).toContain("return '查看任务日志，有任务执行失败'")
    expect(source).toContain("return '查看任务日志，有任务执行完成'")
    expect(source).toContain('markCompletedTasksViewed()')
    expect(source).toContain('@click="handleTaskButtonClick"')
  })

  it('keeps app shell decorative data urls out of the main css budget path', () => {
    const css = readGlobalCss()

    expect(css).not.toMatch(/\.app-shell__dropdown-item:hover\s*\{[^}]*?data:image/)
    expect(css).not.toMatch(/\.app-shell__project-welcome-message\s*\{[^}]*?data:image/)
  })

  it('keeps failed chapter recovery constrained by server allowed commands', () => {
    const source = readSource('src/components/writing-desk/ChapterWorkflowPanel.vue')

    expect(source).toContain("props.allowedCommands.includes('retry')")
    expect(source).toContain("props.allowedCommands.includes('retry_external')")
    expect(source).toContain("props.allowedCommands.includes('retry_projection')")
    expect(source).toContain('确认风险并重试')
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
    const workspaceSource = readSource('src/components/writing-desk/WDWorkspace.vue')

    expect(apiSource).toContain(
      "export type ChapterGenerationTrace = components['schemas']['ChapterGenerationTrace']",
    )
    expect(apiSource).toContain("export type Chapter = components['schemas']['Chapter']")
    expect(workspaceSource).toContain('const traceReplayProps = computed')
    expect(workspaceSource).toContain('selectedChapter.value?.generation_traces ?? []')
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
    const stripSource = readSource('src/components/novel-detail/OverviewStrip.vue')

    expect(overviewSource).toContain('archive-overview__summary-aside')
    expect(overviewSource).toContain('aria-label="蓝图资料状态"')
    expect(overviewSource).toContain('role="meter"')
    expect(overviewSource).toContain('archive-overview__readiness-card')
    expect(overviewSource).toContain('synopsisParagraphs')
    expect(overviewSource).not.toContain(':aria-label="item.toneLabel"')
    expect(contentSource).toContain('tabindex="0"')
    expect(contentSource).toContain('detail-shell__content-surface--classical')
    expect(contentSource).not.toContain('detail-shell__content-surface--flat')
    expect(readCssBlock(stripSource, '.detail-shell__scroll-time')).not.toContain('opacity:')
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

  it('keeps writing desk drawers out of the accessibility tree when closed', () => {
    const source = readSource('src/views/WritingDesk.vue')

    expect(source).toContain(":aria-hidden=\"useSidebarDrawer && !isSidebarDrawerOpen ? 'true' : undefined\"")
    expect(source).toContain(':inert="useSidebarDrawer && !isSidebarDrawerOpen"')
    expect(source).toContain(':aria-expanded="isSidebarDrawerOpen"')
    expect(source).toContain('aria-controls="writing-desk-chapter-drawer"')
    expect(source).toContain(":aria-hidden=\"useAssistantDrawer && !isAssistantDrawerOpen ? 'true' : undefined\"")
    expect(source).toContain(':inert="useAssistantDrawer && !isAssistantDrawerOpen"')
    expect(source).toContain('aria-controls="writing-desk-assistant-panel"')
    expect(source).toContain('overflow-x: clip')
    expect(source).toContain('height: calc(var(--app-viewport-unit) - var(--app-topbar-height) - 88px)')
  })

  it('keeps the novel detail drawer dismissible and restores its trigger', () => {
    const drawerSource = readSource('src/components/novel-detail/ShellDrawerNav.vue')
    const shellSource = readSource('src/components/shared/NovelDetailShell.vue')

    expect(drawerSource).toContain('aria-label="关闭小说档案分区导航"')
    expect(drawerSource).toContain('<button')
    expect(shellSource).toContain("event.key !== 'Escape'")
    expect(shellSource).toContain('closeSidebar(true)')
    expect(shellSource).toContain('trigger.focus()')
  })

  it('protects unsaved model routes and prompts across navigation', () => {
    const settingsSource = readSource('src/views/SettingsView.vue')
    const promptSource = readSource('src/components/admin/PromptManagement.vue')
    const adminSource = readSource('src/views/AdminView.vue')

    expect(settingsSource).toContain('confirmDiscardChanges')
    expect(settingsSource).toContain('resolveSettingsSection(route.query.tab)')
    expect(settingsSource).toContain("router.push({ name: 'settings'")
    expect(settingsSource).toContain('onBeforeRouteLeave')
    expect(settingsSource).toContain("window.addEventListener('beforeunload', onBeforeUnload)")
    expect(promptSource).toContain('const isDirty = computed')
    expect(promptSource).toContain('isEditDirty.value || isCreateDirty.value')
    expect(promptSource).toContain('createForm.name.trim()')
    expect(promptSource).toContain('defineExpose({ isDirty, confirmDiscardChanges })')
    expect(promptSource).toContain('filteredPrompts')
    expect(promptSource).toContain("mobileView === 'editor'")
    expect(promptSource).toContain('aria-label="添加 Prompt 标签"')
    expect(adminSource).toContain('onBeforeRouteUpdate')
    expect(adminSource).toContain('onBeforeRouteLeave')
  })

  it('routes settings, account security, and prompt usage without business modals', () => {
    const routerSource = readSource('src/router/index.ts')
    const loginSource = readSource('src/views/Login.vue')
    const adminSource = readSource('src/views/AdminView.vue')
    const pickerSource = readSource('src/components/llm-settings/ModelPickerPanel.vue')

    expect(routerSource).toContain("path: '/account/security'")
    expect(routerSource).toContain("name: 'account-security'")
    expect(routerSource).toContain("to.name !== 'account-security'")
    expect(routerSource).toContain("return { name: 'account-security' }")
    expect(loginSource).toContain("router.push({ name: 'account-security' })")
    expect(adminSource).toContain("'prompt-usage': createAsyncSection")
    expect(adminSource).toContain("{ key: 'prompt-usage', label: '提示词用量'")
    expect(pickerSource).not.toContain('<Teleport')
    expect(pickerSource).not.toContain('role="dialog"')
    expect(pickerSource).toContain('class="model-routing__model-picker"')
  })

  it('confirms destructive account and inspiration actions before mutation', () => {
    const usersSource = readSource('src/components/admin/UserManagement.vue')
    const inspirationSource = readSource('src/views/InspirationMode.vue')
    const workspaceSource = readSource('src/views/NovelWorkspace.vue')

    expect(usersSource).toContain('await globalAlert.showConfirm')
    expect(usersSource).toContain("'aria-label': `${row.username} 账号状态")
    expect(inspirationSource).toContain('await deleteNovelsMutation.mutateAsync([projectId])')
    expect(inspirationSource).toContain("const projectId = currentProject.value?.id ?? activeProjectId.value")
    expect(workspaceSource).toContain(
      "if (isInspirationProject(project) || context?.surface === 'inspiration') return '继续灵感对话'",
    )
    expect(workspaceSource).toContain(
      "if (isInspirationProject(project) || context?.surface === 'inspiration') {",
    )
  })

  it('keeps auth footer links touch-safe', () => {
    const loginSource = readSource('src/views/Login.vue')
    const registerSource = readSource('src/views/Register.vue')

    expect(loginSource).toContain('login-link__cta')
    expect(registerSource).toContain('register-link__cta')
    expect(loginSource).toContain('md-btn md-btn-text md-ripple')
    expect(registerSource).toContain('md-btn md-btn-text md-ripple')
  })

  it('keeps auth pages to one main landmark and omits ineffective persistence controls', () => {
    const layoutSource = readSource('src/components/shared/AuthLayout.vue')
    const loginSource = readSource('src/views/Login.vue')
    const registerSource = readSource('src/views/Register.vue')

    expect(layoutSource).not.toContain('<main')
    expect(loginSource.match(/<main\b/g)).toHaveLength(1)
    expect(registerSource.match(/<main\b/g)).toHaveLength(1)
    expect(loginSource).not.toContain('rememberMe')
    expect(loginSource).not.toContain('记住我')
  })

  it('keeps audited status text readable and initial statistics honest', () => {
    const inspirationSource = readSource('src/views/InspirationMode.vue')
    const workspaceSource = readSource('src/views/NovelWorkspace.vue')
    const assistantSource = readSource('src/components/writing-desk/WDAssistantPanel.vue')
    const statisticsSource = readSource('src/components/admin/Statistics.vue')

    expect(readCssBlock(inspirationSource, '.ledger-item')).not.toContain('opacity: 0.38')
    expect(readCssBlock(inspirationSource, '.ledger-footer')).toContain('color: var(--md-on-surface-variant)')
    expect(readCssBlock(workspaceSource, '.workspace-hero__goal-tag')).toContain('color: var(--md-on-surface)')
    expect(readCssBlock(assistantSource, '.wd-ai__section--risk .wd-ai__head')).toContain('color: var(--md-on-surface)')
    expect(assistantSource.match(/<details class="wd-ai__section/g)).toHaveLength(6)
    expect(assistantSource.match(/<details class="wd-ai__section" open>/g)).toHaveLength(1)
    expect(statisticsSource).toContain("statisticsPending ? '—'")
    expect(statisticsSource).toContain("novelsPending ? '—'")
  })

  it('avoids layout-property animation in character dna panels', () => {
    const source = readSource('src/components/CharactersEditorEnhanced.vue')

    expect(source).toContain('opacity 0.2s ease-out')
    expect(source).toContain('transform 0.2s ease-out')
    expect(source).not.toContain('max-height 0.3s ease')
  })

  it('keeps paper-theme primary text token contrast at WCAG AA level', () => {
    const source = readGlobalCss()
    const primaryText = readLightThemeCustomProperty(source, '--md-primary')
    const background = readLightThemeCustomProperty(source, '--md-background')

    expect(contrastRatio(primaryText, background)).toBeGreaterThanOrEqual(4.5)
  })

  it('keeps paper-theme vermilion text token contrast at WCAG AA level', () => {
    const source = readGlobalCss()
    const secondaryText = readLightThemeCustomProperty(source, '--md-secondary-readable')
    const surface = readLightThemeCustomProperty(source, '--md-surface')
    const background = readLightThemeCustomProperty(source, '--md-background')
    const loginSource = readSource('src/views/Login.vue')

    expect(contrastRatio(secondaryText, surface)).toBeGreaterThanOrEqual(4.5)
    expect(contrastRatio(secondaryText, background)).toBeGreaterThanOrEqual(4.5)
    expect(loginSource).toContain('color: var(--md-secondary-readable)')
  })

  it('keeps typography roles centralized in design tokens', () => {
    const css = readGlobalCss()
    const mainSource = readSource('src/main.ts')
    const bodyBlock = readCssBlock(css, 'body')

    expect(readLightThemeCustomProperty(css, '--md-font-serif')).toContain("'Noto Serif SC'")
    expect(readLightThemeCustomProperty(css, '--md-font-sans')).toContain('ui-sans-serif')
    expect(readLightThemeCustomProperty(css, '--md-font-kai')).toBe('var(--md-font-sans)')
    expect(readLightThemeCustomProperty(css, '--md-font-family')).toBe('var(--md-font-sans)')
    expect(readLightThemeCustomProperty(css, '--md-font-display')).toContain("'Arial Narrow'")
    expect(readLightThemeCustomProperty(css, '--md-font-label')).toBe('var(--md-font-sans)')
    expect(readLightThemeCustomProperty(css, '--md-font-mono')).toContain("'SFMono-Regular'")
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

  it('keeps control outlines visible on the light work surface', () => {
    const css = readGlobalCss()
    const outline = readLightThemeCustomProperty(css, '--md-outline')
    const success = readLightThemeCustomProperty(css, '--md-success')
    const surface = readLightThemeCustomProperty(css, '--md-surface')

    expect(contrastRatio(outline, surface)).toBeGreaterThanOrEqual(3)
    expect(contrastRatio(success, surface)).toBeGreaterThanOrEqual(4.5)
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

  it('uses quiet serif label styling for workspace eyebrow labels', () => {
    const source = readSource('src/views/NovelWorkspace.vue')
    const eyebrowBlock = source.match(/\.workspace-eyebrow\s*\{[\s\S]*?\}/)?.[0] ?? ''

    // 描红界格世界：题签为宋体小签（焦墨系 variant 色），禁用 eyebrow 式 uppercase 小字眉与描红权责色
    expect(eyebrowBlock).toContain('color: var(--md-on-surface-variant);')
    expect(eyebrowBlock).not.toContain('color: var(--md-primary);')
    expect(eyebrowBlock).not.toContain('text-transform: uppercase')
  })

  it('keeps project title buttons touch-safe', () => {
    const source = readSource('src/components/ProjectCard.vue')
    const titleButtonBlock = source.match(/\.project-card__title-button\s*\{[\s\S]*?\}/)?.[0] ?? ''

    expect(titleButtonBlock).toContain('min-height: 44px')
    expect(titleButtonBlock).toContain('padding:')
  })

  it('keeps workflow candidate cards as one accessible radio group', () => {
    const source = readSource('src/components/writing-desk/ChapterWorkflowPanel.vue')

    expect(source).toContain('role="radiogroup"')
    expect(source).toContain('role="radio"')
    expect(source).toContain(':aria-checked="selectedCandidateId === candidate.id"')
    expect(source).toContain('@click="selectedCandidateId = candidate.id"')
  })

  it('announces workflow status and failures with live region semantics', () => {
    const source = readSource('src/components/writing-desk/ChapterWorkflowPanel.vue')

    expect(source).toContain(":role=\"isAlert ? 'alert' : 'status'\"")
    expect(source).toContain(":aria-live=\"isAlert ? 'assertive' : 'polite'\"")
    expect(source).toContain('aria-atomic="true"')
    expect(source).toContain("props.phase === 'fatal' || props.phase === 'failed'")
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

  it('connects auth form errors to their fields', () => {
    const loginSource = readSource('src/views/Login.vue')
    const registerSource = readSource('src/views/Register.vue')

    expect(loginSource).toContain('id="login-error"')
    expect(loginSource).toContain(':aria-invalid="Boolean(error)"')
    expect(loginSource).toContain(':aria-describedby="error ? \'login-error\' : undefined"')

    expect(registerSource).toContain('id="register-error"')
    expect(registerSource).toContain(':aria-invalid="Boolean(fieldErrors.username)"')
    expect(registerSource).toContain(':aria-invalid="Boolean(fieldErrors.email)"')
    expect(registerSource).toContain(':aria-invalid="Boolean(fieldErrors.verificationCode)"')
    expect(registerSource).toContain(':aria-invalid="Boolean(fieldErrors.password)"')
    expect(registerSource).toContain('focusFirstFieldError')
    expect(registerSource).not.toContain(':aria-describedby="error ? \'register-error\' : undefined"')
  })

  it('keeps bundle budget below the warning threshold', () => {
    const packageJson = readJson<{ scripts: Record<string, string> }>('package.json')

    // 描红界格编辑器内核（TipTap/ProseMirror 独立分包 tiptap-editor，仅写作台异步加载）上调后的基线
    expect(packageJson.scripts['build:budget']).toContain('BUNDLE_BUDGET_WARN_JS_TOTAL_GZIP_KB=560')
    expect(packageJson.scripts['build:budget']).toContain('BUNDLE_BUDGET_MAX_JS_TOTAL_GZIP_KB=600')

    // 编辑器内核必须保持独立分包，不得回流入首屏 vendor chunk
    const viteConfigSource = readSource('vite.config.ts')
    expect(viteConfigSource).toContain("'tiptap-editor'")
    expect(viteConfigSource).toContain("'@tiptap', 'prosemirror'")
  })

  it('keeps emotion curve rendering off the Chart.js runtime path', () => {
    const source = readSource('src/components/novel-detail/EmotionCurveSection.vue')

    expect(source).not.toContain("import('@/lib/chartLine')")
    expect(source).not.toContain('chartCanvas')
    expect(source).toContain('emotion-curve-svg')
  })
})
