<!-- AIMETA P=世界观区_世界设定展示|R=世界观信息|NR=不含编辑功能|E=component:WorldSettingSection|X=ui|A=世界观组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="blueprint-page world-setting-section">
    <header class="blueprint-section-header">
      <div class="blueprint-section-header__main">
        <span class="blueprint-section-header__icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="9" />
            <path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" />
          </svg>
        </span>
        <div class="blueprint-section-header__text">
          <p class="blueprint-kicker">世界蓝图</p>
          <h2 class="blueprint-title">世界设定</h2>
          <p class="blueprint-subtitle">集中查看故事规则、关键地点与主要阵营，保证后续章节不偏离基础设定。</p>
        </div>
      </div>
    </header>

    <section class="blueprint-panel blueprint-panel--paper">
      <div class="blueprint-panel__body world-setting-section__rules">
        <div class="world-setting-section__panel-head">
          <div>
            <p class="blueprint-kicker">核心规则</p>
            <h3 class="blueprint-item-title">故事运行边界</h3>
          </div>
          <button
            v-if="editable"
            type="button"
            class="blueprint-icon-action"
            aria-label="编辑核心规则"
            title="编辑核心规则"
            @click="emitEdit('world_setting.core_rules', '核心规则', worldSetting.core_rules)"
          >
            <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
              <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
            </svg>
          </button>
        </div>
        <p class="blueprint-prose" :class="{ 'world-setting-section__empty': !worldSetting.core_rules }">
          {{ worldSetting.core_rules || '暂无核心规则。' }}
        </p>
      </div>
    </section>

    <div class="blueprint-card-grid blueprint-card-grid--wide">
      <section class="blueprint-panel">
        <div class="blueprint-panel__body">
          <div class="world-setting-section__panel-head">
            <div>
              <p class="blueprint-kicker">空间材料</p>
              <h3 class="blueprint-item-title">关键地点</h3>
            </div>
            <button
              v-if="editable"
              type="button"
              class="blueprint-icon-action"
              aria-label="编辑关键地点"
              title="编辑关键地点"
              @click="emitEdit('world_setting.key_locations', '关键地点', worldSetting.key_locations)"
            >
              <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
                <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
              </svg>
            </button>
          </div>
          <ul v-if="locations.length" class="world-setting-section__list">
            <li v-for="(item, index) in locations" :key="`${item.title}-${index}`" class="blueprint-item-card">
              <strong class="blueprint-item-title">{{ item.title }}</strong>
              <span class="blueprint-item-meta">{{ item.description }}</span>
            </li>
          </ul>
          <div v-else class="blueprint-empty">
            <div>
              <p class="blueprint-empty__title">暂无地点</p>
              <p class="blueprint-empty__desc">补充地点后，章节生成会更容易保持空间连续性。</p>
            </div>
          </div>
        </div>
      </section>

      <section class="blueprint-panel">
        <div class="blueprint-panel__body">
          <div class="world-setting-section__panel-head">
            <div>
              <p class="blueprint-kicker">势力材料</p>
              <h3 class="blueprint-item-title">主要阵营</h3>
            </div>
            <button
              v-if="editable"
              type="button"
              class="blueprint-icon-action"
              aria-label="编辑主要阵营"
              title="编辑主要阵营"
              @click="emitEdit('world_setting.factions', '主要阵营', worldSetting.factions)"
            >
              <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
                <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
              </svg>
            </button>
          </div>
          <ul v-if="factions.length" class="world-setting-section__list">
            <li v-for="(item, index) in factions" :key="`${item.title}-${index}`" class="blueprint-item-card">
              <strong class="blueprint-item-title">{{ item.title }}</strong>
              <span class="blueprint-item-meta">{{ item.description }}</span>
            </li>
          </ul>
          <div v-else class="blueprint-empty">
            <div>
              <p class="blueprint-empty__title">暂无阵营</p>
              <p class="blueprint-empty__desc">补充阵营后，冲突、关系和伏笔会更容易归档。</p>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface ListItem {
  title: string
  description: string
}

const props = defineProps<{
  data: Record<string, any> | null
  editable?: boolean
}>()

const emit = defineEmits<{
  (e: 'edit', payload: { field: string; title: string; value: any }): void
}>()

const worldSetting = computed(() => props.data?.world_setting || {})

const normalizeList = (source: any): ListItem[] => {
  if (!source) return []
  if (Array.isArray(source)) {
    return source.map((item: any) => {
      if (typeof item === 'string') {
        const [title, ...rest] = item.split('：')
        return {
          title: title || item,
          description: rest.join('：') || '暂无描述',
        }
      }
      return {
        title: item?.name || item?.title || '未命名',
        description: item?.description || item?.details || '暂无描述',
      }
    })
  }
  return []
}

const locations = computed(() => normalizeList(worldSetting.value?.key_locations))
const factions = computed(() => normalizeList(worldSetting.value?.factions))

const emitEdit = (field: string, title: string, value: any) => {
  if (!props.editable) return
  emit('edit', { field, title, value })
}
</script>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'WorldSettingSection',
})
</script>

<style scoped>
.world-setting-section__rules {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-4);
}

.world-setting-section__panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--md-spacing-4);
  margin-bottom: var(--md-spacing-4);
}

.world-setting-section__list {
  display: grid;
  gap: var(--md-spacing-3);
  margin: 0;
  padding: 0;
  list-style: none;
}

.world-setting-section__list .blueprint-item-card {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-2);
}

.world-setting-section__empty {
  color: var(--md-on-surface-variant);
  font-style: italic;
}

@media (max-width: 640px) {
  .world-setting-section__panel-head {
    flex-direction: column;
  }
}
</style>
