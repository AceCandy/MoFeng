<!-- AIMETA P=章节工作流节点进度条|R=只读节点状态_节点选择|NR=不提交节点重试或生命周期命令|E=component:ChapterPipeline|X=internal|A=workflow-pipeline|D=vue|S=dom|RD=./README.ai -->
<template>
  <article
    class="chapter-console__pipeline-card"
    :class="{ 'is-read-only': true }"
    aria-label="生成进度"
  >
    <header class="chapter-console__pipeline-header-main">
      <div class="chapter-console__pipeline-title-group">
        <h4>生成进度</h4>
        <span class="chapter-console__read-only-badge">只读回溯</span>
      </div>
    </header>
    <ol class="chapter-console__pipeline">
      <li
        v-for="(item, index) in pipelineSteps"
        :key="item.key"
        :aria-label="stepTooltipText(item.key, index)"
        :class="[
          'chapter-console__pipeline-item',
          `is-${stepState(item.key, index).tone}`,
          { 'is-current': stepState(item.key, index).tone === 'in-progress' },
          { 'is-selected': activeStepKey === item.key },
          { 'is-clickable': stepState(item.key, index).tone !== 'waiting' },
        ]"
        @click="emit('select', item.key, index)"
      >
        <Tooltip
          :text="stepTooltipText(item.key, index)"
          :show-delay="150"
          class="chapter-console__pipeline-tooltip-wrapper"
        >
          <div class="chapter-console__pipeline-marker">
            <span class="chapter-console__dot"></span>
          </div>
          <div class="chapter-console__pipeline-content">
            <div class="chapter-console__pipeline-header">
              <span class="chapter-console__pipeline-title">{{ item.label }}</span>
              <span
                v-if="shouldShowManualConfirmBadge(item.key)"
                class="chapter-console__pipeline-badge chapter-console__pipeline-badge--manual-confirm"
              >
                待人工确认
              </span>
              <span
                v-if="stepState(item.key, index).tone === 'in-progress'"
                class="chapter-console__pipeline-badge"
              >
                进行中
              </span>
              <span
                v-else-if="stepState(item.key, index).tone === 'failed'"
                class="chapter-console__pipeline-badge chapter-console__pipeline-badge--failed"
              >
                失败
              </span>
            </div>
          </div>
        </Tooltip>
      </li>
    </ol>
  </article>
</template>

<script setup lang="ts">
import Tooltip from '@/components/Tooltip.vue'

interface PipelineStep {
  key: string
  label: string
}

interface Props {
  pipelineSteps: PipelineStep[]
  stepState: (key: string, index: number) => { tone: string; label: string }
  stepTooltipText: (key: string, index: number) => string
  shouldShowManualConfirmBadge: (key: string) => boolean
  activeStepKey: string | null
}

defineProps<Props>()

const emit = defineEmits<{
  select: [key: string, index: number]
}>()
</script>

<style scoped>
/* 卡片骨架：源自 ChapterGenerating 与其余 card 共享的 border/radius/bg/shadow/padding，
   scoped 隔离下父组件选择器不再作用于本组件元素，故在此重复声明 */
.chapter-console__pipeline-card {
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-sm);
  background: color-mix(in srgb, var(--md-surface) 96%, transparent);
  box-shadow: var(--md-elevation-1);
  padding: var(--md-spacing-4);
  position: relative;
  z-index: 5;
  overflow: visible !important;
}

.chapter-console__pipeline-card h4 {
  margin: 0;
  color: var(--md-on-surface);
  font-size: var(--md-title-medium);
}

.chapter-console__pipeline-title-group {
  display: inline-flex;
  align-items: center;
  gap: var(--md-spacing-2);
}

.chapter-console__read-only-badge {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 8px;
  border: 1px solid var(--md-outline);
  border-radius: var(--md-radius-xs);
  background-color: var(--md-surface-container-low);
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-small);
  font-weight: 700;
}

.chapter-console__pipeline-header-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--md-spacing-2);
}

.chapter-console__pipeline-meta-top {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: var(--md-body-small);
  color: var(--md-on-surface-variant);
  background-color: var(--md-surface-container-low);
  padding: 4px 12px;
  border-radius: var(--md-radius-md);
  border: 1px dashed color-mix(in srgb, var(--md-primary) 20%, var(--md-outline-variant));
}

.chapter-console__meta-item {
  display: flex;
  align-items: center;
}

.chapter-console__meta-label {
  color: var(--md-on-surface-variant);
  opacity: 0.8;
}

.chapter-console__meta-value {
  font-weight: 700;
  color: var(--md-primary-dark);
}

.chapter-console__meta-divider {
  color: var(--md-outline);
  opacity: 0.5;
}

.chapter-console__pipeline {
  margin: var(--md-spacing-4) 0 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--md-spacing-2);
  overflow: visible !important;
}

.chapter-console__pipeline-item {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  flex: 1;
  padding: 0 0 14px 0;
  overflow: visible;
  transition: z-index 0.2s ease;
}

.chapter-console__pipeline-item:hover {
  z-index: 10;
}

.chapter-console__pipeline-item::before {
  display: none;
}

.chapter-console__pipeline-item::after {
  content: '';
  position: absolute;
  top: 9px;
  left: calc(50% + 10px);
  right: calc(-50% + 10px);
  height: 2px;
  background-color: var(--md-outline-variant);
  z-index: 1;
}

.chapter-console__pipeline-item:last-child::after {
  display: none;
}

.chapter-console__pipeline-item.is-done::after {
  background-color: var(--md-success);
}

.chapter-console__pipeline-item.is-in-progress::after {
  background: linear-gradient(
    90deg,
    var(--md-success) 0%,
    var(--md-primary) 30%,
    color-mix(in srgb, var(--md-surface) 92%, transparent) 50%,
    var(--md-primary) 70%,
    var(--md-outline-variant) 100%
  );
  background-size: 200% 100%;
  animation: line-flow 2s infinite linear;
}

.chapter-console__pipeline-marker {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  z-index: 2;
  margin-bottom: 8px;
}

.chapter-console__dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background-color: var(--md-outline);
  transition:
    background-color 0.3s cubic-bezier(0.4, 0, 0.2, 1),
    box-shadow 0.3s cubic-bezier(0.4, 0, 0.2, 1),
    transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.chapter-console__pipeline-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.chapter-console__pipeline-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.chapter-console__pipeline-title {
  font-size: var(--md-body-medium);
  font-weight: 500;
  color: var(--md-on-surface-variant);
  transition: color 0.3s ease;
}

.chapter-console__pipeline-badge {
  font-size: var(--md-label-small);
  font-weight: 700;
  color: var(--md-primary);
  background-color: color-mix(in srgb, var(--md-primary) 12%, transparent);
  padding: 2px 6px;
  border-radius: var(--md-radius-small, 4px);
}

.chapter-console__pipeline-badge--failed {
  color: var(--md-error);
  background-color: color-mix(in srgb, var(--md-error) 14%, var(--md-surface));
  border: 1px solid color-mix(in srgb, var(--md-error) 28%, transparent);
}

.chapter-console__pipeline-badge--manual-confirm {
  color: var(--md-on-secondary);
  background-color: var(--md-secondary);
  border: 1px solid var(--md-secondary-dark);
  box-shadow: 1px 1px 0 color-mix(in srgb, var(--md-on-surface) 18%, transparent);
  font-family: var(--md-font-serif);
  letter-spacing: 0.04em;
}

.chapter-console__pipeline-item.is-done .chapter-console__dot {
  background-color: var(--md-success);
}

.chapter-console__pipeline-item.is-done .chapter-console__pipeline-title {
  color: color-mix(in srgb, var(--md-on-surface) 60%, transparent);
}

.chapter-console__pipeline-item.is-in-progress .chapter-console__dot {
  background-color: var(--md-primary);
  transform: scale(1.2);
  position: relative;
}

.chapter-console__pipeline-item.is-in-progress .chapter-console__dot::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background-color: var(--md-primary);
  animation: dot-ripple 1.5s infinite ease-out;
  opacity: 0.4;
  pointer-events: none;
}

.chapter-console__pipeline-item.is-in-progress .chapter-console__pipeline-title {
  color: var(--md-primary);
  font-weight: 700;
  font-size: var(--md-title-small);
}

.chapter-console__pipeline-item.is-failed .chapter-console__dot {
  width: 18px;
  height: 18px;
  display: grid;
  place-items: center;
  border: 3px solid var(--md-error);
  background-color: var(--md-error-container);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--md-error) 18%, transparent);
  transform: scale(1.1);
}

.chapter-console__pipeline-item.is-failed .chapter-console__dot::before {
  content: '!';
  color: var(--md-error);
  font-size: 12px;
  font-weight: 900;
  line-height: 1;
}

.chapter-console__pipeline-item.is-failed .chapter-console__pipeline-title {
  color: var(--md-error);
  font-weight: 700;
}

.chapter-console__pipeline-tooltip-wrapper {
  display: flex !important;
  flex-direction: column;
  align-items: center;
  width: 100%;
}

/* 只读回溯模式：覆写 pipeline 内部元素（ol/item/title）的间距与字号。
   原父级 .chapter-console--read-only 后代选择器选不到子组件内部元素，
   故子组件收 readOnly prop 自绑 is-read-only 类，在此自管覆写。
   根级 border-radius/box-shadow/padding/bg 覆写仍由父级管理（子根继承父 data-v 命中） */
.chapter-console__pipeline-card.is-read-only .chapter-console__pipeline {
  margin-top: var(--md-spacing-3);
}

.chapter-console__pipeline-card.is-read-only .chapter-console__pipeline-item {
  padding-bottom: 8px;
}

.chapter-console__pipeline-card.is-read-only .chapter-console__pipeline-title {
  font-size: var(--md-label-medium);
  font-weight: 600;
}

.chapter-console__pipeline-item.is-clickable {
  cursor: pointer;
}

.chapter-console__pipeline-item.is-clickable:hover .chapter-console__dot {
  transform: scale(1.3);
}

/* 选中节点的圆圈特效 */
.chapter-console__pipeline-item.is-selected .chapter-console__dot {
  outline: 2px solid var(--md-primary);
  outline-offset: 3px;
  transform: scale(1.2);
}

.chapter-console__pipeline-item.is-selected.is-failed .chapter-console__dot {
  outline-color: var(--md-error);
}

.chapter-console__pipeline-item.is-selected.is-done .chapter-console__dot {
  outline-color: var(--md-success);
}

@media (hover: hover) and (min-width: 834px) {
  .chapter-console__pipeline-tooltip-wrapper {
    cursor: pointer;
  }
}

@media (prefers-reduced-motion: reduce) {
  .chapter-console__pipeline-item.is-in-progress .chapter-console__dot {
    animation: none;
  }
}

@keyframes dot-ripple {
  0% {
    transform: scale(1);
    opacity: 0.4;
  }

  100% {
    transform: scale(2.2);
    opacity: 0;
  }
}

@keyframes line-flow {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: 0 0;
  }
}

@keyframes line-flow-vertical {
  0% {
    background-position: 0 200%;
  }
  100% {
    background-position: 0 0;
  }
}

@media (max-width: 833px) {
  .chapter-console__pipeline {
    flex-direction: column;
    gap: 0;
  }

  .chapter-console__pipeline-item {
    padding: 10px 0 14px 0;
    flex: none;
  }

  .chapter-console__pipeline-tooltip-wrapper {
    flex-direction: row;
    align-items: flex-start;
    text-align: left;
  }

  .chapter-console__pipeline-item::before {
    display: block;
    content: '';
    position: absolute;
    left: 9px;
    top: 24px;
    bottom: -10px;
    width: 2px;
    background-color: var(--md-outline-variant);
    z-index: 1;
  }

  .chapter-console__pipeline-item:last-child::before {
    display: none;
  }

  .chapter-console__pipeline-item.is-done::before {
    background-color: var(--md-success);
  }

  .chapter-console__pipeline-item.is-in-progress::before {
    background: linear-gradient(
      180deg,
      var(--md-success) 0%,
      var(--md-primary) 30%,
      color-mix(in srgb, var(--md-surface) 92%, transparent) 50%,
      var(--md-primary) 70%,
      var(--md-outline-variant) 100%
    );
    background-size: 100% 200%;
    animation: line-flow-vertical 2s infinite linear;
  }

  .chapter-console__pipeline-item::after {
    display: none;
  }

  .chapter-console__pipeline-marker {
    margin-bottom: 0;
    margin-top: 2px;
  }

  .chapter-console__pipeline-content {
    align-items: flex-start;
  }

  .chapter-console__pipeline-header {
    flex-direction: row;
    align-items: center;
    gap: var(--md-spacing-2);
  }
}
</style>
