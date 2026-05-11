<!-- AIMETA P=设置页_用户设置|R=用户设置表单|NR=不含管理员设置|E=route:/settings#component:SettingsView|X=ui|A=设置表单|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="min-h-screen md-surface-dim settings-page">
    <div class="mx-auto flex w-full max-w-7xl flex-col gap-5 px-4 py-6 md:px-6 md:py-8">
      <section class="md-card md-card-elevated settings-overview">
        <div class="settings-overview__top">
          <div class="settings-overview__lead">
            <router-link to="/workspace" class="md-btn md-btn-text md-ripple">
              <span aria-hidden="true">←</span>
              返回
            </router-link>
            <h1 class="md-title-large settings-title">模型设置</h1>
          </div>
          <span class="settings-version-badge" :class="versionStatusClass">
            {{ versionStatusLabel }}
          </span>
        </div>
        <div class="settings-overview__meta">
          <span class="settings-meta-pill">
            <span class="md-label-medium">本地</span>
            <code class="settings-code">{{ localVersion }}</code>
          </span>
          <span class="settings-meta-pill">
            <span class="md-label-medium">远程</span>
            <code class="settings-code">{{ remoteVersion || '未获取' }}</code>
          </span>
        </div>
      </section>

      <section v-if="showInspirationConfigNotice" class="md-card settings-notice">
        <p class="md-title-small">灵感模式需要先完成模型配置</p>
        <p class="md-body-small mt-1">
          请先在 <strong>LLM 模型</strong> 中启用模型并勾选主模型，保存后会自动跳回灵感模式。
        </p>
      </section>

      <section class="settings-console">
        <nav class="settings-console__nav" aria-label="设置分区">
          <button
            v-for="section in settingsSections"
            :key="section.id"
            type="button"
            class="settings-console__nav-item"
            :class="{ 'is-active': activeSettingsSection === section.id }"
            :aria-current="activeSettingsSection === section.id ? 'page' : undefined"
            @click="selectSettingsSection(section.id)"
          >
            <span class="settings-console__nav-item-label">{{ section.label }}</span>
            <span class="settings-console__nav-item-description">{{ section.description }}</span>
          </button>
        </nav>

        <section class="md-card md-card-elevated settings-panel">
          <div class="settings-console__mobile-tabs" aria-label="设置分区">
            <button
              v-for="section in settingsSections"
              :key="section.id"
              type="button"
              class="settings-console__mobile-tab"
              :class="{ 'is-active': activeSettingsSection === section.id }"
              :aria-current="activeSettingsSection === section.id ? 'page' : undefined"
              @click="selectSettingsSection(section.id)"
            >
              {{ section.label }}
            </button>
          </div>

          <div class="settings-panel__header">
            <div>
              <p class="md-label-medium settings-panel__eyebrow">当前分区</p>
              <h2 class="md-title-large settings-panel__title">{{ activeSectionMeta.label }}</h2>
            </div>
            <p class="md-body-small settings-panel__description">
              {{ activeSectionMeta.description }}
            </p>
          </div>

          <PersonalModelRouting
            v-if="activeSettingsSection === 'llm'"
            active-section="llm"
            @saved="handleLLMConfigSaved"
          />
          <PersonalModelRouting
            v-else-if="activeSettingsSection === 'embedding'"
            active-section="embedding"
            @saved="handleLLMConfigSaved"
          />
          <PersonalModelRouting v-else active-section="routes" @saved="handleLLMConfigSaved" />
        </section>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PersonalModelRouting from '@/components/llm-settings/PersonalModelRouting.vue'
import { getRemoteVersion, normalizeComparableVersion } from '@/api/version'

type SettingsSectionId = 'llm' | 'embedding' | 'routes'

interface SettingsSection {
  id: SettingsSectionId
  label: string
  description: string
}

const route = useRoute()
const router = useRouter()
const localVersion = (import.meta.env.VITE_APP_VERSION as string | undefined)?.trim() || 'dev'
const remoteVersion = ref<string | null>(null)
const remoteVersionCheckFailed = ref(false)
const settingsSections: SettingsSection[] = [
  { id: 'llm', label: 'LLM 模型', description: '启用 Chat 模型并指定主模型' },
  { id: 'embedding', label: '向量模型', description: '为记忆检索选择唯一向量模型' },
  { id: 'routes', label: 'AI 阶段路由', description: '按写作阶段覆盖主模型' },
]

const activeSettingsSection = ref<SettingsSectionId>('llm')

const activeSectionMeta = computed(
  () =>
    settingsSections.find((section) => section.id === activeSettingsSection.value) ||
    settingsSections[0],
)

const selectSettingsSection = (sectionId: SettingsSectionId) => {
  activeSettingsSection.value = sectionId
}

const hasNewVersion = computed(() => {
  if (!remoteVersion.value) {
    return false
  }
  return (
    normalizeComparableVersion(remoteVersion.value) !== normalizeComparableVersion(localVersion)
  )
})

const showInspirationConfigNotice = computed(
  () => route.query.source === 'inspiration' && route.query.reason === 'missing_models',
)

const versionStatusClass = computed(() => {
  if (remoteVersionCheckFailed.value) {
    return 'is-error'
  }
  if (hasNewVersion.value) {
    return 'is-warning'
  }
  return 'is-success'
})

const versionStatusLabel = computed(() => {
  if (remoteVersionCheckFailed.value) {
    return '版本检查失败'
  }
  if (hasNewVersion.value) {
    return '发现新版本'
  }
  return '已是最新'
})

const handleLLMConfigSaved = async () => {
  if (!showInspirationConfigNotice.value) {
    return
  }
  await router.push('/inspiration')
}

onMounted(async () => {
  try {
    remoteVersion.value = await getRemoteVersion()
    remoteVersionCheckFailed.value = !remoteVersion.value
  } catch {
    remoteVersionCheckFailed.value = true
  }
})
</script>

<style scoped>
.settings-page {
  background-color: var(--md-surface-dim);
}

.settings-overview {
  border-radius: var(--md-radius-xl);
  padding: var(--md-spacing-3) var(--md-spacing-4);
}

.settings-overview__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--md-spacing-2);
}

.settings-overview__lead {
  display: flex;
  align-items: center;
  gap: var(--md-spacing-2);
}

.settings-title {
  margin: 0;
  color: var(--md-on-surface);
}

.settings-overview__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--md-spacing-1);
  margin-top: var(--md-spacing-2);
}

.settings-meta-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 26px;
  padding: 0 10px;
  border-radius: var(--md-radius-full);
  border: 1px solid var(--md-outline-variant);
  background-color: var(--md-surface-container-low);
}

.settings-code {
  font-family: var(--md-font-mono);
  font-size: 0.78rem;
  color: var(--md-on-surface);
}

.settings-version-badge {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  border-radius: var(--md-radius-full);
  padding: 0 10px;
  font-size: var(--md-label-medium);
  font-weight: 600;
}

.settings-version-badge.is-success {
  background-color: var(--md-success-container);
  color: var(--md-on-success-container);
}

.settings-version-badge.is-warning {
  background-color: var(--md-warning-container);
  color: var(--md-on-warning-container);
}

.settings-version-badge.is-error {
  background-color: var(--md-error-container);
  color: var(--md-on-error-container);
}

.settings-notice {
  border-radius: var(--md-radius-lg);
  padding: var(--md-spacing-4);
  border: 1px solid color-mix(in srgb, var(--md-warning) 35%, var(--md-outline-variant));
  background-color: var(--md-warning-container);
  color: var(--md-on-warning-container);
}

.settings-console {
  display: grid;
  grid-template-columns: minmax(220px, 260px) minmax(0, 1fr);
  align-items: start;
  gap: var(--md-spacing-4);
}

.settings-console__nav {
  position: sticky;
  top: var(--md-spacing-4);
  display: grid;
  gap: var(--md-spacing-2);
  align-self: start;
}

.settings-console__nav-item {
  display: grid;
  gap: 4px;
  width: 100%;
  padding: var(--md-spacing-3);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-lg);
  background-color: var(--md-surface-container-low);
  color: var(--md-on-surface);
  text-align: left;
  transition:
    background-color 160ms ease,
    border-color 160ms ease;
}

.settings-console__nav-item:hover {
  border-color: var(--md-outline);
  background-color: var(--md-surface-container);
}

.settings-console__nav-item:focus-visible,
.settings-console__mobile-tab:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}

.settings-console__nav-item.is-active,
.settings-console__nav-item[aria-current='page'] {
  border-color: var(--md-primary);
  background-color: var(--md-primary-container);
  color: var(--md-on-primary-container);
}

.settings-console__nav-item-label {
  font-size: var(--md-title-small);
  font-weight: 600;
}

.settings-console__nav-item-description {
  font-size: var(--md-body-small);
  color: var(--md-on-surface-variant);
}

.settings-console__nav-item.is-active .settings-console__nav-item-description,
.settings-console__nav-item[aria-current='page'] .settings-console__nav-item-description {
  color: inherit;
}

.settings-panel {
  min-width: 0;
  border-radius: var(--md-radius-xl);
  padding: var(--md-spacing-4);
  overflow: visible;
}

.settings-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--md-spacing-3);
  margin-bottom: var(--md-spacing-4);
}

.settings-panel__eyebrow {
  margin: 0 0 4px;
  color: var(--md-on-surface-variant);
}

.settings-panel__title {
  margin: 0;
  color: var(--md-on-surface);
}

.settings-panel__description {
  max-width: 34ch;
  margin: 4px 0 0;
  color: var(--md-on-surface-variant);
  text-align: right;
}

.settings-console__mobile-tabs {
  display: none;
  gap: var(--md-spacing-2);
  margin-bottom: var(--md-spacing-3);
  overflow-x: auto;
  padding-bottom: 2px;
}

.settings-console__mobile-tab {
  flex: 0 0 auto;
  min-height: 44px;
  padding: 8px 14px;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-full);
  background-color: var(--md-surface-container-low);
  color: var(--md-on-surface);
  white-space: nowrap;
}

.settings-console__mobile-tab.is-active,
.settings-console__mobile-tab[aria-current='page'] {
  border-color: var(--md-primary);
  background-color: var(--md-primary-container);
  color: var(--md-on-primary-container);
}

@media (max-width: 768px) {
  .settings-overview__top {
    align-items: flex-start;
    flex-direction: column;
  }

  .settings-console {
    grid-template-columns: minmax(0, 1fr);
  }

  .settings-console__nav {
    display: none;
  }

  .settings-console__mobile-tabs {
    display: flex;
  }

  .settings-panel__header {
    flex-direction: column;
  }

  .settings-panel__description {
    max-width: none;
    text-align: left;
  }
}
</style>
