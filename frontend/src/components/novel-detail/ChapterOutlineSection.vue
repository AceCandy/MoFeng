<!-- AIMETA P=章节大纲区_大纲展示|R=大纲列表|NR=不含编辑功能|E=component:ChapterOutlineSection|X=ui|A=大纲组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="blueprint-page chapter-outline-section">
    <header class="blueprint-section-header">
      <div class="blueprint-section-header__main">
        <span class="blueprint-section-header__icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M8 6h13M8 12h13M8 18h13" />
            <path d="M3 6h.01M3 12h.01M3 18h.01" />
          </svg>
        </span>
        <div class="blueprint-section-header__text">
          <p class="blueprint-kicker">结构档案</p>
          <h2 class="blueprint-title">章节大纲</h2>
          <p class="blueprint-subtitle">按章节查看故事推进、节奏节点与内容摘要，便于写作台定位下一章。</p>
        </div>
      </div>
      <div v-if="editable" class="blueprint-action-row">
        <button
          type="button"
          class="blueprint-button blueprint-button--primary"
          @click="$emit('add')"
        >
          <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path fill-rule="evenodd" d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" clip-rule="evenodd" />
          </svg>
          新增章节
        </button>
        <button
          type="button"
          class="blueprint-button"
          @click="emitEdit('chapter_outline', '章节大纲', outline)"
        >
          <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
            <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
          </svg>
          编辑大纲
        </button>
      </div>
    </header>

    <ol v-if="outline.length" class="chapter-outline-section__list">
      <li
        v-for="chapter in outline"
        :key="chapter.chapter_number"
        class="chapter-outline-section__item"
      >
        <span class="chapter-outline-section__number" aria-hidden="true">
          {{ chapter.chapter_number }}
        </span>
        <article class="chapter-outline-section__content">
          <div class="chapter-outline-section__item-head">
            <h3 class="blueprint-item-title">{{ chapter.title || `第${chapter.chapter_number}章` }}</h3>
            <span class="blueprint-status">第 {{ chapter.chapter_number }} 章</span>
          </div>
          <p class="blueprint-item-meta chapter-outline-section__summary">
            {{ chapter.summary || '暂无摘要' }}
          </p>
        </article>
      </li>
    </ol>

    <div v-else class="blueprint-empty">
      <div>
        <p class="blueprint-empty__title">暂无章节大纲</p>
        <p class="blueprint-empty__desc">新增章节后，写作台会按照大纲安排下一步创作。</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
interface OutlineItem {
  chapter_number: number
  title: string
  summary: string
}

const props = defineProps<{
  outline: OutlineItem[]
  editable?: boolean
}>()

const emit = defineEmits<{
  (e: 'edit', payload: { field: string; title: string; value: any }): void
  (e: 'add'): void
}>()

const emitEdit = (field: string, title: string, value: any) => {
  if (!props.editable) return
  emit('edit', { field, title, value })
}
</script>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'ChapterOutlineSection',
})
</script>

<style scoped>
.chapter-outline-section__list {
  display: grid;
  gap: var(--md-spacing-4);
  margin: 0;
  padding: 0;
  list-style: none;
}

.chapter-outline-section__item {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr);
  gap: var(--md-spacing-4);
  align-items: start;
}

.chapter-outline-section__number {
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border: 1px solid var(--md-outline);
  border-radius: var(--md-radius-xs);
  background-color: var(--md-primary);
  color: var(--md-on-primary);
  font-family: var(--md-font-display);
  font-weight: 700;
  box-shadow: 2px 2px 0px rgba(28, 32, 34, 0.12);
}

.chapter-outline-section__content {
  min-width: 0;
  padding: var(--md-spacing-5);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-sm);
  background-color: var(--md-surface-container-low);
}

.chapter-outline-section__item-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--md-spacing-3);
}

.chapter-outline-section__summary {
  margin-top: var(--md-spacing-3);
  line-height: 1.75;
  white-space: pre-line;
}

@media (max-width: 560px) {
  .chapter-outline-section__item {
    grid-template-columns: 1fr;
    gap: var(--md-spacing-2);
  }

  .chapter-outline-section__item-head {
    flex-direction: column;
  }
}
</style>
