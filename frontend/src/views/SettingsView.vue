<!-- AIMETA P=设置页_用户设置|R=用户设置表单|NR=不含管理员设置|E=route:/settings#component:SettingsView|X=ui|A=设置表单|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="app-page settings-page">
    <section class="settings-hero" aria-label="AI 设置总览">
      <div class="settings-hero__copy">
        <h1>AI 设置</h1>
        <p>
          先完成文本生成与记忆检索，再按需调整语音朗读和阶段路由。
        </p>
      </div>
      <div class="settings-hero__status">
        <span class="settings-status-chip" :class="`is-${centerStatus.tone}`">{{ centerStatus.label }}</span>
        <span class="settings-status-text">{{ centerStatus.description }}</span>
      </div>
    </section>

    <section class="settings-summary" aria-label="能力摘要">
      <article class="settings-summary__card">
        <p>主文本模型</p>
        <strong>{{ primaryChatModelLabel }}</strong>
        <span>{{ primaryChatProviderLabel }}</span>
      </article>
      <article class="settings-summary__card">
        <p>主检索模型</p>
        <strong>{{ primaryEmbeddingModelLabel }}</strong>
        <span>{{ primaryEmbeddingProviderLabel }}</span>
      </article>
    </section>

    <details class="settings-metrics">
      <summary>
        <span>查看运行指标</span>
        <em>{{ enabledProviders }}/{{ providerCount }} 供应商已启用</em>
      </summary>
      <div class="settings-metrics__grid">
        <article class="settings-summary__card">
          <p>供应商状态</p>
          <strong>{{ enabledProviders }}/{{ providerCount }}</strong>
          <span>已启用 / 总数</span>
        </article>
        <article class="settings-summary__card">
          <p>模型分组</p>
          <strong>{{ enabledChatModels }} 文本 · {{ enabledEmbeddingModels }} 检索</strong>
          <span>{{ stageRouteCount }} 条阶段路由</span>
        </article>
      </div>
    </details>

    <section v-if="showInspirationConfigNotice" class="md-card settings-notice">
      <p class="md-title-small">灵感模式需要先完成模型配置</p>
      <p class="md-body-small mt-1">
        请先在 <strong>文本生成</strong> 中启用模型并指定主模型，保存后会自动跳回灵感模式。
      </p>
    </section>

    <section class="settings-center" aria-label="能力配置面板">
      <nav class="settings-center__nav" aria-label="设置分区" role="tablist">
        <div v-for="group in settingsGroups" :key="group.label" class="settings-center__nav-group" role="presentation">
          <p class="settings-center__nav-group-label" aria-hidden="true">{{ group.label }}</p>
          <button
            v-for="section in group.sections"
            :key="section.id"
            :ref="(el) => setSettingsTabRef(section.id, el)"
            type="button"
            class="settings-center__nav-item"
            :class="{
              'is-active': activeSettingsSection === section.id,
              'nav-item-llm': section.id === 'llm',
              'nav-item-embedding': section.id === 'embedding',
              'nav-item-tts': section.id === 'tts',
              'nav-item-routes': section.id === 'routes'
            }"
            :id="`settings-tab-${section.id}`"
            role="tab"
            :aria-selected="activeSettingsSection === section.id"
            :tabindex="activeSettingsSection === section.id ? 0 : -1"
            aria-controls="settings-panel"
            :title="section.description"
            @click="selectSettingsSection(section.id)"
            @keydown="onSettingsTabKeydown(section.id, $event)"
          >
            <div>
              <span class="settings-center__nav-item-label">{{ section.label }}</span>
              <small>{{ section.description }}</small>
            </div>
          </button>
        </div>
      </nav>

      <section
        id="settings-panel"
        class="settings-center__panel"
        role="tabpanel"
        :aria-labelledby="activeSettingsTabId"
      >
        <PersonalModelRouting
          v-if="activeSettingsSection === 'llm'"
          ref="personalRoutingXRef"
          active-section="llm"
          @saved="handleLLMConfigSaved"
          @navigate="selectSettingsSection"
        />
        <PersonalModelRouting
          v-else-if="activeSettingsSection === 'embedding'"
          ref="personalRoutingXRef"
          active-section="embedding"
          @saved="handleLLMConfigSaved"
          @navigate="selectSettingsSection"
        />
        <PersonalModelRouting
          v-else-if="activeSettingsSection === 'tts'"
          ref="personalRoutingXRef"
          active-section="tts"
          @saved="handleLLMConfigSaved"
          @navigate="selectSettingsSection"
        />
        <PersonalModelRouting
          v-else
          ref="personalRoutingXRef"
          active-section="routes"
          @saved="handleLLMConfigSaved"
          @navigate="selectSettingsSection"
        />
      </section>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch, type ComponentPublicInstance } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import PersonalModelRouting from '@/components/llm-settings/PersonalModelRouting.vue'
import { globalAlert } from '@/composables/useAlert'
import { useLLMConfigBundleQuery } from '@/queries/llm'

type SettingsSectionId = 'llm' | 'embedding' | 'tts' | 'routes'

interface SettingsSection {
  id: SettingsSectionId
  label: string
  description: string
}

const route = useRoute()
const router = useRouter()
const bundleQuery = useLLMConfigBundleQuery()

const settingsGroups: Array<{ label: string; sections: SettingsSection[] }> = [
  {
    label: '基础能力',
    sections: [
      { id: 'llm', label: '文本生成', description: '供应商、模型拉取与主模型' },
      { id: 'embedding', label: '记忆检索', description: '向量供应商与唯一检索模型' },
    ],
  },
  {
    label: '高级能力',
    sections: [
      { id: 'tts', label: '语音朗读', description: '默认朗读模型' },
      { id: 'routes', label: '阶段路由', description: '按创作阶段覆盖主模型' },
    ],
  },
]
const settingsSections = settingsGroups.flatMap((group) => group.sections)

const resolveSettingsSection = (value: unknown): SettingsSectionId =>
  typeof value === 'string' && settingsSections.some((section) => section.id === value)
    ? value as SettingsSectionId
    : 'llm'

const activeSettingsSection = ref<SettingsSectionId>(resolveSettingsSection(route.query.tab))
const personalRoutingXRef = ref<InstanceType<typeof PersonalModelRouting> | null>(null)
const isDirty = computed(() => personalRoutingXRef.value?.isDirty ?? false)
const settingsTabRefs = ref<Record<SettingsSectionId, HTMLButtonElement | null>>({
  llm: null,
  embedding: null,
  tts: null,
  routes: null,
})

const activeSettingsTabId = computed(() => `settings-tab-${activeSettingsSection.value}`)

const confirmDiscardChanges = () => {
  if (!isDirty.value) return Promise.resolve(true)
  return globalAlert.showConfirm('当前配置尚未保存，继续将丢失这些修改。', '放弃未保存修改？')
}

const selectSettingsSection = async (sectionId: SettingsSectionId) => {
  if (sectionId === activeSettingsSection.value) return true
  if (!(await confirmDiscardChanges())) return false
  activeSettingsSection.value = sectionId
  await router.push({ name: 'settings', query: { ...route.query, tab: sectionId } })
  return true
}

watch(
  () => route.query.tab,
  (tab) => {
    activeSettingsSection.value = resolveSettingsSection(tab)
  },
)

const setSettingsTabRef = (
  sectionId: SettingsSectionId,
  element: Element | ComponentPublicInstance | null,
) => {
  const target =
    element instanceof HTMLButtonElement
      ? element
      : element && '$el' in element && element.$el instanceof HTMLButtonElement
        ? element.$el
        : null
  settingsTabRefs.value[sectionId] = target
}

const focusSettingsTab = (sectionId: SettingsSectionId) => {
  settingsTabRefs.value[sectionId]?.focus()
}

// 设置页 tabs 使用 roving tabindex 和方向键切换，保证键盘用户无需反复 Tab 扫描。
const onSettingsTabKeydown = async (sectionId: SettingsSectionId, event: KeyboardEvent) => {
  const currentIndex = settingsSections.findIndex((section) => section.id === sectionId)
  if (currentIndex === -1) return
  const lastIndex = settingsSections.length - 1

  let nextIndex: number | null = null
  if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
    nextIndex = currentIndex === lastIndex ? 0 : currentIndex + 1
  } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
    nextIndex = currentIndex === 0 ? lastIndex : currentIndex - 1
  } else if (event.key === 'Home') {
    nextIndex = 0
  } else if (event.key === 'End') {
    nextIndex = lastIndex
  }

  if (nextIndex === null || nextIndex === currentIndex) return
  event.preventDefault()
  const nextSectionId = settingsSections[nextIndex].id
  if (await selectSettingsSection(nextSectionId)) {
    focusSettingsTab(nextSectionId)
  }
}

const showInspirationConfigNotice = computed(
  () => route.query.source === 'inspiration' && route.query.reason === 'missing_models',
)

const providerCount = computed(() => bundleQuery.data.value?.providers?.length ?? 0)
const enabledProviders = computed(
  () => bundleQuery.data.value?.providers?.filter((provider) => provider.is_enabled).length ?? 0,
)

const enabledChatModels = computed(
  () =>
    bundleQuery.data.value?.models?.filter(
      (model) => Boolean(model.is_enabled) && Boolean(model.capabilities?.chat),
    ).length ?? 0,
)

const enabledEmbeddingModels = computed(
  () =>
    bundleQuery.data.value?.models?.filter(
      (model) => Boolean(model.is_enabled) && Boolean(model.capabilities?.embedding),
    ).length ?? 0,
)

const stageRouteCount = computed(() => bundleQuery.data.value?.stage_routes?.length ?? 0)

const primaryChatModel = computed(
  () =>
    bundleQuery.data.value?.models?.find(
      (model) => Boolean(model.is_enabled) && Boolean(model.capabilities?.chat) && model.is_default_chat,
    ) ?? null,
)

const primaryEmbeddingModel = computed(
  () =>
    bundleQuery.data.value?.models?.find(
      (model) =>
        Boolean(model.is_enabled) && Boolean(model.capabilities?.embedding) && model.is_default_embedding,
    ) ?? null,
)

const providerNameById = (providerId?: number | null) => {
  if (providerId === null || providerId === undefined) return '未绑定供应商'
  const provider = bundleQuery.data.value?.providers?.find((item) => item.id === providerId)
  return provider?.name || '未知供应商'
}

const primaryChatModelLabel = computed(() => primaryChatModel.value?.display_name || '未指定')
const primaryEmbeddingModelLabel = computed(
  () => primaryEmbeddingModel.value?.display_name || '未指定',
)

const primaryChatProviderLabel = computed(() => providerNameById(primaryChatModel.value?.provider_id))
const primaryEmbeddingProviderLabel = computed(() =>
  providerNameById(primaryEmbeddingModel.value?.provider_id),
)

const centerStatus = computed(() => {
  if (bundleQuery.isFetching.value || bundleQuery.isLoading.value) {
    return {
      label: '配置同步中',
      description: '正在同步最新模型配置。',
      tone: 'neutral' as const,
    }
  }

  if (enabledChatModels.value === 0) {
    return {
      label: '待配置',
      description: '至少启用一个文本模型并设置主模型后，创作链路才会稳定。',
      tone: 'warning' as const,
    }
  }

  if (enabledEmbeddingModels.value === 0) {
    return {
      label: '基础待完善',
      description: '文本生成已可用，配置记忆检索模型后可完成基础设置。',
      tone: 'warning' as const,
    }
  }

  return {
    label: '基础就绪',
    description: stageRouteCount.value === 0
      ? '文本生成和记忆检索已可用，高级能力可按需配置。'
      : '文本生成、记忆检索和阶段路由已就绪。',
    tone: 'success' as const,
  }
})

const onBeforeUnload = (event: BeforeUnloadEvent) => {
  if (!isDirty.value) return
  event.preventDefault()
  event.returnValue = ''
}

onMounted(() => window.addEventListener('beforeunload', onBeforeUnload))
onBeforeUnmount(() => window.removeEventListener('beforeunload', onBeforeUnload))
onBeforeRouteUpdate((to) => {
  const nextSection = resolveSettingsSection(to.query.tab)
  if (nextSection === activeSettingsSection.value) return true
  return confirmDiscardChanges()
})
onBeforeRouteLeave(() => confirmDiscardChanges())

const handleLLMConfigSaved = async () => {
  if (!showInspirationConfigNotice.value) {
    return
  }
  await router.push('/inspiration')
}
</script>

<style scoped>
.settings-page {
  min-height: calc(var(--app-viewport-unit) - 112px);
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-5);
  color: var(--md-on-surface);
  font-family: var(--md-font-serif) !important;
}

.settings-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--md-spacing-4);
  padding: clamp(var(--md-spacing-5), 4vw, var(--md-spacing-8));
  border: 1px solid var(--md-jiege) !important; /* 1px 界格发线 */
  border-radius: var(--md-radius-xs) !important;
  background-color: var(--md-surface) !important;
  box-shadow: var(--md-elevation-paper-1) !important;
}

.settings-hero h1 {
  margin: 0;
  color: var(--md-on-surface);
  font-size: clamp(1.4rem, 2vw, 1.95rem);
  font-family: var(--md-font-serif) !important;
  font-weight: 600;
  letter-spacing: 0.05em;
}

.settings-hero p {
  margin: var(--md-spacing-3) 0 0;
  max-width: 72ch;
  color: var(--md-on-surface-variant);
  line-height: 1.7;
  font-family: var(--md-font-serif) !important; /* 落定 UI 文案一律宋体 */
}

.settings-hero__status {
  padding: var(--md-spacing-4);
  border-radius: var(--md-radius-xs) !important;
  border: 1px solid var(--md-outline-variant);
  background-color: color-mix(in srgb, var(--md-surface) 88%, transparent);
  min-width: 260px;
}

.settings-status-chip {
  display: inline-flex;
  align-items: center;
  height: 30px;
  padding: 0 12px;
  border-radius: var(--md-radius-xs) !important;
  font-size: var(--md-label-medium);
  font-weight: 700;
  border: 1px solid currentColor !important;
  /* 状态印一律无影 */
}

.settings-status-chip.is-warning {
  color: var(--md-on-warning-container);
  background-color: var(--md-warning-container);
}

.settings-status-chip.is-focus {
  color: var(--md-on-surface);
  background-color: var(--md-surface-container);
}

.settings-status-chip.is-success {
  color: var(--md-on-success-container);
  background-color: var(--md-success-container);
}

.settings-status-chip.is-neutral {
  color: var(--md-on-surface-variant);
  background-color: var(--md-surface-container);
}

.settings-status-text {
  margin-top: var(--md-spacing-2);
  display: block;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
  line-height: 1.6;
}

.settings-summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--md-spacing-4);
}

.settings-summary__card {
  padding: var(--md-spacing-4);
  border: 1px solid var(--md-jiege) !important;
  border-radius: var(--md-radius-xs) !important;
  background-color: var(--md-surface) !important;
  transition:
    border-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.25s cubic-bezier(0.22, 1, 0.36, 1) !important;
}

.settings-summary__card:hover {
  box-shadow: var(--md-elevation-paper-1) !important;
  border-color: var(--md-outline) !important;
}

.settings-summary__card p,
.settings-summary__card span {
  margin: 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.settings-summary__card strong {
  margin: var(--md-spacing-2) 0 4px;
  display: block;
  color: var(--md-on-surface);
  font-size: var(--md-title-medium);
}

.settings-metrics {
  border: 1px solid var(--md-jiege) !important;
  border-radius: var(--md-radius-xs) !important;
  background-color: var(--md-surface) !important;
}

.settings-metrics summary {
  list-style: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--md-spacing-2);
  min-height: 44px;
  padding: var(--md-spacing-3) var(--md-spacing-4);
  color: var(--md-on-surface);
  font-size: var(--md-title-small);
  font-weight: 600;
  cursor: pointer;
  transition:
    background-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    color 0.25s cubic-bezier(0.22, 1, 0.36, 1) !important;
}

.settings-metrics summary::-webkit-details-marker {
  display: none;
}

.settings-metrics summary::after {
  content: '';
  width: 9px;
  height: 9px;
  border-right: 1.5px solid currentColor;
  border-bottom: 1.5px solid currentColor;
  transform: rotate(45deg);
  transform-origin: center;
  transition: transform var(--md-duration-short) var(--md-easing-standard);
}

.settings-metrics[open] summary::after {
  transform: rotate(-135deg) translate(-1px, -1px);
}

.settings-metrics summary:hover {
  color: var(--md-on-surface) !important;
  background-color: var(--md-state-layer-hover) !important;
}

.settings-metrics summary:active {
  transform: translate(1px, 1px);
  opacity: 0.8;
}

.settings-metrics summary:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
  border-radius: var(--md-radius-xs);
}

.settings-metrics summary em {
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-medium);
  font-style: normal;
  font-weight: 500;
}

.settings-metrics__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--md-spacing-4);
  padding: var(--md-spacing-4);
  border-top: 1px dashed var(--md-outline-variant) !important;
}

.settings-notice {
  border-radius: var(--md-radius-xs) !important;
  padding: var(--md-spacing-4);
  border: 1px dashed var(--md-warning) !important;
  background-color: var(--md-warning-container) !important;
  color: var(--md-warning-text) !important;
}

.settings-center {
  display: grid;
  grid-template-columns: 250px minmax(0, 1fr);
  gap: var(--md-spacing-4);
  align-items: start;
}

.settings-center__nav,
.settings-center__panel {
  border: 1px solid var(--md-jiege) !important; /* 1px 界格发线 */
  border-radius: var(--md-radius-xs) !important;
  background-color: var(--md-surface) !important;
  box-shadow: var(--md-elevation-paper-1) !important;
}

.settings-center__nav {
  padding: var(--md-spacing-2);
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-2);
}

.settings-center__nav-group {
  display: grid;
  gap: var(--md-spacing-2);
}

.settings-center__nav-group + .settings-center__nav-group {
  margin-top: var(--md-spacing-2);
  padding-top: var(--md-spacing-3);
  border-top: 1px solid var(--md-outline-variant);
}

.settings-center__nav-group-label {
  margin: 0;
  padding: 0 var(--md-spacing-3);
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-small);
  font-weight: 700;
}

.settings-center__nav-item {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: var(--md-spacing-2);
  width: 100%;
  min-width: 0;
  min-height: 64px;
  padding: 12px var(--md-spacing-4) !important;
  border: 1px solid transparent; /* 等宽透明描边，激活态只换色不改宽，消除抖动 */
  border-radius: var(--md-radius-xs) !important;
  background-color: transparent;
  color: var(--md-on-surface);
  cursor: pointer;
  text-align: left;
  transition:
    background-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.25s cubic-bezier(0.22, 1, 0.36, 1) !important;
}

.settings-center__nav-item > div {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 3px;
  min-width: 0;
  flex: 1;
}

.settings-center__nav-item:hover {
  border-color: var(--md-outline-variant);
  background-color: var(--md-state-layer-hover) !important;
  color: var(--md-on-surface) !important;
}

.settings-center__nav-item:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}

.settings-center__nav-item.is-active,
.settings-center__nav-item[aria-selected='true'] {
  border-color: var(--md-jiege) !important; /* 激活=界格发线笺片，轻微浮起标识当前卷 */
  background-color: var(--md-surface) !important;
  color: var(--md-primary-dark) !important;
  font-weight: 700 !important;
  box-shadow: var(--md-elevation-paper-1) !important;
}

.settings-center__nav-item:active {
  transform: translate(1px, 1px) !important;
}

/* “词、忆、枢” 终极金石印章 ::after - 初始悬空隐形，防止布局抖动 */
.settings-center__nav-item::after {
  content: '';
  font-family: var(--md-font-serif) !important;
  font-weight: 900;
  font-size: 14px;
  color: transparent !important;
  background-color: transparent !important;
  border: 1px solid transparent !important;
  border-radius: var(--md-radius-xs) !important;
  width: 24px;
  height: 24px;
  display: grid;
  place-items: center;
  user-select: none;
  flex-shrink: 0;
  margin-left: 8px;
  opacity: 0;
  transform: scale(1.1) translateY(-2px); /* 起笔悬空 */
  transition:
    background-color 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    color 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.3s cubic-bezier(0.22, 1, 0.36, 1) !important;
}

/* 激活时，红泥落地，徐徐印下（印章一律无影） */
.settings-center__nav-item.is-active::after,
.settings-center__nav-item[aria-selected='true']::after {
  color: var(--md-secondary) !important;
  background-color: color-mix(in srgb, var(--md-secondary) 12%, transparent) !important;
  border: 1px solid var(--md-secondary) !important;
  opacity: 1;
  transform: scale(1) translateY(0); /* 盖章印入熟宣 */
}

/* 预先配置字符，保证静态占位 */
.settings-center__nav-item.nav-item-llm::after {
  content: '詞' !important;
}

.settings-center__nav-item.nav-item-embedding::after {
  content: '憶' !important;
}

.settings-center__nav-item.nav-item-tts::after {
  content: '讀' !important;
}

.settings-center__nav-item.nav-item-routes::after {
  content: '樞' !important;
}

.settings-center__nav-item-label {
  font-size: var(--md-title-small);
  font-weight: 700;
}

.settings-center__nav-item small {
  color: inherit;
  font-size: var(--md-body-small);
  opacity: 0.85;
}

.settings-center__panel {
  min-width: 0;
  padding: var(--md-spacing-5);
}

@media (max-width: 1199px) {
  .settings-center {
    grid-template-columns: minmax(0, 1fr);
  }

  .settings-center__nav {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .settings-center__nav-group + .settings-center__nav-group {
    margin-top: 0;
    padding-top: 0;
    padding-left: var(--md-spacing-2);
    border-top: 0;
    border-left: 1px solid var(--md-outline-variant);
  }
}

@media (max-width: 833px) {
  .settings-page {
    gap: var(--md-spacing-4);
  }

  .settings-hero {
    flex-direction: column;
    align-items: stretch;
    padding: var(--md-spacing-4);
    border-radius: var(--md-radius-xs) !important;
  }

  .settings-hero__status {
    min-width: 0;
  }

  .settings-summary {
    grid-template-columns: minmax(0, 1fr);
  }

  .settings-metrics__grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .settings-center__nav-item {
    min-height: 48px !important;
    padding: 6px var(--md-spacing-3) !important;
  }

  .settings-center__nav-item-label {
    font-size: var(--md-body-medium) !important;
  }

  .settings-center__nav-item small {
    font-size: 12px !important;
  }

  .settings-center__nav-item::after {
    width: 20px !important;
    height: 20px !important;
    font-size: 11px !important;
    margin-left: 4px !important;
  }

  .settings-center__panel {
    padding: var(--md-spacing-4);
  }
}

@media (max-width: 680px) {
  .settings-center__nav {
    grid-template-columns: minmax(0, 1fr);
  }

  .settings-center__nav-group + .settings-center__nav-group {
    margin-top: var(--md-spacing-2);
    padding-top: var(--md-spacing-3);
    padding-left: 0;
    border-top: 1px solid var(--md-outline-variant);
    border-left: 0;
  }
}

/* 补齐 details 伸缩栏展开纵向慢润动画 */
.settings-metrics[open] .settings-metrics__grid {
  animation: ink-details-slide 0.35s cubic-bezier(0.22, 1, 0.36, 1) both;
  transform-origin: top; /* 以顶端为轴垂挂挂开 */
}

@keyframes ink-details-slide {
  from {
    opacity: 0;
    transform: translateY(-8px) scaleY(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scaleY(1);
  }
}
</style>
