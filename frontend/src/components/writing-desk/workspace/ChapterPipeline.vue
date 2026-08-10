<!-- AIMETA P=章节工作流节点进度条|R=节点状态_节点选择_失败节点重试入口|NR=不直接调用API_不持有命令状态|E=component:ChapterPipeline|X=internal|A=workflow-pipeline|D=vue|S=dom|RD=./README.ai -->
<template>
  <article
    class="chapter-console__pipeline-card"
    :class="{
      'is-read-only': true,
      'has-node-retry': canRetryActiveStep && activeStepKey !== null,
    }"
    aria-label="生成进度"
  >
    <header class="chapter-console__pipeline-header-main">
      <div class="chapter-console__pipeline-title-group">
        <h4>生成进度</h4>
        <span class="chapter-console__read-only-badge">只读回溯</span>
      </div>
      <button
        v-if="canCancel"
        type="button"
        class="md-btn md-btn-outlined md-ripple chapter-console__pipeline-cancel"
        data-action="cancel"
        :disabled="pending"
        @click="emit('cancel')"
      >
        取消本轮
      </button>
    </header>
    <ol class="chapter-console__pipeline">
      <li
        v-for="(item, index) in pipelineSteps"
        :key="item.key"
        :aria-label="stepTooltipText(item.key, index)"
        :aria-current="activeStepKey === item.key ? 'step' : undefined"
        :role="canRetryActiveStep && activeStepKey === item.key
          ? 'group'
          : stepState(item.key, index).tone !== 'waiting' ? 'button' : undefined"
        :tabindex="stepState(item.key, index).tone !== 'waiting'
          && !(canRetryActiveStep && activeStepKey === item.key) ? 0 : undefined"
        :class="[
          'chapter-console__pipeline-item',
          `is-${stepState(item.key, index).tone}`,
          { 'is-current': stepState(item.key, index).tone === 'in-progress' },
          { 'is-leading-to-current': isLeadingToCurrent(index) },
          { 'is-selected': activeStepKey === item.key },
          { 'is-clickable': stepState(item.key, index).tone !== 'waiting' },
          { 'has-retry-action': canRetryActiveStep && activeStepKey === item.key },
        ]"
        @click="emit('select', item.key, index)"
        @keydown.enter.self="emit('select', item.key, index)"
        @keydown.space.self.prevent="emit('select', item.key, index)"
      >
        <Transition name="chapter-node-retry">
          <Tooltip
            v-if="canRetryActiveStep && activeStepKey === item.key"
            text="使用上一节点的结果重新执行当前节点"
            :show-delay="240"
            class="chapter-console__pipeline-node-retry-trigger"
          >
            <button
              type="button"
              class="md-btn md-ripple chapter-console__pipeline-node-retry"
              data-action="retry-external-node"
              :aria-label="`使用上一节点结果重试${item.label}`"
              :disabled="pending"
              @click.stop="emit('retryExternal')"
            >
              <svg
                class="chapter-console__pipeline-node-retry-icon"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path d="M3 12a9 9 0 1 0 3-6.7" />
                <path d="M3 4v6h6" />
              </svg>
              <span>{{ pending ? '提交' : '重试' }}</span>
            </button>
          </Tooltip>
        </Transition>
        <Tooltip
          :text="canRetryActiveStep && activeStepKey === item.key ? undefined : stepTooltipText(item.key, index)"
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
  canRetryActiveStep?: boolean
  canCancel?: boolean
  pending?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  canRetryActiveStep: false,
  canCancel: false,
  pending: false,
})

const isLeadingToCurrent = (index: number) => {
  const nextStep = props.pipelineSteps[index + 1]
  return nextStep ? props.stepState(nextStep.key, index + 1).tone === 'in-progress' : false
}

const emit = defineEmits<{
  select: [key: string, index: number]
  cancel: []
  retryExternal: []
}>()
</script>

<style scoped>
/* 卡片骨架：源自 ChapterGenerating 与其余 card 共享的 border/radius/bg/shadow/padding，
   scoped 隔离下父组件选择器不再作用于本组件元素，故在此重复声明 */
.chapter-console__pipeline-card {
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-sm);
  background: color-mix(in srgb, var(--md-surface) 96%, transparent);
  box-shadow: var(--md-elevation-paper-1); /* 浮起纸影 */
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

.chapter-console__pipeline-cancel {
  min-height: 36px;
  white-space: nowrap;
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

.chapter-console__pipeline-item.is-leading-to-current::after {
  background-color: var(--md-success);
  background-image: linear-gradient(
    90deg,
    transparent 0%,
    color-mix(in srgb, var(--md-surface) 82%, transparent) 46%,
    var(--md-primary) 68%,
    transparent 100%
  );
  background-position: -60% 0;
  background-repeat: no-repeat;
  background-size: 38% 100%;
  animation: line-flow 1.25s infinite linear;
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
  box-shadow: none;
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

.chapter-console__pipeline-item.is-in-progress .chapter-console__pipeline-marker::before,
.chapter-console__pipeline-item.is-in-progress .chapter-console__pipeline-marker::after {
  content: '';
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
}

.chapter-console__pipeline-item.is-in-progress .chapter-console__pipeline-marker::before {
  inset: -2px;
  border: 2px solid color-mix(in srgb, var(--md-primary) 18%, transparent);
  border-top-color: var(--md-primary);
  border-right-color: var(--md-primary);
  animation: current-node-orbit 1s infinite linear;
}

.chapter-console__pipeline-item.is-in-progress .chapter-console__pipeline-marker::after {
  inset: 1px;
  border: 1px solid var(--md-primary);
  opacity: 0;
  animation: current-node-ripple 1.6s infinite linear;
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

.chapter-console__pipeline-item.is-clickable:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 4px;
  border-radius: var(--md-radius-xs);
}

.chapter-console__pipeline-item > .chapter-console__pipeline-node-retry-trigger {
  position: absolute;
  z-index: 4;
  top: -36px;
  left: 50%;
  transform: translateX(-50%);
}

.chapter-console__pipeline-node-retry {
  width: 56px;
  min-width: 56px;
  min-height: 28px;
  gap: 3px;
  padding: 0 6px;
  border: 1px solid color-mix(in srgb, var(--md-error) 55%, var(--md-outline));
  border-radius: var(--md-radius-xs);
  background-color: var(--md-surface);
  color: var(--md-error);
  box-shadow: none;
  font-size: var(--md-label-medium);
  font-weight: 700;
  letter-spacing: 0;
  white-space: nowrap;
}

.chapter-console__pipeline-node-retry:hover:not(:disabled) {
  border-color: var(--md-error);
  background-color: color-mix(in srgb, var(--md-error) 8%, var(--md-surface));
}

.chapter-console__pipeline-node-retry-icon {
  width: 13px;
  height: 13px;
  flex: none;
}

.chapter-node-retry-enter-active,
.chapter-node-retry-leave-active {
  transition:
    opacity 180ms cubic-bezier(0.22, 1, 0.36, 1),
    transform 180ms cubic-bezier(0.22, 1, 0.36, 1),
    filter 180ms cubic-bezier(0.22, 1, 0.36, 1);
}

.chapter-node-retry-enter-from,
.chapter-node-retry-leave-to {
  opacity: 0;
  filter: blur(2px);
  transform: translate(-50%, 6px);
}

/* 选中节点的圆圈特效 */
.chapter-console__pipeline-item.is-selected .chapter-console__dot {
  outline: 2px solid var(--md-primary);
  outline-offset: 3px;
  transform: scale(1.2);
}

.chapter-console__pipeline-item.is-selected.is-in-progress .chapter-console__dot {
  outline: none;
}

.chapter-console__pipeline-item.is-selected.is-failed .chapter-console__dot {
  outline-color: var(--md-error);
}

.chapter-console__pipeline-item.is-selected.is-done .chapter-console__dot {
  outline-color: var(--md-success);
}

@media (hover: hover) and (min-width: 834px) {
  .chapter-console__pipeline-card.is-read-only.has-node-retry .chapter-console__pipeline {
    margin-top: calc(var(--md-spacing-3) + 36px);
  }

  .chapter-console__pipeline-tooltip-wrapper {
    cursor: pointer;
  }
}

@keyframes current-node-ripple {
  0% {
    transform: scale(0.55);
    opacity: 0;
  }

  18% {
    opacity: 0.72;
  }

  60% {
    opacity: 0.42;
  }

  100% {
    transform: scale(1.5);
    opacity: 0;
  }
}

@keyframes current-node-orbit {
  to {
    transform: rotate(360deg);
  }
}

@keyframes line-flow {
  0% {
    background-position: -60% 0;
  }
  100% {
    background-position: 160% 0;
  }
}

@keyframes line-flow-vertical {
  0% {
    background-position: 0 -60%;
  }
  100% {
    background-position: 0 160%;
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

  .chapter-console__pipeline-item.has-retry-action {
    padding-right: 68px;
  }

  .chapter-console__pipeline-item > .chapter-console__pipeline-node-retry-trigger {
    top: 50%;
    right: 0;
    left: auto;
    transform: translateY(-50%);
  }

  .chapter-node-retry-enter-from,
  .chapter-node-retry-leave-to {
    transform: translate(6px, -50%);
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

  .chapter-console__pipeline-item.is-leading-to-current::before {
    background-color: var(--md-success);
    background-image: linear-gradient(
      180deg,
      transparent 0%,
      color-mix(in srgb, var(--md-surface) 82%, transparent) 46%,
      var(--md-primary) 68%,
      transparent 100%
    );
    background-position: 0 -60%;
    background-repeat: no-repeat;
    background-size: 100% 38%;
    animation: line-flow-vertical 1.25s infinite linear;
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

@media (prefers-reduced-motion: reduce) {
  .chapter-console__pipeline-item.is-leading-to-current::before,
  .chapter-console__pipeline-item.is-leading-to-current::after,
  .chapter-console__pipeline-item.is-in-progress .chapter-console__pipeline-marker::before,
  .chapter-console__pipeline-item.is-in-progress .chapter-console__pipeline-marker::after {
    animation: none;
  }

  .chapter-console__pipeline-item.is-selected.is-in-progress .chapter-console__dot {
    outline: 2px solid var(--md-primary);
    outline-offset: 3px;
  }

  .chapter-node-retry-enter-active,
  .chapter-node-retry-leave-active {
    transition: none;
  }
}
</style>
