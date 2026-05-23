<!-- AIMETA P=概览区_小说基本信息|R=基本信息展示|NR=不含编辑功能|E=component:OverviewSection|X=ui|A=概览组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="archive-overview">
    <!-- 将“核心摘要/项目定位”与“四栏格物屏风表”融合成一整张古籍卡片 -->
    <section class="archive-overview__summary-panel">
      <div class="archive-overview__summary-main">
        <div class="archive-overview__section-head">
          <div>
            <p class="archive-overview__kicker">核心摘要</p>
            <h2 class="archive-overview__title">项目定位</h2>
          </div>
          <!-- 极简无边框阴影编辑按钮 -->
          <button
            v-if="editable"
            type="button"
            class="archive-overview__edit-btn"
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
      </div>

      <!-- 格物分栏作为大卡片下半部分，共享外边框，用 1px 竹青线隔开 -->
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
    </section>

    <!-- 完整剧情梗概作为第二张同样样式的大卡片 -->
    <section class="archive-overview__synopsis">
      <div class="archive-overview__section-head">
        <div>
          <p class="archive-overview__kicker">剧情材料</p>
          <h2 class="archive-overview__title">完整剧情梗概</h2>
        </div>
        <!-- 极简无边框阴影编辑按钮 -->
        <button
          v-if="editable"
          type="button"
          class="archive-overview__edit-btn"
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
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-6);
  width: 100%;
}

/* 融为一体的核心定位与格物大卡片，以及剧情梗概卡片 */
.archive-overview__summary-panel,
.archive-overview__synopsis {
  border: 3px double var(--md-outline); /* 古籍线装本特有双线边框 */
  border-radius: 4px; /* 极微方折圆角 */
  background-color: var(--md-surface); /* 熟宣底色 */
  box-shadow: 2px 2px 0px rgba(28, 32, 34, 0.15); /* 拓片硬投影 */
  overflow: hidden;
  transition: all 0.2s cubic-bezier(0.2, 0, 0, 1);
}

.archive-overview__summary-panel:hover,
.archive-overview__synopsis:hover {
  box-shadow: 3px 3px 0px rgba(28, 32, 34, 0.2);
}

/* 二合一卡片上半部分的 padding */
.archive-overview__summary-main {
  padding: var(--md-spacing-6) clamp(var(--md-spacing-4), 4vw, var(--md-spacing-7)) var(--md-spacing-5);
}

/* 剧情梗概卡片的 padding */
.archive-overview__synopsis {
  padding: var(--md-spacing-6) clamp(var(--md-spacing-4), 4vw, var(--md-spacing-7));
}

.archive-overview__section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--md-spacing-4);
  margin-bottom: var(--md-spacing-4);
}

.archive-overview__kicker {
  margin: 0 0 var(--md-spacing-2);
  color: var(--md-primary-light);
  font-family: STSong, Songti SC, Noto Serif CJK SC, Source Han Serif SC, serif;
  font-size: var(--md-label-medium);
  font-weight: 600;
  letter-spacing: 0.15em;
  border-bottom: 1.5px solid var(--md-outline-variant); /* 墨晕分割线 */
  padding-bottom: 2px;
  display: inline-block;
}

.archive-overview__title {
  position: relative;
  margin: var(--md-spacing-2) 0 0;
  color: var(--md-primary-dark);
  font-family: STSong, Songti SC, Noto Serif CJK SC, Source Han Serif SC, serif;
  font-size: var(--md-title-large);
  font-weight: 600;
  line-height: 1.3;
  letter-spacing: 0.05em; /* 碑拓骨力字间距 */
  padding-left: var(--md-spacing-3);
}

/* 标题左侧朱砂红竖批描红 */
.archive-overview__title::before {
  content: "";
  position: absolute;
  left: 0;
  top: 15%;
  bottom: 15%;
  width: 3px;
  background-color: var(--md-secondary);
  border-radius: 1px;
}

/* 极简精致、不喧宾夺主的编辑按钮 */
.archive-overview__edit-btn {
  flex: 0 0 auto;
  border: none;
  background: transparent;
  color: var(--md-on-surface-variant);
  cursor: pointer;
  width: 2.25rem;
  height: 2.25rem;
  display: grid;
  place-items: center;
  border-radius: 50%;
  transition: all 0.2s ease;
}

.archive-overview__edit-btn:hover {
  color: var(--md-primary-dark);
  background-color: var(--md-surface-container);
}

.archive-overview__lead {
  max-width: 72ch;
  min-height: 2.5rem;
  margin: 0;
  color: var(--md-primary-dark); /* 焦墨正文 */
  font-family: Noto Sans SC, sans-serif;
  font-size: 16px;
  line-height: 1.8;
  font-weight: 450;
}

/* 融合成大卡片下半部分的四栏格物屏风表 */
.archive-overview__metadata {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  margin: 0;
  border-top: 1.5px solid var(--md-outline); /* 上部以一根挺拔竹青线隔开 */
  background-color: var(--md-surface-container-low); /* 温润竹纸底色 */
}

.archive-overview__meta-item {
  position: relative;
  min-width: 0;
  padding: var(--md-spacing-5) var(--md-spacing-4);
  background-color: transparent;
  border-right: 1px solid var(--md-outline-variant); /* 墨晕细线内分割 */
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-2.5);
  transition: background-color 0.2s ease;
}

.archive-overview__meta-item:hover {
  background-color: color-mix(in srgb, var(--md-surface) 40%, transparent);
}

.archive-overview__meta-item:last-child {
  border-right: none;
}

.archive-overview__meta-item dt {
  margin: 0;
  color: var(--md-primary-light);
  font-family: STSong, Songti SC, Noto Serif CJK SC, Source Han Serif SC, serif;
  font-size: var(--md-label-medium);
  font-weight: 600;
  letter-spacing: 0.1em;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.archive-overview__meta-item dt::before {
  content: "◇"; /* 朱砂细印徽志 */
  color: var(--md-secondary);
  font-size: 10px;
  font-weight: 700;
}

.archive-overview__meta-item dd {
  min-height: 1.5rem;
  margin: 0;
  color: var(--md-primary-dark);
  font-family: Noto Sans SC, sans-serif;
  font-size: var(--md-body-medium);
  font-weight: 500;
  line-height: 1.6;
  overflow-wrap: break-word;
}

.archive-overview__prose {
  max-width: 75ch;
  color: var(--md-primary-light);
  font-family: Noto Sans SC, sans-serif;
  font-size: 15px;
  line-height: 1.85; /* 行气舒展 */
  white-space: pre-line;
}

.archive-overview__prose p {
  margin: 0;
  text-indent: 2em; /* 首行空两格 */
}

.archive-overview__lead.is-empty,
.archive-overview__prose.is-empty {
  color: var(--md-on-surface-variant);
  font-style: italic;
  opacity: 0.7;
}

@media (max-width: 1024px) {
  .archive-overview__metadata {
    grid-template-columns: repeat(2, 1fr);
  }
  .archive-overview__meta-item:nth-child(2) {
    border-right: none;
  }
  .archive-overview__meta-item:nth-child(1),
  .archive-overview__meta-item:nth-child(2) {
    border-bottom: 1px solid var(--md-outline-variant);
  }
}

@media (max-width: 560px) {
  .archive-overview {
    gap: var(--md-spacing-4);
  }

  .archive-overview__summary-panel,
  .archive-overview__synopsis {
    padding: 0;
  }

  .archive-overview__summary-main,
  .archive-overview__synopsis {
    padding: var(--md-spacing-4);
  }

  .archive-overview__metadata {
    grid-template-columns: 1fr;
    border-top: 1.5px solid var(--md-outline);
  }
  
  .archive-overview__meta-item {
    border-right: none;
    border-bottom: 1px solid var(--md-outline-variant);
    padding: var(--md-spacing-4);
  }
  
  .archive-overview__meta-item:last-child {
    border-bottom: none;
  }
}
</style>
