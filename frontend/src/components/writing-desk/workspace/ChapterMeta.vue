<!-- AIMETA P=章节头部元信息_标题状态摘要|R=标题复制_状态印章|NR=不含复制实现与状态来源|E=component:ChapterMeta|X=internal|A=章节头部|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="writing-workspace__chapter-meta">
    <div class="writing-workspace__chapter-title-line">
      <h2 class="md-title-large font-semibold writing-workspace__chapter-no">
        第{{ chapterNumber }}章
      </h2>
      <Tooltip :text="titleTooltipText" :show-delay="150">
        <button
          type="button"
          class="writing-workspace__title-copy md-title-medium md-on-surface"
          @click="$emit('copyTitle')"
          @mouseleave="$emit('resetTitleTooltip')"
        >
          {{ chapterOutline?.title || '未知标题' }}
        </button>
      </Tooltip>
      <span
        class="writing-workspace__status-tag"
        :class="`writing-workspace__status-tag--${statusTone}`"
      >
        {{ statusLabel }}
      </span>
      <span class="writing-workspace__chapter-inline-meta md-label-small md-on-surface-variant">
        {{ inlineMeta }}
      </span>
    </div>
    <p class="writing-workspace__summary md-body-small md-on-surface-variant">
      {{ chapterOutline?.summary || '暂无章节描述' }}
    </p>
  </div>
</template>

<script setup lang="ts">
import Tooltip from '@/components/Tooltip.vue'
import type { ChapterOutline } from '@/api/novel'

interface Props {
  chapterNumber: number | null
  chapterOutline: ChapterOutline | null
  statusLabel: string
  statusTone: string
  inlineMeta: string
  titleTooltipText: string
}

defineProps<Props>()
defineEmits(['copyTitle', 'resetTitleTooltip'])
</script>

<style scoped>
/* ==========================================================================
   章节头部元信息（随 template 从 WDWorkspace 迁入）
   ========================================================================== */
.writing-workspace__chapter-meta {
  flex: 1 1 auto;
  min-width: 0;
}

.writing-workspace__chapter-title-line {
  display: flex;
  align-items: center;
  gap: var(--md-spacing-2);
  margin-bottom: var(--md-spacing-1);
  flex-wrap: wrap;
}

.writing-workspace__chapter-no {
  flex-shrink: 0;
  font-size: 22px;
  font-family: var(--md-font-serif);
  font-weight: 600;
  letter-spacing: 0.04em;
}

/* 极致国风脑洞：将状态标签改造为方直“金石印章方印” */
.writing-workspace__status-tag {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 7px;
  border-radius: 0 !important; /* 强制去圆角 */
  border: 1.5px solid transparent;
  font-size: 11px;
  font-weight: 600;
  font-family: var(--md-font-serif);
  letter-spacing: 0.08em;
  white-space: nowrap;
}

/* 竹青阴刻（印面压纸，不浮起） */
.writing-workspace__status-tag--success {
  color: var(--md-on-primary);
  background-color: var(--md-success);
  border-color: var(--md-success-text);
  box-shadow: none;
}

/* 赭红阴刻 */
.writing-workspace__status-tag--error {
  color: var(--md-on-primary);
  background-color: var(--md-error);
  border-color: var(--md-error-text);
  box-shadow: none;
}

/* 朱砂阳刻（红底白字或红边红字，印面压纸不浮起） */
.writing-workspace__status-tag--progress {
  color: var(--md-secondary);
  background-color: color-mix(in srgb, var(--md-secondary) 5%, transparent);
  border-color: var(--md-secondary);
  box-shadow: none;
}

.writing-workspace__status-tag--pending {
  color: var(--md-secondary);
  background-color: color-mix(in srgb, var(--md-secondary) 3%, transparent);
  border-color: var(--md-secondary);
}

.writing-workspace__status-tag--idle {
  color: var(--md-on-surface-variant);
  background-color: var(--md-surface-container-low);
  border-color: var(--md-outline);
}

.writing-workspace__chapter-inline-meta {
  white-space: nowrap;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.08em;
  font-family: var(--md-font-serif);
}

.writing-workspace__title-copy {
  min-width: 0;
  flex: 1;
  padding: 0;
  border: 0;
  background: transparent;
  text-align: left;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: pointer;
  appearance: none;
  font-size: 22px;
  font-family: var(--md-font-serif);
  font-weight: 600;
  letter-spacing: 0.04em;
  transition: color 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}

.writing-workspace__title-copy:hover {
  color: var(--md-secondary);
  text-decoration: underline;
}

.writing-workspace__title-copy:focus-visible {
  outline: 2.5px solid var(--md-secondary);
  outline-offset: 3px;
  border-radius: 0 !important;
}

.writing-workspace__summary {
  max-width: 88ch;
  margin: var(--md-spacing-2) 0 0;
  padding: 0;
  font-size: 15px;
  line-height: 1.75;
  letter-spacing: 0.02em;
  color: var(--md-on-surface-variant);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-family: var(--md-font-serif);
  font-weight: 500;
  font-style: normal;
  opacity: 0.85;
}

@media (max-width: 940px) {
  .writing-workspace__summary {
    max-width: 100%;
  }
}

@media (max-width: 640px) {
  .writing-workspace__chapter-title-line {
    gap: 6px;
  }

  .writing-workspace__chapter-inline-meta {
    width: 100%;
  }
}
</style>
