<!-- AIMETA P=生成中_章节生成进度|R=进度展示_流式输出|NR=不含生成逻辑|E=component:ChapterGenerating|X=internal|A=生成状态|D=vue|S=dom|RD=./README.ai -->
<template>
  <section
    class="chapter-console"
    :class="{ 'chapter-console--read-only': props.readOnly }"
    aria-label="AI章节生成控制台"
  >
    <article class="chapter-console__pipeline-card" aria-label="生成进度">
      <header class="chapter-console__pipeline-header-main">
        <div class="chapter-console__pipeline-title-group">
          <h4>生成进度</h4>
          <span v-if="props.readOnly" class="chapter-console__read-only-badge">只读回溯</span>
        </div>
        <div
          v-if="!props.readOnly && props.status && ['generating', 'evaluating', 'selecting'].includes(props.status)"
          class="chapter-console__pipeline-meta-top"
        >
          <span class="chapter-console__meta-item">
            <span class="meta-label">已耗时：</span>
            <span class="meta-value">{{ elapsedText }}</span>
          </span>
          <span class="chapter-console__meta-divider">·</span>
          <span class="chapter-console__meta-item">
            <span class="meta-label">预计剩余：</span>
            <span class="meta-value">{{ etaText }}</span>
          </span>
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
          @click="selectStep(item.key, index)"
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
                <button
                  v-if="canRetryFromNode(item.key, index)"
                  type="button"
                  class="chapter-console__pipeline-retry"
                  :disabled="generatingChapter === chapterNumber"
                  @click.stop="emit('retryFromNode', { chapterNumber: props.chapterNumber, nodeKey: item.key })"
                >
                  从此节点重试
                </button>
              </div>
            </div>
          </Tooltip>
        </li>
      </ol>
    </article>

    <!-- 失败状态展示区域 -->
    <div v-if="!props.readOnly && (props.status === 'failed' || props.status === 'evaluation_failed')" class="chapter-console__failed-container">

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
          v-if="props.status === 'evaluation_failed'"
          type="button"
          @click="emit('evaluateChapter')"
          class="md-btn md-btn-filled md-ripple"
        >
          重新 AI评审
        </button>
        <button
          type="button"
          @click="handleFailedGenerateAction"
          :disabled="generatingChapter === chapterNumber"
          :class="[
            'md-btn md-ripple disabled:opacity-50',
            props.status === 'evaluation_failed'
              ? 'md-btn-outlined chapter-console__danger-action'
              : 'md-btn-filled',
          ]"
        >
          {{ generatingChapter === chapterNumber ? '重试中...' : retryGenerateLabel }}
        </button>
      </div>

    </div>

    <!-- 正常生成中状态展示草稿预览卡片 -->
    <ChapterDraftPreview
      v-else-if="!props.readOnly"
      :chapter-content-preview="props.chapterContentPreview"
    />

    <!-- 节点详情面板 -->
    <article
      v-if="activeStepDetails && (!props.readOnly || activeStepKey)"
      class="chapter-console__inspector-card"
    >
      <header class="chapter-console__inspector-header">
        <div class="chapter-console__inspector-title-group">
          <span class="chapter-console__inspector-badge">节点详情</span>
          <h4 class="chapter-console__inspector-title">{{ activeStepDetails.label }}</h4>
        </div>
        <span class="chapter-console__inspector-subtitle">{{ activeStepDetails.summary }}</span>
      </header>
      <div class="chapter-console__inspector-meta">
        <span class="chapter-console__call-type">调用类型：{{ activeStepDetails.callType }}</span>
        <span class="chapter-console__llm-usage">LLM 调用：{{ activeStepDetails.llmUsage }}</span>
        <span
          v-if="activeStepDetails.status"
          class="chapter-console__trace-status"
          :class="{ 'is-failed': activeStepDetails.status === '失败' }"
        >
          状态：{{ activeStepDetails.status }}
        </span>
        <span class="chapter-console__trace-duration">
          系统耗时：{{ activeStepDetails.systemDuration }}
        </span>
      </div>
      <div class="chapter-console__inspector-grids">
        <div class="chapter-console__inspector-panel">
          <div class="chapter-console__panel-title">
            <svg class="w-4 h-4 text-primary" viewBox="0 0 20 20" fill="currentColor" width="16" height="16">
              <path fill-rule="evenodd" d="M3 3a1 1 0 011-1h12a1 1 0 011 1v12a1 1 0 01-1 1H4a1 1 0 01-1-1V3zm2.5 1.5v3h9v-3h-9zm9 5.5h-9v3h9v-3z" clip-rule="evenodd" />
            </svg>
            输入材料
          </div>
          <div class="chapter-console__panel-code-wrapper">
            <pre class="chapter-console__panel-code"><code>{{ activeStepDetails.inputs }}</code></pre>
          </div>
        </div>
        <div class="chapter-console__inspector-panel">
          <div class="chapter-console__panel-title">
            <svg class="w-4 h-4 text-primary" viewBox="0 0 20 20" fill="currentColor" width="16" height="16">
              <path fill-rule="evenodd" d="M18 10c0 3.866-3.582 7-8 7a8.841 8.841 0 01-4.083-.98L2 17l1.338-3.123C2.493 12.767 2 11.434 2 10c0-3.866 3.582-7 8-7s8 3.134 8 7zM7 9H5v2h2V9zm8 0h-2v2h2V9zM9 9h2v2H9V9z" clip-rule="evenodd" />
            </svg>
            实际动作
          </div>
          <div class="chapter-console__panel-code-wrapper">
            <pre class="chapter-console__panel-code"><code>{{ activeStepDetails.actions }}</code></pre>
          </div>
        </div>
        <div class="chapter-console__inspector-panel">
          <div class="chapter-console__panel-title">
            <svg class="w-4 h-4 text-primary" viewBox="0 0 20 20" fill="currentColor" width="16" height="16">
              <path fill-rule="evenodd" d="M4 3a1 1 0 00-1 1v12a1 1 0 001 1h12a1 1 0 001-1V8.414a1 1 0 00-.293-.707l-4.414-4.414A1 1 0 0011.586 3H4zm7 1.5V8h3.5L11 4.5zM6 11h8v1.5H6V11zm0 3h6v1.5H6V14z" clip-rule="evenodd" />
            </svg>
            产出结果
          </div>
          <div class="chapter-console__panel-code-wrapper">
            <pre class="chapter-console__panel-code"><code>{{ activeStepDetails.outputs }}</code></pre>
          </div>
        </div>
      </div>
    </article>

    <footer
      v-if="!props.readOnly && props.status !== 'failed' && props.status !== 'evaluation_failed'"
      class="chapter-console__actions"
    >
      <button type="button" class="md-btn md-btn-outlined md-ripple" @click="moveToBackground">
        转入后台生成
      </button>
      <button type="button" class="md-btn md-btn-outlined md-ripple" @click="cancelGeneration">
        取消生成
      </button>
      <button
        type="button"
        class="md-btn md-btn-tonal md-ripple"
        :class="{ 'is-enabled': notifyWhenDone }"
        @click="toggleNotify"
      >
        {{ notifyWhenDone ? '已开启完成通知' : '完成后通知我' }}
      </button>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import Tooltip from '@/components/Tooltip.vue'
import ChapterDraftPreview from './ChapterDraftPreview.vue'
import type { Chapter, ChapterGenerationTrace, ChapterVersion } from '@/api/novel'
import { globalAlert } from '@/composables/useAlert'
import { useGenerationTiming } from '@/composables/useGenerationTiming'
import { useGenerationFailure } from '@/composables/useGenerationFailure'
import { useGenerationPipeline } from '@/composables/useGenerationPipeline'
import {
  STEP_DETAILS,
  PIPELINE_LABELS,
  TRACE_STATUS_LABELS,
  normalizePipelineStepKey,
  traceMetadata,
  resolveTraceDurationMs,
  formatSystemDuration,
  traceUsesLlm,
  formatTraceInputs,
  formatTraceActions,
  formatTraceOutputs,
  resolveTraceCallType,
  type ActiveStepDetails,
} from '@/utils/generationTrace'

interface Props {
  chapterNumber: number | null
  chapterTitle?: string | null
  chapterSummary?: string | null
  chapterContentPreview?: string | null
  status: Chapter['generation_status'] | null
  generationProgress?: number | null
  generationStep?: string | null
  generationStepIndex?: number | null
  generationStepTotal?: number | null
  generationStartedAt?: string | null
  statusUpdatedAt?: string | null
  generationTraces?: ChapterGenerationTrace[]
  generatingChapter?: number | null
  availableVersions?: ChapterVersion[]
  selectedVersionIndex?: number
  readOnly?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  chapterTitle: '',
  chapterSummary: '',
  chapterContentPreview: '',
  generationTraces: () => [],
  generatingChapter: null,
  availableVersions: () => [],
  selectedVersionIndex: 0,
  readOnly: false,
})

const emit = defineEmits(['generateChapter', 'showVersionDetail', 'evaluateChapter', 'retryFromNode'])

const notifyWhenDone = ref(false)

const activeStepKey = ref<string | null>(null)

const { elapsedText, etaText } = useGenerationTiming(props)

const selectStep = (key: string, index: number) => {
  if (stepState(key, index).tone !== 'waiting') {
    activeStepKey.value = key
  }
}

const pipelineSteps = computed(() => {
  if (props.status === 'finalizing') {
    return [
      { key: 'real_summary', label: '生成章节梳理' },
      { key: 'finalize_memory', label: '更新记忆快照' },
      { key: 'chapter_ingest', label: '写入章节索引' },
      { key: 'foreshadowing_sync', label: '同步伏笔' },
    ]
  }
  return [
    { key: 'context_prep', label: '整理前文' },
    { key: 'director_mission', label: '规划剧情' },
    { key: 'rag_retrieval', label: '调用设定' },
    { key: 'draft_generation', label: '生成正文' },
    { key: 'quality_review', label: 'AI评审' },
    { key: 'review_refinement', label: '修复润色' },
  ]
})

const {
  isFailureStatus,
  terminalFailedTrace,
  failureReason,
  failureScenario,
  failedVersionCards,
  stepExists,
} = useGenerationFailure(props, pipelineSteps)

const {
  currentStepKey,
  stepState,
  canRetryFromNode,
  shouldShowManualConfirmBadge,
  stepTooltipText,
} = useGenerationPipeline(props, pipelineSteps, {
  isFailureStatus,
  terminalFailedTrace,
  stepExists,
  failureReason,
  failureScenario,
})

const retryGenerateLabel = computed(() =>
  props.status === 'evaluation_failed' ? '放弃本轮草稿并重新生成' : '整章重新生成',
)

watch(
  () => currentStepKey.value,
  (newKey) => {
    if (!props.readOnly) {
      activeStepKey.value = newKey
    }
  },
  { immediate: true }
)

watch(
  () => props.readOnly,
  (readOnly) => {
    if (!readOnly && !activeStepKey.value) {
      activeStepKey.value = currentStepKey.value
    }
  },
)

const activeStepTraces = computed(() => {
  const key = activeStepKey.value || currentStepKey.value
  return props.generationTraces.filter((trace) => normalizePipelineStepKey(trace.node_key) === key)
})

const activeTrace = computed(() => {
  const key = activeStepKey.value || currentStepKey.value
  const traces = activeStepTraces.value
  if (isFailureStatus.value && key === currentStepKey.value) {
    const failedTrace = [...traces].reverse().find((trace) => trace.status === 'failed')
    if (failedTrace) return failedTrace
    return terminalFailedTrace.value
  }
  return traces.length ? traces[traces.length - 1] : null
})

const activeStepDetails = computed<ActiveStepDetails>(() => {
  const key = activeStepKey.value || currentStepKey.value
  const stepConfig = STEP_DETAILS[key] ?? {
    summary: '正在处理当前章节请求。',
    inputs: '系统自动组装',
    outputs: '处理中',
    next: '请稍候',
  }
  const trace = activeTrace.value

  if (trace) {
    const metadata = traceMetadata(trace)
    return {
      label: PIPELINE_LABELS[key] || trace.node_label || stepConfig.summary,
      summary: metadata.summary || (trace.status === 'failed'
        ? `真实运行记录：${trace.node_label || stepConfig.summary} 执行失败`
        : `真实运行记录：${trace.node_label || stepConfig.summary}`),
      callType: resolveTraceCallType(trace),
      llmUsage: traceUsesLlm(trace) ? '是' : '否',
      status: TRACE_STATUS_LABELS[trace.status] || trace.status || '',
      systemDuration: formatSystemDuration(resolveTraceDurationMs(trace)),
      inputs: formatTraceInputs(trace),
      actions: formatTraceActions(trace),
      outputs: formatTraceOutputs(trace),
    }
  }

  if (isFailureStatus.value && key === currentStepKey.value) {
    const label = PIPELINE_LABELS[key] || stepConfig.summary
    const reason = failureReason.value || failureScenario.value.description
    return {
      label,
      summary: `${label}执行失败，当前章节流程已停止。`,
      callType: '失败节点',
      llmUsage: key === 'quality_review' || key === 'review_refinement' ? '是' : '待确认',
      status: '失败',
      systemDuration: '未记录',
      inputs: stepConfig.inputs,
      actions: '该失败节点未返回完整 trace，前端已按章节失败状态显示兜底详情。',
      outputs: `错误：\n${reason}`,
    }
  }

  return {
    label: PIPELINE_LABELS[key] || stepConfig.summary,
    summary: `暂未收到 ${PIPELINE_LABELS[key] || stepConfig.summary} 的真实运行记录`,
    callType: '等待记录',
    llmUsage: '待记录',
    status: '',
    systemDuration: '未记录',
    inputs: '该节点暂未收到真实运行记录。',
    actions: '该节点暂未收到真实运行记录。',
    outputs: '该节点暂未收到真实运行记录。',
  }
})

const moveToBackground = () => {
  globalAlert.showToast('已切换为后台生成，章节完成后会在列表中显示状态。', 'success')
}

const handleFailedGenerateAction = async () => {
  if (props.chapterNumber === null) return
  if (props.status === 'evaluation_failed') {
    const confirmed = await globalAlert.showConfirm(
      '重新生成会放弃本轮已生成的候选正文，并用新生成结果替换它们。确认要重新生成本章吗？',
      '放弃本轮草稿',
    )
    if (!confirmed) return
  }
  emit('generateChapter', props.chapterNumber)
}

const cancelGeneration = async () => {
  const confirmed = await globalAlert.showConfirm(
    '当前版本暂不支持中途取消生成。你可以先转入后台，或等待本轮生成完成后再处理。',
    '暂不支持取消',
  )
  if (confirmed) {
    globalAlert.showToast('建议使用"转入后台生成"避免阻塞当前写作。', 'info')
  }
}

const toggleNotify = () => {
  notifyWhenDone.value = !notifyWhenDone.value
  localStorage.setItem('writing-desk-notify-when-done', notifyWhenDone.value ? '1' : '0')
  if (notifyWhenDone.value) {
    globalAlert.showToast('已开启完成通知。', 'success')
  } else {
    globalAlert.showToast('已关闭完成通知。', 'info')
  }
}

watch(
  () => props.status,
  async (nextStatus, prevStatus) => {
    if (
      notifyWhenDone.value &&
      prevStatus &&
      ['generating', 'evaluating', 'selecting'].includes(prevStatus) &&
      (nextStatus === 'waiting_for_confirm' || nextStatus === 'successful')
    ) {
      await globalAlert.showSuccess(`第${props.chapterNumber}章已完成 AI 评审和修复润色。`, '生成完成')
    }
  },
)

onMounted(() => {
  notifyWhenDone.value = localStorage.getItem('writing-desk-notify-when-done') === '1'
})
</script>

<style scoped>
.chapter-console {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-4);
}

.chapter-console__pipeline-retry {
  margin-left: auto;
  padding: 2px 10px;
  font-size: 12px;
  line-height: 1.4;
  color: var(--md-sys-color-primary, #2563eb);
  background: transparent;
  border: 1px solid var(--md-sys-color-primary, #2563eb);
  border-radius: 999px;
  cursor: pointer;
  transition: opacity 0.15s ease;
}

.chapter-console__pipeline-retry:hover:not(:disabled) {
  opacity: 0.8;
}

.chapter-console__pipeline-retry:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.chapter-console__header,
.chapter-console__summary-card,
.chapter-console__task-card,
.chapter-console__pipeline-card,
.chapter-console__explain-card,
.chapter-console__log {
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-sm);
  background: color-mix(in srgb, var(--md-surface) 96%, transparent);
  box-shadow: var(--md-elevation-1);
}

.chapter-console__pipeline-card {
  position: relative;
  z-index: 5;
  overflow: visible !important;
}

.chapter-console__header {
  padding: var(--md-spacing-4);
  display: flex;
  justify-content: space-between;
  gap: var(--md-spacing-3);
  align-items: flex-start;
}

.chapter-console__title {
  margin: 0;
  color: var(--md-on-surface);
  font-size: var(--md-title-large);
}

.chapter-console__status-line {
  margin: 8px 0 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.chapter-console__state-badge {
  display: inline-flex;
  align-items: center;
  height: 30px;
  padding: 0 12px;
  border-radius: var(--md-radius-full);
  background: var(--md-primary-container);
  color: var(--md-on-primary-container);
  font-size: var(--md-label-medium);
  font-weight: 700;
  white-space: nowrap;
}

.chapter-console__summary-card,
.chapter-console__pipeline-card,
.chapter-console__explain-card,
.chapter-console__log {
  padding: var(--md-spacing-4);
}

.chapter-console__summary-label {
  margin: 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-medium);
}

.chapter-console__summary-body {
  margin: var(--md-spacing-2) 0 0;
  color: var(--md-on-surface);
  line-height: 1.8;
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
    rgba(255, 255, 255, 0.95) 50%,
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
  box-shadow: 1px 1px 0 rgba(28, 32, 34, 0.18);
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

.chapter-console--read-only {
  gap: var(--md-spacing-3);
}

.chapter-console--read-only .chapter-console__pipeline-card,
.chapter-console--read-only .chapter-console__inspector-card {
  border-radius: 0;
  box-shadow: none;
}

.chapter-console--read-only .chapter-console__pipeline-card {
  padding: var(--md-spacing-3) var(--md-spacing-4);
  background-color: color-mix(in srgb, var(--md-surface-container-low) 66%, var(--md-surface));
}

.chapter-console--read-only .chapter-console__pipeline {
  margin-top: var(--md-spacing-3);
}

.chapter-console--read-only .chapter-console__pipeline-item {
  padding-bottom: 8px;
}

.chapter-console--read-only .chapter-console__pipeline-title {
  font-size: var(--md-label-medium);
  font-weight: 600;
}

@media (hover: hover) and (min-width: 834px) {
  .chapter-console__pipeline-tooltip-wrapper {
    cursor: pointer;
  }
}




.chapter-console__log summary {
  cursor: pointer;
  color: var(--md-primary-dark);
  font-weight: 600;
}

.chapter-console__log-body {
  margin-top: var(--md-spacing-3);
  border-top: 1px solid var(--md-outline-variant);
  padding-top: var(--md-spacing-3);
}

.chapter-console__log-body p {
  margin: 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
  line-height: 1.7;
}

.chapter-console__log-body p + p {
  margin-top: 4px;
}

.chapter-console__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--md-spacing-2);
}

.chapter-console__actions .is-enabled {
  border-color: color-mix(in srgb, var(--md-success) 28%, var(--md-outline-variant));
}



@media (prefers-reduced-motion: reduce) {
  .chapter-console__pipeline-item.is-in-progress .chapter-console__dot {
    animation: none;
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
      rgba(255, 255, 255, 0.95) 50%,
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

  .chapter-console__pipeline-meta {
    margin-top: 6px;
    align-self: flex-start;
    justify-content: flex-start;
  }

  .chapter-console__actions {
    flex-direction: column;
  }

  .chapter-console__actions .md-btn {
    width: 100%;
  }
}

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

/* 节点详情面板样式 */
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

.chapter-console__inspector-card {
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-md, 8px);
  background: color-mix(in srgb, var(--md-surface) 95%, transparent);
  padding: var(--md-spacing-4);
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-3);
  animation: fadeInInspector 0.3s ease-out;
}

.chapter-console__inspector-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px dashed var(--md-outline-variant);
  padding-bottom: var(--md-spacing-2);
  flex-wrap: wrap;
  gap: 8px;
}

.chapter-console__inspector-title-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.chapter-console__inspector-badge {
  font-size: var(--md-label-small);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  background-color: var(--md-primary-container);
  color: var(--md-on-primary-container);
  padding: 2px 6px;
  border-radius: var(--md-radius-small, 4px);
}

.chapter-console__inspector-title {
  margin: 0;
  color: var(--md-on-surface);
  font-size: var(--md-title-medium);
  font-weight: 600;
}

.chapter-console__inspector-subtitle {
  font-size: var(--md-body-small);
  color: var(--md-on-surface-variant);
}

.chapter-console__inspector-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chapter-console__call-type,
.chapter-console__llm-usage,
.chapter-console__trace-status {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-xs);
  background-color: var(--md-surface-container-low);
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-small);
  font-weight: 700;
}

.chapter-console__trace-status.is-failed {
  border-color: color-mix(in srgb, var(--md-error) 36%, var(--md-outline-variant));
  background-color: color-mix(in srgb, var(--md-error) 10%, var(--md-surface));
  color: var(--md-error);
}

.chapter-console__inspector-grids {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--md-spacing-3);
}

@media (max-width: 833px) {
  .chapter-console__inspector-grids {
    grid-template-columns: 1fr;
  }
}

.chapter-console__inspector-panel {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.chapter-console__panel-title {
  font-size: var(--md-label-medium);
  font-weight: 600;
  color: var(--md-primary-dark);
  display: flex;
  align-items: center;
  gap: 6px;
}

.chapter-console__panel-code-wrapper {
  background-color: color-mix(in srgb, var(--md-surface-container-highest) 35%, var(--md-surface-container-low));
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-md, 6px);
  padding: var(--md-spacing-3);
  height: 240px;
  overflow: auto;
}

.chapter-console__panel-code {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 13px;
  line-height: 1.6;
  color: var(--md-on-surface);
}

@keyframes fadeInTooltip {
  to {
    opacity: 1;
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

@keyframes fadeInInspector {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
