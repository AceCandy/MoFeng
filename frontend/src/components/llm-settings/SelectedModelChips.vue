<template>
  <!-- 已选模型 chip 列表：按能力分区显示已启用模型，含 主/用/读 印记与删除按钮 -->
  <div class="model-routing__selected-models">
    <p class="md-label-medium model-routing__model-list-title">
      {{
        activeSection === 'llm'
          ? '已选文本生成模型'
          : activeSection === 'embedding'
            ? '已选检索模型'
            : '已选语音朗读模型'
      }}
    </p>
    <p v-if="chips.length === 0" class="model-routing__empty">
      点击"拉取模型"后勾选模型。
    </p>
    <div v-else class="model-routing__selected-chip-list">
      <span
        v-for="chip in chips"
        :key="chip.id"
        class="model-routing__selected-chip"
      >
        <span class="model-routing__chip-name">{{ chip.display_name || chip.model_name }}</span>
        <small v-if="activeSection === 'llm' && chip.is_default_chat" class="model-routing__stamp-label">主</small>
        <small v-else-if="activeSection === 'embedding' && chip.is_default_embedding" class="model-routing__stamp-label">用</small>
        <small v-else-if="activeSection === 'tts' && chip.is_default_tts" class="model-routing__stamp-label">读</small>
        <button
          type="button"
          class="model-routing__delete-btn"
          :aria-label="`删除模型 ${chip.display_name || chip.model_name}`"
          :title="`删除模型 ${chip.display_name || chip.model_name}`"
          @click="emit('delete', chip.model_name)"
        >
          删除
        </button>
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { UserAIModel } from '@/api/llm'
import type { RoutingSection } from './modelRoutingTypes'

defineProps<{
  chips: UserAIModel[]
  activeSection: RoutingSection
}>()

const emit = defineEmits<{
  (event: 'delete', modelName: string): void
}>()
</script>

<style scoped>
.model-routing__selected-models {
  display: grid;
  gap: var(--md-spacing-3);
}

.model-routing__model-list-title {
  margin: 0;
  color: var(--md-on-surface-variant);
}

/* empty 共用样式（复制自父；picker/empty-state 仍消费父规则） */
.model-routing__empty {
  margin: 4px 0 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.model-routing__selected-chip-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: var(--md-spacing-2);
}

/* 合并原父「picker-head/picker-row/selected-chip 混合 flex」的 gap 与独立 selected-chip 定义 */
.model-routing__selected-chip {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--md-spacing-3);
  min-height: 38px;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-xs);
  padding: 6px 8px 6px 12px;
  background: var(--md-surface-container);
  color: var(--md-on-surface);
  box-shadow: 1px 1px 0px rgba(28, 32, 34, 0.04);
  transition:
    background-color var(--md-duration-short) var(--md-easing-standard),
    border-color var(--md-duration-short) var(--md-easing-standard),
    box-shadow var(--md-duration-short) var(--md-easing-standard),
    color var(--md-duration-short) var(--md-easing-standard),
    opacity var(--md-duration-short) var(--md-easing-standard),
    transform var(--md-duration-short) var(--md-easing-standard);
  cursor: default;
}

.model-routing__selected-chip:hover {
  background: var(--md-surface-container-high);
  border-color: var(--md-outline);
  box-shadow: 2px 2px 0px rgba(28, 32, 34, 0.1);
}

.model-routing__selected-chip > span.model-routing__chip-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--md-body-small);
  padding-right: 18px; /* 固定右内边距，为删除按钮预留空间，静止稳定且无 layout-transition 隐患 */
  flex: 1 1 0%;
}

.model-routing__selected-chip .model-routing__stamp-label {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 1px;
  padding: 1px 4px;
  background: var(--md-secondary);
  color: var(--md-on-primary);
  font-family: var(--md-font-display);
  font-size: 10px;
  font-weight: 700;
  line-height: 1;
  letter-spacing: 0.03em;
  white-space: nowrap;
  border: 1px solid rgba(184, 60, 50, 0.2);
  margin-left: 4px;
  box-shadow: 1px 1px 0px rgba(184, 60, 50, 0.15);
  flex-shrink: 0;
}

.model-routing__delete-btn {
  position: absolute;
  right: 6px;
  top: 50%;
  transform: translateY(-50%) scale(0.8);
  border: none;
  background: transparent;
  color: var(--md-secondary);
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  pointer-events: none;
  transition:
    background-color var(--md-duration-short) var(--md-easing-standard),
    border-color var(--md-duration-short) var(--md-easing-standard),
    box-shadow var(--md-duration-short) var(--md-easing-standard),
    color var(--md-duration-short) var(--md-easing-standard),
    opacity var(--md-duration-short) var(--md-easing-standard),
    transform var(--md-duration-short) var(--md-easing-standard);
  border-radius: var(--md-radius-xs);
}

.model-routing__delete-btn::before {
  content: '';
  position: absolute;
  top: -11px;
  bottom: -11px;
  left: -11px;
  right: -11px;
}

.model-routing__selected-chip:hover .model-routing__delete-btn {
  opacity: 1;
  transform: translateY(-50%) scale(1);
  pointer-events: auto;
}

.model-routing__delete-btn:hover {
  color: var(--md-error);
  transform: translateY(-50%) scale(1.15) !important;
  text-shadow: 1px 1px 0px rgba(184, 60, 50, 0.2);
}

.model-routing__delete-btn:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}
</style>
