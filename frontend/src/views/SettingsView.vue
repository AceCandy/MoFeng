<!-- AIMETA P=设置页_用户设置|R=用户设置表单|NR=不含管理员设置|E=route:/settings#component:SettingsView|X=ui|A=设置表单|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="min-h-screen md-surface-dim settings-page">
    <div class="settings-content mx-auto flex w-full max-w-7xl flex-col px-4 md:px-6">
      <section v-if="showInspirationConfigNotice" class="md-card settings-notice">
        <p class="md-title-small">灵感模式需要先完成模型配置</p>
        <p class="md-body-small mt-1">
          请先在 <strong>文本生成</strong> 中启用模型并指定主模型，保存后会自动跳回灵感模式。
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
            :title="section.description"
            @click="selectSettingsSection(section.id)"
          >
            <span class="settings-console__nav-item-label">{{ section.label }}</span>
          </button>
        </nav>

        <section class="settings-panel">
          <PersonalModelRouting
            v-if="activeSettingsSection === 'llm'"
            active-section="llm"
            @saved="handleLLMConfigSaved"
            @navigate="selectSettingsSection"
          />
          <PersonalModelRouting
            v-else-if="activeSettingsSection === 'embedding'"
            active-section="embedding"
            @saved="handleLLMConfigSaved"
            @navigate="selectSettingsSection"
          />
          <PersonalModelRouting
            v-else
            active-section="routes"
            @saved="handleLLMConfigSaved"
            @navigate="selectSettingsSection"
          />
        </section>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PersonalModelRouting from '@/components/llm-settings/PersonalModelRouting.vue'

type SettingsSectionId = 'llm' | 'embedding' | 'routes'

interface SettingsSection {
  id: SettingsSectionId
  label: string
  description: string
}

const route = useRoute()
const router = useRouter()
const settingsSections: SettingsSection[] = [
  { id: 'llm', label: '文本生成', description: '供应商、模型拉取与主模型' },
  { id: 'embedding', label: '记忆检索', description: '向量供应商与唯一检索模型' },
  { id: 'routes', label: '阶段路由', description: '按创作阶段覆盖主模型' },
]

const activeSettingsSection = ref<SettingsSectionId>('llm')

const selectSettingsSection = (sectionId: SettingsSectionId) => {
  activeSettingsSection.value = sectionId
}

const showInspirationConfigNotice = computed(
  () => route.query.source === 'inspiration' && route.query.reason === 'missing_models',
)

const handleLLMConfigSaved = async () => {
  if (!showInspirationConfigNotice.value) {
    return
  }
  await router.push('/inspiration')
}
</script>

<style scoped>
.settings-page {
  background-color: var(--md-surface-dim);
}

.settings-content {
  gap: var(--md-spacing-3);
  padding-top: var(--md-spacing-4);
  padding-bottom: var(--md-spacing-6);
}

.settings-notice {
  border-radius: var(--md-radius-lg);
  padding: var(--md-spacing-4);
  border: 1px solid color-mix(in srgb, var(--md-warning) 35%, var(--md-outline-variant));
  background-color: var(--md-warning-container);
  color: var(--md-on-warning-container);
}

.settings-console {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--md-spacing-4);
}

.settings-console__nav {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--md-spacing-1);
  width: 100%;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-full);
  padding: var(--md-spacing-1);
  background-color: var(--md-surface-container-low);
}

.settings-console__nav-item {
  display: inline-flex;
  width: 100%;
  min-width: 0;
  align-items: center;
  justify-content: center;
  min-height: 40px;
  padding: 0 var(--md-spacing-3);
  border: none;
  border-radius: var(--md-radius-full);
  background-color: transparent;
  color: var(--md-on-surface);
  white-space: nowrap;
  transition:
    background-color 160ms ease,
    color 160ms ease;
}

.settings-console__nav-item:hover {
  background-color: var(--md-surface-container);
}

.settings-console__nav-item:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}

.settings-console__nav-item.is-active,
.settings-console__nav-item[aria-current='page'] {
  background-color: var(--md-primary-container);
  color: var(--md-on-primary-container);
}

.settings-console__nav-item-label {
  font-size: var(--md-title-small);
  font-weight: 600;
}

.settings-panel {
  min-width: 0;
  padding: 0;
  overflow: visible;
}

@media (max-width: 768px) {
  .settings-content {
    padding-top: var(--md-spacing-4);
  }

  .settings-console__nav {
    width: 100%;
  }
}
</style>
