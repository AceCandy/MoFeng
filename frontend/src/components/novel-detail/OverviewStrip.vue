<template>
  <section class="detail-shell__overview-strip" aria-label="当前小说概览">
    <div class="detail-shell__overview-scroll">
      <div class="detail-shell__scroll-main">
        <div class="detail-shell__scroll-header">
          <div>
            <p class="detail-shell__kicker">故事蓝图</p>
            <h2>{{ title }}</h2>
          </div>
        </div>
        <p class="detail-shell__scroll-desc">
          {{ summary || '从侧边分区查看设定、角色、章节与分析材料。' }}
        </p>
        <div class="detail-shell__scroll-status">
          <span class="detail-shell__status-pill" :class="`is-${status.tone}`">
            {{ status.label }}
          </span>
          <span class="detail-shell__status-meta">{{ currentChapterLabel }}</span>
          <span v-if="updatedAt" class="detail-shell__scroll-time">
            更新于 {{ formatDateTime(updatedAt) }}
          </span>
        </div>
      </div>
      <dl class="detail-shell__scroll-metrics" aria-label="蓝图统计">
        <div class="detail-shell__scroll-metric">
          <dt>角色</dt>
          <dd>
            <strong>{{ characterCount }}</strong>
            <span>主要角色</span>
          </dd>
        </div>
        <div class="detail-shell__scroll-metric">
          <dt>章节</dt>
          <dd>
            <strong>{{ chapterCompleted }}/{{ chapterTotal }}</strong>
            <span>已完成 / 总大纲</span>
          </dd>
        </div>
        <div class="detail-shell__scroll-metric is-alert">
          <dt>伏笔</dt>
          <dd>
            <strong>{{ foreshadowingOverdue }}</strong>
            <span>待回收线索</span>
          </dd>
        </div>
      </dl>
    </div>
  </section>
</template>

<script setup lang="ts">
import { formatDateTime } from '@/utils/date'

// 小说概览长卷（标题/一句话简介/状态/统计指标）。从 NovelDetailShell 抽出，纯展示组件。
type ProjectStatusTone = 'done' | 'active' | 'draft'

defineProps<{
  title: string
  summary?: string
  status: { label: string; tone: ProjectStatusTone }
  currentChapterLabel: string
  updatedAt?: string | null
  characterCount: number
  chapterCompleted: number
  chapterTotal: number
  foreshadowingOverdue: number
}>()
</script>

<style scoped>
.detail-shell__overview-strip {
  max-width: 1800px;
  width: 100%;
  margin: 0 auto;
  padding: var(--md-spacing-3) 1rem 0;
  box-sizing: border-box;
}

/* 一体化界格长卷大容器 */
.detail-shell__overview-scroll {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.75fr);
  border: 1px solid var(--md-jiege); /* 1px 界格发线 */
  border-radius: var(--md-radius-xs); /* 界格微直角 */
  background-color: var(--md-surface); /* 熟宣底色 */
  box-shadow: var(--md-elevation-paper-1); /* 稿纸容器浮起 */
  overflow: hidden;
  height: var(--detail-shell-overview-height);
  min-height: 0;
}

/* 左侧总览区 */
.detail-shell__scroll-main {
  min-height: 0;
  padding: var(--md-spacing-3) var(--md-spacing-5);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  border-right: 1px solid var(--md-outline-variant); /* 分割画卷的墨晕细线 */
}

.detail-shell__scroll-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--md-spacing-4);
}

.detail-shell__kicker {
  margin: 0;
  color: var(--md-primary-light);
  font-family: var(--md-font-serif);
  font-size: 12px; /* 宋体题签 */
  font-weight: 600;
  letter-spacing: 0.04em;
  border-bottom: 1px solid var(--md-jiege);
  padding-bottom: 2px;
  display: inline-block;
}

.detail-shell__scroll-main h2 {
  margin: var(--md-spacing-2) 0 0;
  font-family: var(--md-font-serif);
  font-size: 1.3rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--md-primary-dark);
}

.detail-shell__scroll-desc {
  margin: var(--md-spacing-1) 0 var(--md-spacing-2);
  color: var(--md-on-surface-variant);
  font-family: var(--md-font-family);
  font-size: 13.5px;
  line-height: 1.5;
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.detail-shell__scroll-status {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--md-spacing-3);
  margin-top: auto;
}

.detail-shell__status-pill {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 28px;
  padding: 0 10px;
  font-family: var(--md-font-serif);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.1em;
  border-radius: var(--md-radius-xs);
  /* 状态印一律无影 */
}

.detail-shell__status-pill::before {
  content: "";
  position: absolute;
  inset: 1px;
  border: 1px dashed currentColor;
  opacity: 0.45;
  pointer-events: none;
}

.detail-shell__status-pill.is-active {
  background-color: var(--md-secondary-container);
  color: var(--md-secondary);
  border: 1.5px solid var(--md-secondary);
}

.detail-shell__status-pill.is-done {
  background-color: var(--md-success-container);
  color: var(--md-success-text);
  border: 1.5px solid var(--md-success);
}

.detail-shell__status-pill.is-draft {
  background-color: var(--md-surface-container);
  color: var(--md-on-surface-variant);
  border: 1.5px solid var(--md-outline);
}

.detail-shell__status-meta {
  color: var(--md-on-surface-variant);
  font-size: 13px;
  font-family: var(--md-font-family);
  font-weight: 500;
}

.detail-shell__scroll-time {
  color: var(--md-on-surface-variant);
  font-size: 12px;
  font-family: var(--md-font-family);
  opacity: 0.75;
  margin-left: auto;
}

/* 右侧三栏指标区 */
.detail-shell__scroll-metrics {
  display: grid;
  grid-template-rows: repeat(3, minmax(0, 1fr)); /* 纵向均匀排开 */
  background-color: var(--md-surface-container-low); /* 竹纸底色 */
  min-height: 0;
  margin: 0;
}

.detail-shell__scroll-metric {
  position: relative;
  min-height: 0;
  padding: var(--md-spacing-2) var(--md-spacing-4) var(--md-spacing-2) var(--md-spacing-3);
  display: flex;
  flex-direction: column;
  justify-content: center;
  border-bottom: 1.5px solid var(--md-outline-variant); /* 墨晕细横线 */
  transition:
    background-color 0.2s cubic-bezier(0.2, 0, 0, 1),
    border-color 0.2s cubic-bezier(0.2, 0, 0, 1);
}

.detail-shell__scroll-metric dt,
.detail-shell__scroll-metric dd {
  margin: 0;
  min-width: 0;
}

.detail-shell__scroll-metric dd {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.detail-shell__scroll-metric:last-child {
  border-bottom: none;
}

.detail-shell__scroll-metric::before {
  content: "";
  position: absolute;
  top: var(--md-spacing-3);
  right: var(--md-spacing-3);
  width: 6px;
  height: 6px;
  border: 1px solid var(--md-outline);
  background-color: var(--md-surface);
  transform: rotate(45deg);
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease;
}

.detail-shell__scroll-metric:hover {
  background-color: color-mix(in srgb, var(--md-surface) 60%, transparent);
}

.detail-shell__scroll-metric dt {
  margin: 0;
  font-family: var(--md-font-serif);
  font-weight: 600;
  letter-spacing: 0.05em;
  color: var(--md-primary-light);
  font-size: 12px;
}

.detail-shell__scroll-metric strong {
  margin: 0.125rem 0;
  display: block;
  font-family: var(--md-font-serif);
  color: var(--md-primary-dark);
  font-size: 1.18rem;
  font-weight: 600;
  line-height: 1.1;
}

.detail-shell__scroll-metric span {
  margin: 0;
  color: var(--md-on-surface-variant);
  font-size: 11.5px;
  font-family: var(--md-font-family);
  line-height: 1.25;
}

/* 警示性指标（待回收伏笔）：错误语义色，不挪用朱砂 */
.detail-shell__scroll-metric.is-alert::before {
  border-color: var(--md-error-text);
  background-color: var(--md-error-container);
}

.detail-shell__scroll-metric.is-alert strong {
  color: var(--md-error-text);
}

@media (min-width: 1200px) {
  .detail-shell__overview-strip {
    padding: var(--md-spacing-3) 2rem 0;
  }

  .detail-shell__scroll-metrics {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    grid-template-rows: none;
  }

  .detail-shell__scroll-metric {
    border-right: 1.5px solid var(--md-outline-variant);
    border-bottom: 0;
  }

  .detail-shell__scroll-metric:last-child {
    border-right: 0;
  }
}

@media (min-width: 1200px) and (max-height: 700px) {
  .detail-shell__scroll-main {
    padding-block: var(--md-spacing-2);
  }

  .detail-shell__scroll-desc {
    -webkit-line-clamp: 1;
  }
}

@media (max-width: 1199px) {
  .detail-shell__overview-strip {
    grid-template-columns: minmax(0, 1fr);
    padding: var(--md-spacing-3) var(--md-spacing-4) 0;
  }

  .detail-shell__overview-scroll {
    grid-template-columns: minmax(0, 1fr);
  }

  .detail-shell__scroll-main {
    border-right: 0;
    border-bottom: 1px solid var(--md-outline-variant);
  }
}

@media (max-width: 833px) {
  .detail-shell__overview-strip {
    padding: var(--md-spacing-2) var(--md-spacing-4) 0;
  }

  .detail-shell__scroll-main {
    padding: var(--md-spacing-3) var(--md-spacing-4) var(--md-spacing-2);
  }

  .detail-shell__scroll-main h2 {
    margin-top: var(--md-spacing-1);
    font-size: 1.15rem;
  }

  .detail-shell__scroll-desc {
    -webkit-line-clamp: 1;
    margin-block: var(--md-spacing-1);
    font-size: 12.5px;
    line-height: 1.45;
  }

  .detail-shell__scroll-status {
    gap: var(--md-spacing-2);
  }

  .detail-shell__scroll-time {
    display: none;
  }

  .detail-shell__scroll-metrics {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    grid-template-rows: none;
  }

  .detail-shell__scroll-metric {
    padding: var(--md-spacing-2);
    border-right: 1.5px solid var(--md-outline-variant);
    border-bottom: 0;
  }

  .detail-shell__scroll-metric:last-child {
    border-right: 0;
  }

  .detail-shell__scroll-metric::before {
    top: var(--md-spacing-2);
    right: var(--md-spacing-2);
  }

  .detail-shell__scroll-metric strong {
    font-size: 1rem;
  }

  .detail-shell__scroll-metric span {
    font-size: 10.5px;
  }
}
</style>
