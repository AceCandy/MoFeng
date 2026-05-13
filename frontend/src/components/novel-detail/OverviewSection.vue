<!-- AIMETA P=概览区_小说基本信息|R=基本信息展示|NR=不含编辑功能|E=component:OverviewSection|X=ui|A=概览组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="archive-overview">
    <section class="archive-overview__summary">
      <div class="archive-overview__section-head">
        <div>
          <p class="archive-overview__kicker">核心摘要</p>
          <h2 class="archive-overview__title">项目定位</h2>
        </div>
        <button
          v-if="editable"
          type="button"
          class="md-icon-btn archive-overview__edit"
          aria-label="编辑核心摘要"
          @click="emitEdit('one_sentence_summary', '核心摘要', data?.one_sentence_summary)">
          <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
            <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
          </svg>
        </button>
      </div>
      <p class="archive-overview__lead" :class="{ 'is-empty': !data?.one_sentence_summary }">
        {{ data?.one_sentence_summary || '暂无核心摘要' }}
      </p>
    </section>

    <dl class="archive-overview__metadata" aria-label="项目元信息">
      <div class="archive-overview__meta-item">
        <dt>目标受众</dt>
        <dd>{{ data?.target_audience || '暂无' }}</dd>
      </div>
      <div class="archive-overview__meta-item">
        <dt>类型</dt>
        <dd>{{ data?.genre || '暂无' }}</dd>
      </div>
      <div class="archive-overview__meta-item">
        <dt>风格</dt>
        <dd>{{ data?.style || '暂无' }}</dd>
      </div>
      <div class="archive-overview__meta-item">
        <dt>基调</dt>
        <dd>{{ data?.tone || '暂无' }}</dd>
      </div>
    </dl>

    <section class="archive-overview__synopsis">
      <div class="archive-overview__section-head">
        <div>
          <p class="archive-overview__kicker">剧情材料</p>
          <h2 class="archive-overview__title">完整剧情梗概</h2>
        </div>
        <button
          v-if="editable"
          type="button"
          class="md-icon-btn archive-overview__edit"
          aria-label="编辑完整剧情梗概"
          @click="emitEdit('full_synopsis', '完整剧情梗概', data?.full_synopsis)">
          <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
            <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
          </svg>
        </button>
      </div>
      <div class="archive-overview__prose" :class="{ 'is-empty': !data?.full_synopsis }">
        <p>{{ data?.full_synopsis || '暂无完整剧情梗概' }}</p>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">

interface OverviewData {
  one_sentence_summary?: string | null
  target_audience?: string | null
  genre?: string | null
  style?: string | null
  tone?: string | null
  full_synopsis?: string | null
}

const props = defineProps<{
  data: OverviewData | null
  editable?: boolean
}>()

const emit = defineEmits<{
  (e: 'edit', payload: { field: string; title: string; value: any }): void
}>()

const emitEdit = (field: string, title: string, value: any) => {
  if (!props.editable) return
  emit('edit', { field, title, value })
}
</script>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'OverviewSection'
})
</script>

<style scoped>
.archive-overview {
  display: grid;
  gap: var(--md-spacing-6);
  width: 100%;
}

.archive-overview__summary,
.archive-overview__synopsis {
  padding: var(--md-spacing-6);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-lg);
  background-color: var(--md-surface);
}

.archive-overview__summary {
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--md-primary-container) 34%, transparent),
      transparent 56%
    ),
    var(--md-surface);
}

.archive-overview__section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--md-spacing-4);
  margin-bottom: var(--md-spacing-4);
}

.archive-overview__kicker {
  margin: 0 0 var(--md-spacing-1);
  color: var(--md-primary-dark);
  font-size: var(--md-label-medium);
  font-weight: 600;
}

.archive-overview__title {
  margin: 0;
  color: var(--md-on-surface);
  font-size: var(--md-title-large);
  font-weight: 600;
  line-height: 1.3;
}

.archive-overview__edit {
  flex: 0 0 auto;
  color: var(--md-on-surface-variant);
}

.archive-overview__edit:hover {
  color: var(--md-primary-dark);
}

.archive-overview__lead {
  max-width: 72ch;
  min-height: 2.5rem;
  margin: 0;
  color: var(--md-on-surface);
  font-size: var(--md-body-large);
  line-height: 1.75;
}

.archive-overview__metadata {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: var(--md-spacing-3);
  margin: 0;
}

.archive-overview__meta-item {
  min-width: 0;
  padding: var(--md-spacing-4);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-md);
  background-color: var(--md-surface-container-low);
}

.archive-overview__meta-item dt {
  margin: 0 0 var(--md-spacing-2);
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-medium);
  font-weight: 600;
}

.archive-overview__meta-item dd {
  min-height: 1.5rem;
  margin: 0;
  color: var(--md-on-surface);
  font-size: var(--md-body-medium);
  font-weight: 500;
  line-height: 1.7;
  overflow-wrap: normal;
  word-break: normal;
}

.archive-overview__prose {
  max-width: 75ch;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-medium);
  line-height: 1.8;
  white-space: pre-line;
}

.archive-overview__prose p {
  margin: 0;
}

.archive-overview__lead.is-empty,
.archive-overview__prose.is-empty {
  color: var(--md-on-surface-variant);
}

@media (max-width: 560px) {
  .archive-overview {
    gap: var(--md-spacing-4);
  }

  .archive-overview__summary,
  .archive-overview__synopsis {
    padding: var(--md-spacing-4);
  }

  .archive-overview__metadata {
    grid-template-columns: 1fr;
  }
}
</style>
