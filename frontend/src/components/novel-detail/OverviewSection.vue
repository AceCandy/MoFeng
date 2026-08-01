<!-- AIMETA P=概览区_小说基本信息|R=基本信息展示|NR=不含编辑功能|E=component:OverviewSection|X=ui|A=概览组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="archive-overview blueprint-page">


    <div class="archive-overview__content-grid">
      <section class="blueprint-panel blueprint-panel--paper archive-overview__summary-panel">
        <div class="blueprint-panel__body archive-overview__summary-body">
          <div class="archive-overview__summary-copy">
            <div class="archive-overview__panel-head archive-overview__panel-head--inline">
              <div>
                <p class="blueprint-kicker">一句话定位</p>
                <h3 class="blueprint-item-title">故事核心判断</h3>
              </div>
              <button
                v-if="editable"
                type="button"
                class="blueprint-icon-action"
                aria-label="编辑核心摘要"
                title="编辑核心摘要"
                @click="emitEdit('one_sentence_summary', '核心摘要', data?.one_sentence_summary)"
              >
                <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                  <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
                  <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
                </svg>
              </button>
            </div>
            <p class="archive-overview__quote" :class="{ 'archive-overview__empty-text': !data?.one_sentence_summary }">
              {{ data?.one_sentence_summary || '暂无一句话定位。' }}
            </p>

            <!-- 横向平铺的大纲量化指标，去除右侧元数据已有的类型与基调，仅保留核心量化数据 -->
            <dl class="archive-overview__horizontal-metrics" aria-label="大纲核心指标">
              <div class="archive-overview__horizontal-metric">
                <dt>主要角色</dt>
                <dd>
                  <strong>{{ characterCount }}</strong>
                  <span>位登场人物</span>
                </dd>
              </div>
              <div class="archive-overview__horizontal-metric">
                <dt>大纲章节</dt>
                <dd>
                  <strong>{{ chapterCount }}</strong>
                  <span>章规划规模</span>
                </dd>
              </div>
            </dl>
          </div>

          <aside class="archive-overview__summary-aside" aria-label="蓝图资料状态">
            <div class="archive-overview__summary-footer">
              <span class="blueprint-kicker">{{ summaryStatus }}</span>
              <span>{{ updatedLabel }}</span>
            </div>
            <div class="archive-overview__readiness-grid">
              <article
                v-for="item in readinessItems"
                :key="item.kicker"
                class="archive-overview__readiness-card blueprint-panel"
              >
                <span
                  class="archive-overview__readiness-mark"
                  :class="`is-${item.tone}`"
                  :aria-label="item.toneLabel"
                >
                  {{ item.toneText }}
                </span>
                <div>
                  <p class="blueprint-kicker">{{ item.kicker }}</p>
                  <h4 class="blueprint-item-title">{{ item.label }}</h4>
                  <p class="blueprint-item-copy">{{ item.description }}</p>
                </div>
              </article>
            </div>
          </aside>
        </div>
      </section>

      <section class="blueprint-panel archive-overview__metadata-panel">
        <div class="blueprint-panel__body">
          <div class="archive-overview__panel-head">
            <div>
              <p class="blueprint-kicker">项目元信息</p>
              <h3 class="blueprint-item-title">基础资料</h3>
            </div>
          </div>
          <dl class="archive-overview__metadata" aria-label="项目元信息">
            <div
              v-for="item in metadataItems"
              :key="item.label"
              class="archive-overview__meta-row"
            >
              <dt>{{ item.label }}</dt>
              <dd :class="{ 'archive-overview__empty-text': !item.rawValue }">{{ item.value }}</dd>
            </div>
          </dl>
          <div
            class="archive-overview__completeness"
            role="meter"
            aria-label="基础资料完整度"
            :aria-valuenow="metadataCompletenessPercent"
            aria-valuemin="0"
            aria-valuemax="100"
            :style="{ '--archive-overview-completeness': `${metadataCompletenessPercent}%` }"
          >
            <div class="archive-overview__completeness-copy">
              <span>资料完整度</span>
              <strong>{{ filledMetadataCount }}/{{ metadataTotal }}</strong>
            </div>
            <span class="archive-overview__completeness-track" aria-hidden="true"></span>
          </div>
        </div>
      </section>
    </div>



    <section class="blueprint-panel blueprint-panel--paper archive-overview__synopsis-panel">
      <div class="blueprint-panel__body archive-overview__synopsis-body">
        <div class="archive-overview__panel-head">
          <div>
            <p class="blueprint-kicker">剧情材料</p>
            <h3 class="blueprint-item-title">完整剧情梗概</h3>
          </div>
          <button
            v-if="editable"
            type="button"
            class="blueprint-icon-action"
            aria-label="编辑完整剧情梗概"
            title="编辑完整剧情梗概"
            @click="emitEdit('full_synopsis', '完整剧情梗概', data?.full_synopsis)"
          >
            <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
              <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
            </svg>
          </button>
        </div>
        <div
          class="archive-overview__prose blueprint-prose"
          :class="{ 'archive-overview__empty-text': !data?.full_synopsis }"
        >
          <p>{{ data?.full_synopsis || '暂无完整剧情梗概。' }}</p>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { formatDateTime } from '@/utils/date'

interface OverviewData {
  one_sentence_summary?: string | null
  target_audience?: string | null
  genre?: string | null
  style?: string | null
  tone?: string | null
  full_synopsis?: string | null
  character_count?: number | null
  chapter_count?: number | null
  updated_at?: string | null
}

const props = withDefaults(
  defineProps<{
    data: OverviewData | null
    editable?: boolean
    characterCount?: number
    chapterCount?: number
  }>(),
  {
    editable: false,
    characterCount: 0,
    chapterCount: 0,
  }
)

const emit = defineEmits<{
  (e: 'edit', payload: { field: string; title: string; value: any }): void
}>()

// 元信息统一在脚本层兜底，模板只负责展示，避免多个 tab 的空值样式失控。
const metadataItems = computed(() =>
  [
    { label: '目标受众', rawValue: props.data?.target_audience },
    { label: '类型', rawValue: props.data?.genre },
    { label: '风格', rawValue: props.data?.style },
    { label: '基调', rawValue: props.data?.tone },
  ].map((item) => ({
    ...item,
    value: item.rawValue || '暂无',
  })),
)

const filledMetadataCount = computed(
  () => metadataItems.value.filter((item) => Boolean(item.rawValue)).length,
)
const metadataTotal = computed(() => metadataItems.value.length)
const metadataCompletenessPercent = computed(() =>
  metadataTotal.value
    ? Math.round((filledMetadataCount.value / metadataTotal.value) * 100)
    : 0,
)

const readinessItems = computed(() => [
  {
    kicker: '定位',
    label: props.data?.one_sentence_summary ? '摘要已落点' : '摘要待补充',
    description: props.data?.one_sentence_summary
      ? '故事方向已有一句话抓手，适合继续拆解角色和章节。'
      : '补充一句话定位后，后续分区会更容易保持同一叙事方向。',
    tone: props.data?.one_sentence_summary ? 'ready' : 'pending',
    toneText: props.data?.one_sentence_summary ? '成' : '待',
    toneLabel: props.data?.one_sentence_summary ? '已完成' : '待补充',
  },
  {
    kicker: '资料',
    label: metadataCompletenessPercent.value >= 75 ? '基础资料完整' : '基础资料待齐',
    description: `当前元信息完整度 ${metadataCompletenessPercent.value}%，题材、风格和基调越清晰，生成结果越稳定。`,
    tone: metadataCompletenessPercent.value >= 75 ? 'ready' : 'pending',
    toneText: metadataCompletenessPercent.value >= 75 ? '成' : '待',
    toneLabel: metadataCompletenessPercent.value >= 75 ? '已完成' : '待补充',
  },
  {
    kicker: '剧情',
    label: props.data?.full_synopsis ? '梗概已归档' : '梗概待整理',
    description: props.data?.full_synopsis
      ? '完整梗概已进入档案，可作为章节推进和回收伏笔的主线依据。'
      : '补齐完整梗概后，章节大纲和写作台会有更可靠的主线参照。',
    tone: props.data?.full_synopsis ? 'ready' : 'pending',
    toneText: props.data?.full_synopsis ? '成' : '待',
    toneLabel: props.data?.full_synopsis ? '已完成' : '待补充',
  },
])

const summaryStatus = computed(() => {
  if (props.data?.one_sentence_summary && props.data?.full_synopsis) {
    return '大纲已立'
  }
  if (props.data?.one_sentence_summary || props.data?.full_synopsis) {
    return '大纲待齐'
  }
  return '案头待理'
})

const updatedLabel = computed(() =>
  props.data?.updated_at ? `大纲设定更新于 ${formatDateTime(props.data.updated_at)}` : '暂无大纲设定更新时间',
)

const emitEdit = (field: string, title: string, value: any) => {
  if (!props.editable) return
  emit('edit', { field, title, value })
}
</script>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'OverviewSection',
})
</script>

<style scoped>
.archive-overview {
  padding: 0;
}

.archive-overview__content-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(280px, 0.75fr);
  gap: var(--md-spacing-4);
  align-items: stretch;
}

.archive-overview__summary-panel,
.archive-overview__metadata-panel,
.archive-overview__synopsis-panel {
  min-width: 0;
}

.archive-overview__summary-body {
  display: block;
  height: 100%;
}

.archive-overview__summary-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-4);
}

.archive-overview__panel-head--inline {
  margin-bottom: 0;
}

.archive-overview__quote {
  margin: 0;
  max-width: 68ch;
  color: var(--md-on-surface);
  font-size: var(--md-body-large);
  font-weight: 600;
  line-height: 1.9;
  white-space: pre-line;
}

.archive-overview__summary-footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--md-spacing-3);
  padding-top: var(--md-spacing-2);
  border-top: 1px dashed var(--md-outline-variant);
}

/* 横向平铺的核心量化指标 */
.archive-overview__horizontal-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: var(--md-spacing-4);
  margin: var(--md-spacing-4) 0 0;
  padding: var(--md-spacing-3) 0 0;
  border-top: 1px dashed var(--md-outline-variant); /* 顶部分割墨虚线 */
}

.archive-overview__horizontal-metric {
  flex: 1 1 180px; /* 均分横向排开 */
  min-width: 140px;
  padding: var(--md-spacing-3);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-sm);
  background-color: var(--md-surface-container-low); /* 竹纸淡黄底色 */
  display: flex;
  align-items: center;
  gap: var(--md-spacing-3);
  transition:
    background-color 0.2s ease,
    border-color 0.2s ease;
}

.archive-overview__horizontal-metric:hover {
  background-color: color-mix(in srgb, var(--md-surface) 60%, transparent);
}

.archive-overview__horizontal-metric dt {
  margin: 0;
  color: var(--md-primary-light);
  font-family: var(--md-font-serif);
  font-weight: 600;
  font-size: 13px;
  letter-spacing: 0.05em;
  writing-mode: vertical-rl; /* 汉字竖排，呈现古典笺印艺术感 */
  text-orientation: mixed;
  border-right: 1.5px solid var(--md-outline-variant);
  padding-right: 6px;
  line-height: 1.2;
}

.archive-overview__horizontal-metric dd {
  margin: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 2px;
}

.archive-overview__horizontal-metric strong {
  color: var(--md-primary-dark);
  font-family: var(--md-font-serif);
  font-size: 1.35rem;
  font-weight: 700;
  line-height: 1.1;
}

.archive-overview__horizontal-metric span {
  color: var(--md-on-surface-variant);
  font-size: 11px;
  font-family: var(--md-font-family);
  line-height: 1.2;
}



.archive-overview__panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--md-spacing-4);
  margin-bottom: var(--md-spacing-4);
}

.archive-overview__metadata {
  display: grid;
  gap: var(--md-spacing-3);
  margin: 0;
}

.archive-overview__meta-row {
  display: grid;
  grid-template-columns: minmax(5em, auto) minmax(0, 1fr);
  gap: var(--md-spacing-3);
  align-items: baseline;
  padding-top: var(--md-spacing-3);
  border-top: 1px dashed var(--md-outline-variant);
}

.archive-overview__meta-row:first-child {
  padding-top: 0;
  border-top: 0;
}

.archive-overview__meta-row dt {
  margin: 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-medium);
  font-weight: 700;
  letter-spacing: 0.08em;
}

.archive-overview__meta-row dd {
  margin: 0;
  color: var(--md-primary-dark);
  font-size: var(--md-body-medium);
  font-weight: 600;
  line-height: 1.65;
  overflow-wrap: anywhere;
  text-align: right;
}

.archive-overview__completeness {
  display: grid;
  gap: var(--md-spacing-2);
  margin-top: var(--md-spacing-4);
  padding-top: var(--md-spacing-4);
  border-top: 1px dashed var(--md-outline-variant);
}

.archive-overview__completeness-copy {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--md-spacing-3);
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-medium);
  font-weight: 700;
  letter-spacing: 0.06em;
}

.archive-overview__completeness-copy strong {
  color: var(--md-primary-dark);
  font-family: var(--md-font-display);
  letter-spacing: 0.05em;
}

.archive-overview__completeness-track {
  position: relative;
  height: 8px;
  overflow: hidden;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-xs);
  background-color: var(--md-surface-container);
}

.archive-overview__completeness-track::before {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: var(--archive-overview-completeness, 0%);
  background-color: var(--md-primary-light);
}

.archive-overview__readiness-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(240px, 100%), 1fr));
  gap: var(--md-spacing-4);
}

.archive-overview__readiness-card {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  align-items: start;
  gap: var(--md-spacing-3);
  background-color: var(--md-surface-container-low);
}

.archive-overview__readiness-mark {
  width: 34px;
  height: 34px;
  border: 1px solid var(--md-outline);
  border-radius: var(--md-radius-xs);
  background-color: var(--md-surface);
  display: grid;
  place-items: center;
  color: var(--md-on-surface-variant);
  font-family: var(--md-font-display);
  font-size: var(--md-label-small);
  font-weight: 800;
  letter-spacing: 0;
}

.archive-overview__readiness-mark.is-ready {
  border-color: var(--md-success-text);
  background-color: var(--md-success-container);
  color: var(--md-success-text);
}

.archive-overview__readiness-mark.is-pending {
  border-color: var(--md-warning-text);
  background-color: var(--md-warning-container);
  color: var(--md-warning-text);
}

.archive-overview__readiness-mark {
  line-height: 1;
}

.archive-overview__synopsis-body {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-4);
}

.archive-overview__prose {
  max-width: 78ch;
}

.archive-overview__empty-text {
  color: var(--md-on-surface-variant) !important;
}

@media (max-width: 640px) {
  .archive-overview__content-grid {
    grid-template-columns: 1fr;
  }

  .archive-overview__panel-head,
  .archive-overview__summary-body {
    flex-direction: column;
    grid-template-columns: 1fr;
  }

  .archive-overview__summary-aside {
    padding-left: 0;
    padding-top: var(--md-spacing-4);
    border-left: 0;
    border-top: 1px dashed var(--md-outline-variant);
  }

  .archive-overview__meta-row {
    grid-template-columns: 1fr;
    gap: var(--md-spacing-1);
  }

  .archive-overview__meta-row dd {
    text-align: left;
  }
}
</style>
