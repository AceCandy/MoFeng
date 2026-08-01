<!-- AIMETA P=设置页_用户设置|R=用户设置表单|NR=不含管理员设置|E=route:/settings#component:SettingsView|X=ui|A=设置表单|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div :class="{ 'app-page': !props.isModal, 'settings-page': true, 'is-in-modal': props.isModal }">
    <section v-if="!props.isModal" class="settings-hero" aria-label="AI 能力中心总览">
      <div class="settings-hero__copy">
        <p class="settings-eyebrow">AI 能力中心 <span class="settings-hero__stamp">[ 設 ]</span></p>
        <h2>模型、供应商与创作阶段路由</h2>
        <p>
          统一维护你的文本生成、记忆检索和阶段路由策略，让每个创作环节都调用到合适的 AI
          能力。
        </p>
      </div>
      <div class="settings-hero__status">
        <span class="settings-status-chip" :class="`is-${centerStatus.tone}`">{{ centerStatus.label }}</span>
        <span class="settings-status-text">{{ centerStatus.description }}</span>
      </div>
    </section>

    <section v-if="!props.isModal" class="settings-summary" aria-label="能力摘要">
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

    <details v-if="!props.isModal" class="settings-metrics">
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

    <section v-if="showInspirationConfigNotice && !props.isModal" class="md-card settings-notice">
      <p class="md-title-small">灵感模式需要先完成模型配置</p>
      <p class="md-body-small mt-1">
        请先在 <strong>文本生成</strong> 中启用模型并指定主模型，保存后会自动跳回灵感模式。
      </p>
    </section>

    <section class="settings-center" aria-label="能力配置面板">
      <nav class="settings-center__nav" aria-label="设置分区" role="tablist">
        <button
          v-for="section in settingsSections"
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
          :is-modal="props.isModal"
          @saved="handleLLMConfigSaved"
          @navigate="selectSettingsSection"
        />
        <PersonalModelRouting
          v-else-if="activeSettingsSection === 'embedding'"
          ref="personalRoutingXRef"
          active-section="embedding"
          :is-modal="props.isModal"
          @saved="handleLLMConfigSaved"
          @navigate="selectSettingsSection"
        />
        <PersonalModelRouting
          v-else-if="activeSettingsSection === 'tts'"
          ref="personalRoutingXRef"
          active-section="tts"
          :is-modal="props.isModal"
          @saved="handleLLMConfigSaved"
          @navigate="selectSettingsSection"
        />
        <PersonalModelRouting
          v-else
          ref="personalRoutingXRef"
          active-section="routes"
          :is-modal="props.isModal"
          @saved="handleLLMConfigSaved"
          @navigate="selectSettingsSection"
        />
      </section>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, type ComponentPublicInstance } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PersonalModelRouting from '@/components/llm-settings/PersonalModelRouting.vue'
import { useLLMConfigBundleQuery } from '@/queries/llm'

const props = withDefaults(
  defineProps<{
    isModal?: boolean
  }>(),
  {
    isModal: false,
  }
)

const emit = defineEmits<{
  (e: 'saved'): void
}>()

type SettingsSectionId = 'llm' | 'embedding' | 'tts' | 'routes'

interface SettingsSection {
  id: SettingsSectionId
  label: string
  description: string
}

const route = useRoute()
const router = useRouter()
const bundleQuery = useLLMConfigBundleQuery()

const settingsSections: SettingsSection[] = [
  { id: 'llm', label: '文本生成', description: '供应商、模型拉取与主模型' },
  { id: 'embedding', label: '记忆检索', description: '向量供应商与唯一检索模型' },
  { id: 'tts', label: '语音朗读', description: '朗读模型、音色与语速' },
  { id: 'routes', label: '阶段路由', description: '按创作阶段覆盖主模型' },
]

const activeSettingsSection = ref<SettingsSectionId>('llm')
const settingsTabRefs = ref<Record<SettingsSectionId, HTMLButtonElement | null>>({
  llm: null,
  embedding: null,
  tts: null,
  routes: null,
})

const activeSettingsTabId = computed(() => `settings-tab-${activeSettingsSection.value}`)

const selectSettingsSection = (sectionId: SettingsSectionId) => {
  activeSettingsSection.value = sectionId
}

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
const onSettingsTabKeydown = (sectionId: SettingsSectionId, event: KeyboardEvent) => {
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
  selectSettingsSection(nextSectionId)
  focusSettingsTab(nextSectionId)
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

  if (stageRouteCount.value === 0) {
    return {
      label: '基础可用',
      description: '你已可以创作，建议补充阶段路由以提升不同任务的模型匹配度。',
      tone: 'focus' as const,
    }
  }

  return {
    label: '能力就绪',
    description: '主模型、检索模型和阶段路由已配置，可直接进入高强度创作。',
    tone: 'success' as const,
  }
})

const personalRoutingXRef = ref<InstanceType<typeof PersonalModelRouting> | null>(null)

const save = async () => {
  if (personalRoutingXRef.value && typeof personalRoutingXRef.value.save === 'function') {
    await personalRoutingXRef.value.save()
  }
}

const isDirty = computed(() => {
  return personalRoutingXRef.value?.isDirty ?? false
})

defineExpose({
  save,
  isDirty,
})

const handleLLMConfigSaved = async () => {
  emit('saved')
  if (!showInspirationConfigNotice.value) {
    return
  }
  if (!props.isModal) {
    await router.push('/inspiration')
  }
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
  border: 3px double var(--md-outline) !important;
  border-radius: var(--md-radius-xs) !important;
  background-color: var(--md-surface) !important;
  box-shadow: 4px 4px 0px color-mix(in srgb, var(--md-on-surface) 15%, transparent) !important;
}

.settings-eyebrow {
  margin: 0;
  color: var(--md-primary-dark);
  font-size: var(--md-label-medium);
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.settings-hero__stamp {
  font-family: var(--md-font-serif) !important;
  font-weight: 900;
  color: var(--md-secondary) !important;
  margin-left: 6px;
  user-select: none;
}

.settings-hero h2 {
  margin: 10px 0 0;
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
  font-family: var(--md-font-kai) !important;
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
  box-shadow: 1px 1px 0px color-mix(in srgb, var(--md-on-surface) 8%, transparent) !important;
}

.settings-status-chip.is-warning {
  color: var(--md-on-warning-container);
  background-color: var(--md-warning-container);
}

.settings-status-chip.is-focus {
  color: var(--md-on-primary-container);
  background-color: var(--md-primary-container);
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
  border: 1px solid var(--md-outline-variant) !important;
  border-radius: var(--md-radius-xs) !important;
  background-color: var(--md-surface) !important;
  box-shadow: var(--md-shadow-primary-1) !important;
  transition:
    border-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.25s cubic-bezier(0.22, 1, 0.36, 1) !important;
}

.settings-summary__card:hover {
  transform: translate(-1px, -1px);
  box-shadow: 3px 3px 0px color-mix(in srgb, var(--md-on-surface) 18%, transparent) !important;
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
  border: 1px solid var(--md-outline-variant) !important;
  border-radius: var(--md-radius-xs) !important;
  background-color: var(--md-surface) !important;
  box-shadow: var(--md-shadow-primary-1) !important;
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
  box-shadow: 2px 2px 0px color-mix(in srgb, var(--md-warning) 20%, transparent) !important;
}

.settings-center {
  display: grid;
  grid-template-columns: 250px minmax(0, 1fr);
  gap: var(--md-spacing-4);
  align-items: start;
}

.settings-center__nav,
.settings-center__panel {
  border: 3px double var(--md-outline) !important;
  border-radius: var(--md-radius-sm) !important;
  background-color: var(--md-surface) !important;
  box-shadow: 4px 4px 0px color-mix(in srgb, var(--md-on-surface) 12%, transparent) !important;
}

.settings-center__nav {
  padding: var(--md-spacing-2);
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-2);
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
  border: 1px solid transparent;
  border-left: 3px solid transparent; /* 固定 3px 左框，激活态只换色不改宽，消除抖动 */
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
  border-color: var(--md-outline-variant) !important;
  border-left-color: var(--md-secondary) !important; /* 左侧 3px 朱砂竖描作活动指示，禁整框实底 */
  background-color: var(--md-state-layer-hover) !important;
  color: var(--md-on-surface) !important;
  font-weight: 700 !important;
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

/* 激活时，红泥落地，徐徐印下 */
.settings-center__nav-item.is-active::after,
.settings-center__nav-item[aria-selected='true']::after {
  color: var(--md-secondary) !important;
  background-color: color-mix(in srgb, var(--md-secondary) 12%, transparent) !important;
  border: 1px solid var(--md-secondary) !important;
  box-shadow: 1px 1px 0px color-mix(in srgb, var(--md-secondary) 18%, transparent) !important;
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
    grid-template-columns: repeat(4, minmax(0, 1fr));
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

  .settings-center__nav {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .settings-center__nav-item {
    min-height: 48px !important;
    padding: 6px var(--md-spacing-3) !important;
  }

  .settings-center__nav-item-label {
    font-size: var(--md-body-medium) !important;
  }

  .settings-center__nav-item small {
    font-size: 10px !important;
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
