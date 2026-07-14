<template>
  <div class="chapter-console__failed-container">

    <div v-if="failedVersionCards.length" class="chapter-console__failed-versions" aria-label="已保留候选版本">
      <div class="chapter-console__failed-versions-head">
        <div>
          <span class="chapter-console__failed-versions-kicker">保留草稿</span>
          <h5>本轮候选版本仍可查看</h5>
        </div>
        <p>AI 评审失败不会清空已生成的正文，可先打开候选版本核对内容，再决定重试评审或重新生成。</p>
      </div>
      <div class="chapter-console__failed-version-grid">
        <button
          v-for="item in failedVersionCards"
          :key="`failed-version-${item.index}`"
          type="button"
          class="chapter-console__failed-version-card"
          :aria-label="`候选版本 ${item.displayIndex}，双击查看详情`"
          @dblclick="emit('showVersionDetail', item.index)"
        >
          <span class="chapter-console__failed-version-title">版本 {{ item.displayIndex }}</span>
          <span class="chapter-console__failed-version-meta">{{ item.wordCount }} 字 · {{ item.style }}</span>
          <span class="chapter-console__failed-version-preview">{{ item.preview }}</span>
          <span class="chapter-console__failed-version-action">双击查看正文</span>
        </button>
      </div>
    </div>

    <div class="chapter-console__failed-actions">
      <button
        v-if="status === 'evaluation_failed'"
        type="button"
        @click="emit('evaluateChapter')"
        class="md-btn md-btn-filled md-ripple"
      >
        重新 AI评审
      </button>
      <button
        type="button"
        @click="emit('failedGenerateAction')"
        :disabled="generatingChapter === chapterNumber"
        :class="[
          'md-btn md-ripple disabled:opacity-50',
          status === 'evaluation_failed'
            ? 'md-btn-outlined chapter-console__danger-action'
            : 'md-btn-filled',
        ]"
      >
        {{ generatingChapter === chapterNumber ? '重试中...' : retryGenerateLabel }}
      </button>
    </div>

  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { FailedVersionCard, GenerationStatus } from '@/composables/useGenerationFailure'

interface Props {
  status: GenerationStatus | null
  failedVersionCards: FailedVersionCard[]
  generatingChapter?: number | null
  chapterNumber: number | null
}

const props = withDefaults(defineProps<Props>(), {
  generatingChapter: null,
})

const emit = defineEmits<{
  showVersionDetail: [index: number]
  evaluateChapter: []
  failedGenerateAction: []
}>()

const retryGenerateLabel = computed(() =>
  props.status === 'evaluation_failed' ? '放弃本轮草稿并重新生成' : '整章重新生成',
)
</script>

<style scoped>
/* 失败状态容器样式 */
.chapter-console__failed-container {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-4);
}

@media (max-width: 833px) {
  .chapter-console__failed-versions-head {
    flex-direction: column;
  }
}

.chapter-console__failed-actions {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--md-spacing-2);
}

.chapter-console__failed-actions .md-btn {
  min-height: 40px;
}

.chapter-console__failed-actions .chapter-console__danger-action {
  border-color: color-mix(in srgb, var(--md-error) 42%, var(--md-outline));
  color: var(--md-error);
}

.chapter-console__failed-versions {
  border: 1px solid color-mix(in srgb, var(--md-outline) 72%, var(--md-surface));
  border-radius: var(--md-radius-sm);
  background: color-mix(in srgb, var(--md-surface-container-low) 72%, var(--md-surface));
  padding: var(--md-spacing-3);
}

.chapter-console__failed-versions-head {
  display: flex;
  justify-content: space-between;
  gap: var(--md-spacing-3);
  align-items: flex-start;
}

.chapter-console__failed-versions-head h5 {
  margin: 2px 0 0;
  color: var(--md-on-surface);
  font-size: var(--md-title-small);
}

.chapter-console__failed-versions-head p {
  max-width: 680px;
  margin: 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
  line-height: 1.7;
}

.chapter-console__failed-versions-kicker {
  color: var(--md-error);
  font-size: var(--md-label-small);
  font-weight: 800;
}

.chapter-console__failed-version-grid {
  margin-top: var(--md-spacing-3);
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: var(--md-spacing-3);
}

.chapter-console__failed-version-card {
  min-height: 148px;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-xs);
  background: var(--md-surface);
  color: var(--md-on-surface);
  padding: var(--md-spacing-3);
  text-align: left;
  display: grid;
  gap: 6px;
  align-content: start;
  cursor: pointer;
  transition:
    border-color 160ms ease,
    background-color 160ms ease,
    transform 160ms ease;
}

.chapter-console__failed-version-card:hover,
.chapter-console__failed-version-card:focus-visible {
  border-color: color-mix(in srgb, var(--md-primary) 48%, var(--md-outline));
  background: color-mix(in srgb, var(--md-primary-container) 18%, var(--md-surface));
  transform: translateY(-1px);
  outline: none;
}

.chapter-console__failed-version-title {
  color: var(--md-on-surface);
  font-size: var(--md-title-small);
  font-weight: 800;
}

.chapter-console__failed-version-meta,
.chapter-console__failed-version-action {
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-small);
  font-weight: 700;
}

.chapter-console__failed-version-preview {
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
  line-height: 1.65;
}

.chapter-console__failed-version-action {
  color: var(--md-primary);
}
</style>
