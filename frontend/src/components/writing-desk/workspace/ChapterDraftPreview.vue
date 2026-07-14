<template>
  <article class="chapter-console__preview-card">
    <header>
      <h4>实时草稿预览</h4>
      <span>{{ previewModeLabel }}</span>
    </header>

    <div v-if="previewParagraphs.length > 0" class="chapter-console__preview-body">
      <p
        v-for="(paragraph, index) in previewParagraphs"
        :key="`preview-${index}`"
        :class="{ 'is-streaming': index === previewParagraphs.length - 1 }"
      >
        {{ paragraph }}
        <span
          v-if="index === previewParagraphs.length - 1"
          class="chapter-console__cursor"
          aria-hidden="true"
        >
          ▍
        </span>
      </p>
    </div>

    <div v-else class="chapter-console__strategy-placeholder">
      <p class="chapter-console__strategy-title">本章生成策略摘要</p>
      <ul>
        <li>基于本章任务与摘要先生成冲突主线，再补充人物情绪层。</li>
        <li>优先对齐前文角色状态，避免重复解释既有设定。</li>
        <li>保留原章节内容，新草稿以新版本形式保存，便于对比采纳。</li>
      </ul>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  chapterContentPreview?: string | null
}

const props = withDefaults(defineProps<Props>(), {
  chapterContentPreview: '',
})

const previewParagraphs = computed(() => {
  const raw = (props.chapterContentPreview || '').trim()
  if (!raw) return []
  return raw
    .split(/\n{2,}/)
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 3)
})

const previewModeLabel = computed(() => {
  if (previewParagraphs.value.length > 0) {
    return '已生成片段，正在生成下一段'
  }
  return '暂未生成正文，先展示策略摘要'
})
</script>

<style scoped>
/* 卡片骨架：源自 ChapterGenerating 与其余 card 共享的 border/radius/bg/shadow/padding/h4，
   scoped 隔离下父组件选择器不再作用于本组件元素，故在此重复声明 */
.chapter-console__preview-card {
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-sm);
  background: color-mix(in srgb, var(--md-surface) 96%, transparent);
  box-shadow: var(--md-elevation-1);
  padding: var(--md-spacing-4);
}

.chapter-console__preview-card h4 {
  margin: 0;
  color: var(--md-on-surface);
  font-size: var(--md-title-medium);
}

.chapter-console__preview-card header {
  display: flex;
  justify-content: space-between;
  gap: var(--md-spacing-2);
  align-items: center;
}

.chapter-console__preview-card header span {
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.chapter-console__preview-body {
  margin-top: var(--md-spacing-3);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-md);
  background-color: var(--md-surface-container-low);
  padding: var(--md-spacing-3);
}

.chapter-console__preview-body p {
  margin: 0;
  color: var(--md-on-surface);
  line-height: 1.75;
}

.chapter-console__preview-body p + p {
  margin-top: var(--md-spacing-3);
}

.chapter-console__preview-body p.is-streaming {
  color: color-mix(in srgb, var(--md-on-surface) 92%, var(--md-primary-dark));
}

.chapter-console__cursor {
  margin-left: 2px;
  color: var(--md-primary-dark);
  animation: blink-cursor 1s steps(2, end) infinite;
}

.chapter-console__strategy-placeholder {
  margin-top: var(--md-spacing-3);
  border: 1px dashed color-mix(in srgb, var(--md-primary) 28%, var(--md-outline-variant));
  border-radius: var(--md-radius-md);
  padding: var(--md-spacing-3);
  background-color: color-mix(in srgb, var(--md-primary-container) 48%, var(--md-surface));
}

.chapter-console__strategy-title {
  margin: 0;
  color: var(--md-on-primary-container);
  font-size: var(--md-label-large);
  font-weight: 700;
}

.chapter-console__strategy-placeholder ul {
  margin: var(--md-spacing-2) 0 0;
  padding-left: 1.2rem;
  color: var(--md-on-surface-variant);
}

.chapter-console__strategy-placeholder li + li {
  margin-top: 6px;
}

@keyframes blink-cursor {
  0%,
  49% {
    opacity: 1;
  }

  50%,
  100% {
    opacity: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .chapter-console__cursor {
    animation: none;
  }
}
</style>
