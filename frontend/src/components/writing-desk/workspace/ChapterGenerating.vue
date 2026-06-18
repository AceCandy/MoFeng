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
    <article v-else-if="!props.readOnly" class="chapter-console__preview-card">
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
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import Tooltip from '@/components/Tooltip.vue'
import type { Chapter, ChapterGenerationTrace, ChapterVersion } from '@/api/novel'
import { globalAlert } from '@/composables/useAlert'
import { cleanVersionContent, formatChapterGenerationError } from '@/utils/chapter'
import { countNonWhitespaceChars } from '@/utils/text'

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

const emit = defineEmits(['generateChapter', 'showVersionDetail', 'evaluateChapter'])

const clockNow = ref(Date.now())
const localStartAt = ref(Date.now())
const notifyWhenDone = ref(false)
let timer: number | null = null

const activeStepKey = ref<string | null>(null)

const selectStep = (key: string, index: number) => {
  if (stepState(key, index).tone !== 'waiting') {
    activeStepKey.value = key
  }
}

const STAGE_CONFIG: Record<
  'generating' | 'evaluating' | 'selecting' | 'finalizing',
  { start: number; end: number; expectedSeconds: number; label: string }
> = {
  generating: { start: 8, end: 78, expectedSeconds: 190, label: '生成正文' },
  evaluating: { start: 78, end: 92, expectedSeconds: 55, label: 'AI评审' },
  selecting: { start: 92, end: 98, expectedSeconds: 38, label: '待人工确认' },
  finalizing: { start: 90, end: 99, expectedSeconds: 180, label: '同步定稿' },
}

const PIPELINE_LABELS: Record<string, string> = {
  context_prep: '整理前文',
  director_mission: '规划剧情',
  rag_retrieval: '调用设定',
  draft_generation: '生成正文',
  quality_review: 'AI评审',
  review_refinement: '修复润色',
  auto_optimizing: '修复润色',
  persist_versions: '保存草稿',
  save_draft: '保存草稿',
  waiting_for_confirm: '等待确认',
  selecting_version: '等待确认',
  confirm_finalize: '确认定稿',
  real_summary: '生成章节梳理',
  finalize_memory: '更新记忆快照',
  chapter_ingest: '写入章节索引',
  foreshadowing_sync: '同步伏笔',
  finalized: '定稿完成',
  finalization_error: '定稿失败',
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

type StepDetail = {
  summary: string
  inputs: string
  outputs: string
  next: string
}

type ParsedStepPayload = {
  raw: string
  baseKey: string
  meta: Record<string, string>
}

type TraceMetadata = Record<string, any>

type ActiveStepDetails = {
  label: string
  summary: string
  callType: string
  llmUsage: string
  status: string
  systemDuration: string
  inputs: string
  actions: string
  outputs: string
}

const TRACE_CALL_TYPE_LABELS: Record<string, string> = {
  database_context: '数据库读取',
  database_write: '数据库写入',
  rag_retrieval: 'RAG 检索',
  chat_llm: '聊天模型',
  embedding: '向量模型',
  preview_generation: '预览生成',
  version_review: '版本评审',
  chapter_optimization: '修复润色',
  confirm_finalize: '确认定稿',
  real_summary: '章节梳理',
  finalize_memory: '记忆快照',
  chapter_ingest: '章节索引',
  foreshadowing_sync: '伏笔同步',
  finalized: '定稿完成',
  finalization_error: '定稿失败',
}

const TRACE_STATUS_LABELS: Record<string, string> = {
  success: '成功',
  failed: '失败',
}

const STEP_DETAILS: Record<string, StepDetail> = {
  context_prep: {
    summary: '整理前文重点剧情、角色状态和本章任务。',
    inputs: '上章摘要 + 本章标题与摘要',
    outputs: '本章上下文草案',
    next: '规划剧情',
  },
  director_mission: {
    summary: '明确本章冲突、节奏和人物推进目标。',
    inputs: '章节任务 + 蓝图角色关系',
    outputs: '章节创作方案',
    next: '调用设定',
  },
  rag_retrieval: {
    summary: '检索与本章相关的设定、伏笔和历史片段。',
    inputs: '章节任务关键词',
    outputs: '可引用上下文',
    next: '生成正文',
  },
  draft_generation: {
    summary: '根据任务、前文、人物状态与伏笔生成第一版正文。',
    inputs: '章节方案 + 相关设定',
    outputs: '章节草稿版本',
    next: 'AI评审',
  },
  quality_review: {
    summary: '单版本生成修改意见，多版本对比选优并生成修改建议。',
    inputs: '候选正文版本',
    outputs: '评审结果与修改建议',
    next: '修复润色',
  },
  review_refinement: {
    summary: '根据 AI 评审建议自动修复润色推荐版本。',
    inputs: '推荐版本 + AI 修改建议',
    outputs: '修复润色后的最终正文',
    next: '人工编辑或确认定稿',
  },
  persist_versions: {
    summary: '将修复润色后的草稿写入版本库，进入人工确认节点。',
    inputs: '候选版本 + 推荐索引',
    outputs: '待人工确认状态',
    next: '人工确认定稿',
  },
  save_draft: {
    summary: 'AI 产出已结束，当前可人工编辑草稿或确认定稿。',
    inputs: '修复润色后的正文 + 推荐索引',
    outputs: '待人工确认状态',
    next: '人工编辑或确认定稿',
  },
  waiting_for_confirm: {
    summary: '草稿保存完成，等待你确认定稿。',
    inputs: '新草稿版本',
    outputs: '待确认状态',
    next: '确认后进入同步定稿',
  },
  confirm_finalize: {
    summary: '确认最终草稿并锁定本次定稿正文。',
    inputs: '候选版本 + 手动修改正文',
    outputs: '最终正文与选中版本',
    next: '生成章节梳理',
  },
  real_summary: {
    summary: '基于最终正文生成真实章节梳理。',
    inputs: '最终正文',
    outputs: 'Chapter.real_summary',
    next: '更新记忆',
  },
  finalize_memory: {
    summary: '更新全局摘要、角色状态、剧情线和章节快照。',
    inputs: '最终正文 + 当前项目记忆',
    outputs: '项目记忆与章节快照',
    next: '写入索引',
  },
  chapter_ingest: {
    summary: '写入章节向量索引，供后续检索使用。',
    inputs: '最终正文 + 章节梳理',
    outputs: '章节检索索引',
    next: '同步伏笔',
  },
  foreshadowing_sync: {
    summary: '抽取新伏笔并判断历史伏笔推进或回收。',
    inputs: '最终正文 + 历史活跃伏笔',
    outputs: '伏笔表与状态历史',
    next: '定稿完成',
  },
  finalized: {
    summary: '所有后处理完成，章节进入已完成状态。',
    inputs: '后处理统计',
    outputs: 'successful',
    next: '进入正文查看',
  },
  finalization_error: {
    summary: '定稿后处理失败，章节保留草稿待确认。',
    inputs: '失败节点上下文',
    outputs: '错误详情',
    next: '修改后重试',
  },
}

const parseStepPayload = (rawStep?: string | null): ParsedStepPayload => {
  const raw = (rawStep ?? '').trim()
  if (!raw) {
    return { raw: '', baseKey: '', meta: {} }
  }
  const tokens = raw.split('|').map((item) => item.trim()).filter(Boolean)
  const baseKey = tokens[0] ?? raw
  const meta: Record<string, string> = {}
  for (const token of tokens.slice(1)) {
    const delimiter = token.indexOf('=')
    if (delimiter <= 0) continue
    const key = token.slice(0, delimiter).trim()
    const value = token.slice(delimiter + 1).trim()
    if (key && value) {
      meta[key] = value
    }
  }
  return { raw, baseKey, meta }
}

const parseBackendTimestampToMs = (raw?: string | null): number | null => {
  if (!raw) return null
  const normalized = raw.trim()
  if (!normalized) return null
  const hasExplicitTimezone = /([zZ]|[+\-]\d{2}:\d{2})$/.test(normalized)
  const isoCandidate = normalized.includes('T') ? normalized : normalized.replace(' ', 'T')
  const parseTarget = hasExplicitTimezone ? isoCandidate : `${isoCandidate}+08:00`
  const ts = Date.parse(parseTarget)
  return Number.isFinite(ts) ? ts : null
}

const parsedStepPayload = computed(() => parseStepPayload(props.generationStep))

const isFailureStatus = computed(
  () => props.status === 'failed' || props.status === 'evaluation_failed',
)

const normalizePipelineStepKey = (key?: string | null) => {
  const normalized = (key || '').trim()
  if (normalized === 'persist_versions') return 'save_draft'
  if (normalized === 'evaluation_failed' || normalized === 'evaluating') return 'quality_review'
  if (normalized === 'auto_optimizing') return 'review_refinement'
  if (normalized === 'optimization_done') return 'review_refinement'
  if (normalized === 'failed') return ''
  return normalized
}

const stepExists = (key: string) => pipelineSteps.value.some((item) => item.key === key)

const terminalFailedTrace = computed(() => {
  return [...props.generationTraces].reverse().find((trace) => trace.status === 'failed') ?? null
})

const failureReason = computed(() => {
  const traceError = terminalFailedTrace.value
    ?.error
    ?.trim()
  if (isFailureStatus.value && traceError) {
    return formatChapterGenerationError(traceError)
  }

  const step = (props.generationStep || '').trim()
  if (!step) {
    return ''
  }

  const parsed = parseStepPayload(step)
  let rawError = step
  if (parsed.meta.error) {
    rawError = parsed.meta.error
  } else if (parsed.baseKey && stepExists(normalizePipelineStepKey(parsed.baseKey))) {
    const pipeIdx = step.indexOf('|')
    if (pipeIdx >= 0) {
      rawError = step.slice(pipeIdx + 1)
    }
  }

  if (
    isFailureStatus.value &&
    (parsed.baseKey === 'failed' || parsed.baseKey === 'evaluation_failed') &&
    !parsed.meta.error
  ) {
    return ''
  }

  // 仅在非明确失败状态下，才利用正则过滤标准运行步骤名
  if (!isFailureStatus.value) {
    if (/^[a-z_]+(?:\|.*)?$/i.test(step)) {
      return ''
    }
  }

  return formatChapterGenerationError(rawError)
})

const failureScenario = computed(() => {
  const step = (props.generationStep || '').toLowerCase()

  if (failureReason.value) {
    return {
      title: '已定位错误原因',
      description: failureReason.value,
    }
  }

  if (props.status === 'evaluation_failed') {
    return {
      title: 'AI评审失败',
      description: '评审节点未返回更具体的失败原因，请查看节点详情、后端日志，或重新评审。',
    }
  }

  if (step.includes('timeout') || step.includes('time_out')) {
    return {
      title: '模型超时',
      description: '模型响应超时，可能是瞬时拥塞或模型负载过高。',
    }
  }

  if (step.includes('context') || step.includes('length') || step.includes('token')) {
    return {
      title: '上下文过长',
      description: '本章输入上下文超出稳定范围，请精简前文摘要后再点击重试。',
    }
  }

  if (step.includes('persist') || step.includes('save')) {
    return {
      title: '保存失败',
      description: '草稿生成后写入版本库失败，请确认当前章节状态后再点击重试生成。',
    }
  }

  return {
    title: '生成流程中断',
    description: '本轮草稿生成未完成，可直接重试本章生成。',
  }
})

const retryGenerateLabel = computed(() =>
  props.status === 'evaluation_failed' ? '放弃本轮草稿并重新生成' : '重试生成本章',
)

const isWaitingForManualConfirm = computed(() => props.status === 'waiting_for_confirm')

const shouldShowManualConfirmBadge = (key: string) =>
  key === 'review_refinement' && isWaitingForManualConfirm.value

const currentStepKey = computed(() => {
  const traceStepKey = normalizePipelineStepKey(terminalFailedTrace.value?.node_key)
  if (isFailureStatus.value && traceStepKey && stepExists(traceStepKey)) {
    return traceStepKey
  }
  if (props.status === 'evaluation_failed') {
    return 'quality_review'
  }
  const stepKey = normalizePipelineStepKey(parsedStepPayload.value.baseKey)
  if (stepKey === 'waiting_for_confirm' || stepKey === 'selecting_version') {
    return 'review_refinement'
  }
  if (props.status === 'finalizing') {
    if (stepKey === 'confirm_finalize') {
      return 'real_summary'
    }
    if (stepKey && pipelineSteps.value.some((item) => item.key === stepKey)) {
      return stepKey
    }
    return 'real_summary'
  }
  if (stepKey && pipelineSteps.value.some((item) => item.key === stepKey)) {
    return stepKey
  }

  if (props.status === 'failed') {
    const errorMsg = (props.generationStep || '').toLowerCase()
    if (errorMsg.includes('版本') || errorMsg.includes('字数') || errorMsg.includes('生成章节') || errorMsg.includes('draft')) {
      return 'draft_generation'
    }
    if (errorMsg.includes('评审') || errorMsg.includes('评分') || errorMsg.includes('连贯') || errorMsg.includes('evaluation') || errorMsg.includes('review')) {
      return 'quality_review'
    }
    if (errorMsg.includes('润色') || errorMsg.includes('修复') || errorMsg.includes('optimization') || errorMsg.includes('refinement')) {
      return 'review_refinement'
    }
    if (errorMsg.includes('保存') || errorMsg.includes('存储') || errorMsg.includes('save') || errorMsg.includes('persist')) {
      return 'save_draft'
    }
    if (errorMsg.includes('设定') || errorMsg.includes('retrieval') || errorMsg.includes('rag')) {
      return 'rag_retrieval'
    }
    if (errorMsg.includes('剧情') || errorMsg.includes('规划') || errorMsg.includes('director')) {
      return 'director_mission'
    }
    if (errorMsg.includes('前文') || errorMsg.includes('上下文') || errorMsg.includes('context')) {
      return 'context_prep'
    }
    return 'draft_generation'
  }

  if (props.status === 'evaluating') return 'quality_review'
  if (props.status === 'selecting' || props.status === 'waiting_for_confirm') return 'review_refinement'
  return 'context_prep'
})

const stepTooltipText = (key: string, index: number) => {
  const state = stepState(key, index)
  const label = PIPELINE_LABELS[key] || STEP_DETAILS[key]?.summary || '当前节点'
  if (state.tone === 'failed') {
    const reason = failureReason.value || failureScenario.value.description
    return `${label}失败：${reason}`
  }
  if (shouldShowManualConfirmBadge(key)) {
    return `${label}已完成：当前待人工确认，可人工编辑草稿或确认定稿。`
  }
  return STEP_DETAILS[key]?.summary || ''
}

const failedVersionCards = computed(() =>
  props.availableVersions
    .map((version, index) => {
      const content = cleanVersionContent(version.content || '').trim()
      if (!content) return null
      const preview = content.replace(/\s+/g, ' ').slice(0, 96)
      return {
        index,
        displayIndex: index + 1,
        style: version.style || '标准',
        wordCount: countNonWhitespaceChars(content),
        preview: preview ? `${preview}${content.length > 96 ? '...' : ''}` : '暂无正文预览',
      }
    })
    .filter((item): item is NonNullable<typeof item> => item !== null),
)

const currentStepIndex = computed(() => {
  const index = pipelineSteps.value.findIndex((item) => item.key === currentStepKey.value)
  return index >= 0 ? index : 0
})

const completedSteps = computed(() => Math.max(0, currentStepIndex.value))

const parsedGenerationStartedAt = computed(() => parseBackendTimestampToMs(props.generationStartedAt))
const parsedStatusUpdatedAt = computed(() => parseBackendTimestampToMs(props.statusUpdatedAt))

const startTimestamp = computed(
  () => parsedGenerationStartedAt.value ?? parsedStatusUpdatedAt.value ?? localStartAt.value,
)

const elapsedSeconds = computed(() => {
  const delta = Math.floor((clockNow.value - startTimestamp.value) / 1000)
  return Math.max(0, delta)
})

const backendProgress = computed(() => {
  if (props.generationProgress === null || props.generationProgress === undefined) return null
  if (!Number.isFinite(props.generationProgress)) return null
  return Math.max(0, Math.min(100, props.generationProgress))
})

const currentStageConfig = computed(() => {
  if (
    props.status === 'generating' ||
    props.status === 'evaluating' ||
    props.status === 'selecting' ||
    props.status === 'finalizing'
  ) {
    return STAGE_CONFIG[props.status]
  }
  return null
})

const progressPercent = computed(() => {
  if (backendProgress.value !== null) {
    return backendProgress.value
  }
  const config = currentStageConfig.value
  if (!config) return 12
  const span = config.end - config.start
  const ratio = Math.min(elapsedSeconds.value / config.expectedSeconds, 0.98)
  return config.start + span * ratio
})

const activeStageLabel = computed(() => {
  const key = currentStepKey.value
  return PIPELINE_LABELS[key] || currentStageConfig.value?.label || '处理中'
})

const etaText = computed(() => {
  if (backendProgress.value !== null && backendProgress.value > 4 && elapsedSeconds.value > 8) {
    const estimatedTotal = Math.ceil((elapsedSeconds.value * 100) / backendProgress.value)
    const remain = Math.max(0, estimatedTotal - elapsedSeconds.value)
    if (remain < 60) return '约 1 分钟内'
    return `约 ${Math.ceil(remain / 60)} 分钟`
  }

  const config = currentStageConfig.value
  if (!config) return '约 2 分钟'
  const remain = config.expectedSeconds - elapsedSeconds.value
  if (remain <= 0) return '即将完成'
  if (remain < 60) return '不足 1 分钟'
  return `约 ${Math.ceil(remain / 60)} 分钟`
})

const elapsedText = computed(() => {
  const total = elapsedSeconds.value
  const mins = Math.floor(total / 60)
  const secs = total % 60
  return `${mins} 分 ${String(secs).padStart(2, '0')} 秒`
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

const isPlainTraceObject = (value: unknown): value is TraceMetadata => {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

const traceMetadata = (trace: ChapterGenerationTrace): TraceMetadata => {
  return isPlainTraceObject(trace.metadata) ? trace.metadata : {}
}

const resolveTraceDurationMs = (trace: ChapterGenerationTrace): number | null => {
  if (typeof trace.duration_ms === 'number' && Number.isFinite(trace.duration_ms)) {
    return Math.max(0, Math.round(trace.duration_ms))
  }
  const metadata = traceMetadata(trace)
  if (typeof metadata.duration_ms === 'number' && Number.isFinite(metadata.duration_ms)) {
    return Math.max(0, Math.round(metadata.duration_ms))
  }
  const startedAt = parseBackendTimestampToMs(trace.started_at)
  const endedAt = parseBackendTimestampToMs(trace.ended_at)
  if (startedAt === null || endedAt === null) {
    return null
  }
  return Math.max(0, endedAt - startedAt)
}

const formatSystemDuration = (durationMs: number | null): string => {
  if (durationMs === null) {
    return '未记录'
  }
  if (durationMs < 1000) {
    return `${durationMs} ms`
  }
  if (durationMs < 60_000) {
    const seconds = durationMs / 1000
    const display = Number.isInteger(seconds) ? String(seconds) : seconds.toFixed(1)
    return `${display} 秒`
  }
  const totalSeconds = Math.round(durationMs / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes} 分 ${String(seconds).padStart(2, '0')} 秒`
}

const traceUsesLlm = (trace: ChapterGenerationTrace): boolean => {
  if (trace.uses_llm === true || trace.uses_llm === false) {
    return trace.uses_llm
  }
  const metadata = traceMetadata(trace)
  if (metadata.uses_llm === true || metadata.uses_llm === false) {
    return metadata.uses_llm
  }
  if (Array.isArray(metadata.model_calls)) {
    return metadata.model_calls.length > 0
  }
  return Boolean(trace.system_prompt?.trim() || trace.user_prompt?.trim() || trace.raw_response?.trim())
}

const formatTraceValue = (value: unknown): string => {
  if (value === null || value === undefined || value === '') return '无'
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

const formatTracePayload = (payload: unknown, emptyText: string): string => {
  if (!isPlainTraceObject(payload)) {
    return payload ? formatTraceValue(payload) : emptyText
  }
  const lines = Object.entries(payload)
    .map(([key, value]) => `${key}：${formatTraceValue(value)}`)
    .filter(Boolean)
  return lines.length ? lines.join('\n\n') : emptyText
}

const firstTextValue = (...values: unknown[]): string => {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) {
      return value.trim()
    }
  }
  return ''
}

const toDisplayVersionNumber = (value: unknown): number | null => {
  const index = Number(value)
  if (!Number.isInteger(index) || index < 0) {
    return null
  }
  return index + 1
}

const getTraceOutputPayload = (trace: ChapterGenerationTrace): TraceMetadata | null => {
  const payload = traceMetadata(trace).output_payload
  return isPlainTraceObject(payload) ? payload : null
}

const getTraceOutputText = (trace: ChapterGenerationTrace, ...payloadKeys: string[]): string => {
  const payload = getTraceOutputPayload(trace)
  const payloadValues = payloadKeys.map((key) => payload?.[key])
  const rawText = firstTextValue(trace.cleaned_output, ...payloadValues, trace.raw_response)
  return cleanVersionContent(rawText).trim()
}

const formatDraftGenerationOutputs = (trace: ChapterGenerationTrace) => {
  const text = getTraceOutputText(trace, 'full_chapter', 'content', 'chapter_content')
  return text ? `AI生成正文：\n${text}` : '该节点未记录 AI 生成正文。'
}

const formatAiReviewOutputs = (trace: ChapterGenerationTrace) => {
  const payload = getTraceOutputPayload(trace)
  const summaries = payload?.review_summaries
  const aiReview = isPlainTraceObject(summaries) && isPlainTraceObject(summaries.ai_review)
    ? summaries.ai_review
    : null
  const lines: string[] = []
  const bestVersionNumber = toDisplayVersionNumber(
    payload?.best_version_index ?? aiReview?.best_version_index,
  )

  if (bestVersionNumber !== null) {
    lines.push(`推荐版本：版本 ${bestVersionNumber}`)
  }

  if (aiReview) {
    const evaluation = firstTextValue(
      aiReview.evaluation,
      aiReview.overall_evaluation,
      aiReview.reason_for_choice,
    )
    const suggestions = firstTextValue(
      aiReview.suggestions,
      aiReview.refinement_suggestions,
    )
    const recommendation = firstTextValue(aiReview.final_recommendation)
    if (evaluation) lines.push(`评审结论：${evaluation}`)
    if (suggestions) lines.push(`修改建议：${suggestions}`)
    if (recommendation) lines.push(`最终建议：${recommendation}`)

    const flaws = Array.isArray(aiReview.flaws) ? aiReview.flaws : []
    if (flaws.length) {
      lines.push(`需修复问题：\n${flaws.map((item) => `- ${formatTraceValue(item)}`).join('\n')}`)
    }

    const versionReviews = Array.isArray(aiReview.version_reviews) ? aiReview.version_reviews : []
    if (versionReviews.length) {
      const reviews = versionReviews
        .map((item) => {
          if (!isPlainTraceObject(item)) return ''
          const versionNumber = Number(item.version_number)
          const title = Number.isInteger(versionNumber) && versionNumber > 0
            ? `版本 ${versionNumber}`
            : '候选版本'
          const review = firstTextValue(item.overall_review)
          return review ? `${title}：${review}` : ''
        })
        .filter(Boolean)
      if (reviews.length) {
        lines.push(`分版本评审：\n${reviews.join('\n')}`)
      }
    }
  }

  if (lines.length) {
    return lines.join('\n\n')
  }

  if (payload) {
    return `评审结论：\n${formatTracePayload(payload, '该节点未记录评审结论。')}`
  }
  return '该节点未记录评审结论。'
}

const formatReviewRefinementOutputs = (trace: ChapterGenerationTrace) => {
  const text = getTraceOutputText(trace, 'optimized_content', 'refined_content', 'final_content')
  const payload = getTraceOutputPayload(trace)
  const lines = text ? [`AI修复后正文：\n${text}`] : ['该节点未记录 AI 修复后正文。']
  const notes = firstTextValue(payload?.optimization_notes, payload?.notes)
  if (notes) {
    lines.push(`修复说明：${notes}`)
  }
  return lines.join('\n\n')
}

const formatManualConfirmationOutputs = (trace: ChapterGenerationTrace) => {
  const payload = getTraceOutputPayload(trace)
  const status = firstTextValue(payload?.status) || 'waiting_for_confirm'
  const lines = [
    `人工确认状态：${status}`,
    '此节点不再产生 AI 正文；你可以人工编辑草稿，或确认定稿。',
  ]
  const versions = Array.isArray(payload?.versions) ? payload.versions : []
  if (versions.length) {
    lines.push(`已保存候选版本：${versions.length} 个`)
  }
  return lines.join('\n\n')
}

const formatModelCall = (call: unknown, index: number): string => {
  if (!isPlainTraceObject(call)) {
    return `模型调用 ${index + 1}：${formatTraceValue(call)}`
  }
  const callType = TRACE_CALL_TYPE_LABELS[String(call.call_type || '')] || call.call_type || '模型调用'
  const pieces = [
    `${call.purpose || call.reason || `模型调用 ${index + 1}`}`,
    `类型：${callType}`,
  ]
  if (call.stage) pieces.push(`stage：${call.stage}`)
  if (call.status) pieces.push(`状态：${call.status}`)
  if (call.temperature !== undefined) pieces.push(`temperature：${call.temperature}`)
  if (call.timeout_seconds !== undefined) pieces.push(`超时：${call.timeout_seconds}s`)
  if (call.max_tokens !== undefined) pieces.push(`max_tokens：${call.max_tokens}`)
  return pieces.join('；')
}

const formatTraceInputs = (trace: ChapterGenerationTrace) => {
  const metadata = traceMetadata(trace)
  const sections: string[] = []
  if (metadata.input_payload !== undefined) {
    sections.push(formatTracePayload(metadata.input_payload, '该节点未记录输入材料。'))
  }
  if (trace.system_prompt?.trim()) {
    sections.push(`模型系统指令：\n${trace.system_prompt.trim()}`)
  }
  if (trace.user_prompt?.trim()) {
    sections.push(`模型用户输入：\n${trace.user_prompt.trim()}`)
  }
  return sections.length ? sections.join('\n\n') : '该节点未记录输入材料。'
}

const formatTraceActions = (trace: ChapterGenerationTrace) => {
  const metadata = traceMetadata(trace)
  const lines: string[] = []
  const actions = Array.isArray(metadata.actions) ? metadata.actions : []
  actions.forEach((action: unknown) => {
    lines.push(`- ${formatTraceValue(action)}`)
  })
  const modelCalls = Array.isArray(metadata.model_calls) ? metadata.model_calls : []
  if (modelCalls.length) {
    lines.push('', '模型/向量调用：')
    modelCalls.forEach((call: unknown, index: number) => {
      lines.push(`- ${formatModelCall(call, index)}`)
    })
  } else if (traceUsesLlm(trace)) {
    lines.push('', '模型/向量调用：已调用，但本条记录未保存模型明细。')
  } else {
    lines.push('', '模型/向量调用：无')
  }
  const dataReads = Array.isArray(metadata.data_reads) ? metadata.data_reads : []
  if (dataReads.length) {
    lines.push('', '读取数据：')
    dataReads.forEach((item: unknown) => lines.push(`- ${formatTraceValue(item)}`))
  }
  const dataWrites = Array.isArray(metadata.data_writes) ? metadata.data_writes : []
  if (dataWrites.length) {
    lines.push('', '写入数据：')
    dataWrites.forEach((item: unknown) => lines.push(`- ${formatTraceValue(item)}`))
  }
  if (metadata.skip_reason) {
    lines.push('', `跳过说明：${formatTraceValue(metadata.skip_reason)}`)
  }
  if (metadata.metrics) {
    lines.push('', `运行指标：\n${formatTraceValue(metadata.metrics)}`)
  }
  return lines.length ? lines.join('\n') : '该节点未记录具体动作。'
}

const formatTraceOutputs = (trace: ChapterGenerationTrace) => {
  const metadata = traceMetadata(trace)
  const sections: string[] = []
  if (trace.error?.trim()) {
    sections.push(`错误：\n${trace.error.trim()}`)
  }
  const normalizedNodeKey = normalizePipelineStepKey(trace.node_key)
  if (!sections.length) {
    if (normalizedNodeKey === 'draft_generation') {
      return formatDraftGenerationOutputs(trace)
    }
    if (normalizedNodeKey === 'quality_review') {
      return formatAiReviewOutputs(trace)
    }
    if (normalizedNodeKey === 'review_refinement') {
      return formatReviewRefinementOutputs(trace)
    }
    if (normalizedNodeKey === 'save_draft') {
      return formatManualConfirmationOutputs(trace)
    }
  }
  if (metadata.output_payload !== undefined) {
    sections.push(formatTracePayload(metadata.output_payload, '该节点未记录产出结果。'))
  }
  if (trace.raw_response?.trim()) {
    sections.push(`模型原始返回：\n${trace.raw_response.trim()}`)
  }
  if (trace.cleaned_output?.trim()) {
    sections.push(`清洗后输出：\n${trace.cleaned_output.trim()}`)
  }
  return sections.length ? sections.join('\n\n') : '该节点未记录产出结果。'
}

const resolveTraceCallType = (trace: ChapterGenerationTrace) => {
  const metadata = traceMetadata(trace)
  const callType = String(metadata.call_type || '')
  if (callType) return TRACE_CALL_TYPE_LABELS[callType] || callType
  if (traceUsesLlm(trace)) return '聊天模型'
  return '运行节点'
}

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

const stepState = (key: string, index: number) => {
  if (props.status === 'failed' || props.status === 'evaluation_failed') {
    if (key === currentStepKey.value) {
      return { tone: 'failed', label: '失败' }
    }
    if (index < currentStepIndex.value) {
      return { tone: 'done', label: '已完成' }
    }
    return { tone: 'waiting', label: '等待中' }
  }

  if (props.readOnly && props.status === 'waiting_for_confirm') {
    if (index <= currentStepIndex.value) {
      return { tone: 'done', label: '已完成' }
    }
    return { tone: 'waiting', label: '等待中' }
  }

  if (index < currentStepIndex.value) {
    return { tone: 'done', label: '已完成' }
  }
  if (index === currentStepIndex.value) {
    return { tone: 'in-progress', label: '进行中' }
  }
  return { tone: 'waiting', label: '等待中' }
}

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
  () => [props.chapterNumber, props.status, props.generationStartedAt],
  () => {
    localStartAt.value = Date.now()
  },
  { immediate: true },
)

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
  timer = window.setInterval(() => {
    clockNow.value = Date.now()
  }, 1000)
})

onUnmounted(() => {
  if (timer !== null) {
    window.clearInterval(timer)
    timer = null
  }
})
</script>

<style scoped>
.chapter-console {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-4);
}

.chapter-console__header,
.chapter-console__summary-card,
.chapter-console__task-card,
.chapter-console__pipeline-card,
.chapter-console__explain-card,
.chapter-console__preview-card,
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
.chapter-console__preview-card,
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

.chapter-console__pipeline-card h4,
.chapter-console__preview-card h4 {
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
  .chapter-console__pipeline-item.is-in-progress .chapter-console__dot,
  .chapter-console__cursor {
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
