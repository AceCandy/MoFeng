<!-- AIMETA P=生成中_章节生成进度|R=进度展示_流式输出|NR=不含生成逻辑|E=component:ChapterGenerating|X=internal|A=生成状态|D=vue|S=dom|RD=./README.ai -->
<template>
  <section class="chapter-console" aria-label="AI章节生成控制台">
    <article class="chapter-console__pipeline-card" aria-label="生成进度">
      <header class="chapter-console__pipeline-header-main">
        <h4>生成进度</h4>
        <div v-if="props.status && ['generating', 'evaluating', 'selecting'].includes(props.status)" class="chapter-console__pipeline-meta-top">
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
            :text="STEP_DETAILS[item.key]?.summary || ''"
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
                  v-if="stepState(item.key, index).tone === 'in-progress'"
                  class="chapter-console__pipeline-badge"
                >
                  进行中
                </span>
              </div>
            </div>
          </Tooltip>
        </li>
      </ol>
    </article>

    <!-- 失败状态展示错误卡片 -->
    <article v-if="props.status === 'failed'" class="chapter-console__failed-card">
      <div class="chapter-console__failed-head">
        <div class="chapter-console__failed-icon-wrap">
          <svg class="chapter-console__failed-icon" fill="currentColor" viewBox="0 0 20 20">
            <path
              fill-rule="evenodd"
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
              clip-rule="evenodd"
            ></path>
          </svg>
        </div>
        <div class="chapter-console__failed-title-row">
          <h4>第{{ chapterNumber }}章生成异常</h4>
          <span class="chapter-console__failed-reason-inline">
            <strong>{{ failureScenario.title }}：</strong>{{ failureScenario.description }}
          </span>
        </div>
      </div>

      <div class="chapter-console__failed-actions">
        <button
          type="button"
          @click="emit('generateChapter', chapterNumber)"
          :disabled="generatingChapter === chapterNumber"
          class="md-btn md-btn-filled md-ripple disabled:opacity-50"
        >
          {{ generatingChapter === chapterNumber ? '重试中...' : '重试生成本章' }}
        </button>
      </div>

    </article>

    <!-- 正常生成中状态展示草稿预览卡片 -->
    <article v-else class="chapter-console__preview-card">
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
    <article v-if="activeStepDetails" class="chapter-console__inspector-card">
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
        <span v-if="activeStepDetails.status" class="chapter-console__trace-status">
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

    <footer v-if="props.status !== 'failed'" class="chapter-console__actions">
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
import type { Chapter, ChapterGenerationTrace } from '@/api/novel'
import { globalAlert } from '@/composables/useAlert'
import { formatChapterGenerationError } from '@/utils/chapter'

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
}

const props = withDefaults(defineProps<Props>(), {
  chapterTitle: '',
  chapterSummary: '',
  chapterContentPreview: '',
  generationTraces: () => [],
  generatingChapter: null,
})

const emit = defineEmits(['generateChapter'])

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
  selecting: { start: 92, end: 98, expectedSeconds: 38, label: '保存草稿' },
  finalizing: { start: 90, end: 99, expectedSeconds: 180, label: '同步定稿' },
}

const PIPELINE_LABELS: Record<string, string> = {
  context_prep: '整理前文',
  director_mission: '规划剧情',
  rag_retrieval: '调用设定',
  draft_generation: '生成正文',
  quality_review: 'AI评审',
  review_refinement: '修复润色',
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

const pipelineSteps = [
  { key: 'context_prep', label: '整理前文' },
  { key: 'director_mission', label: '规划剧情' },
  { key: 'rag_retrieval', label: '调用设定' },
  { key: 'draft_generation', label: '生成正文' },
  { key: 'quality_review', label: 'AI评审' },
  { key: 'review_refinement', label: '修复润色' },
  { key: 'save_draft', label: '保存草稿' },
  { key: 'confirm_finalize', label: '确认定稿' },
  { key: 'real_summary', label: '生成章节梳理' },
  { key: 'finalize_memory', label: '更新记忆快照' },
  { key: 'chapter_ingest', label: '写入章节索引' },
  { key: 'foreshadowing_sync', label: '同步伏笔' },
  { key: 'finalized', label: '定稿完成' },
]

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
    next: '保存草稿',
  },
  persist_versions: {
    summary: '将候选草稿写入版本库，等待人工确认定稿。',
    inputs: '候选版本 + 推荐索引',
    outputs: '待确认草稿',
    next: '人工确认定稿',
  },
  save_draft: {
    summary: '将候选草稿写入版本库，等待人工确认定稿。',
    inputs: '候选版本 + 推荐索引',
    outputs: '待确认草稿',
    next: '人工确认定稿',
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

const failureReason = computed(() => {
  const traceError = [...props.generationTraces]
    .reverse()
    .find((trace) => trace.status === 'failed' && trace.error?.trim())
    ?.error
    ?.trim()
  if (props.status === 'failed' && traceError) {
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
  } else if (parsed.baseKey && pipelineSteps.some((item) => item.key === parsed.baseKey)) {
    const pipeIdx = step.indexOf('|')
    if (pipeIdx >= 0) {
      rawError = step.slice(pipeIdx + 1)
    }
  }

  // 仅在非明确失败状态下，才利用正则过滤标准运行步骤名
  if (props.status !== 'failed') {
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
      title: '质量评审未通过',
      description: '当前草稿在一致性或质量评分上未通过，可以重新生成本章后再评审。',
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

const currentStepKey = computed(() => {
  const stepKey = parsedStepPayload.value.baseKey
  if (stepKey === 'waiting_for_confirm' || stepKey === 'selecting_version') {
    return 'save_draft'
  }
  if (stepKey && pipelineSteps.some((item) => item.key === stepKey)) {
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
  if (props.status === 'selecting' || props.status === 'waiting_for_confirm') return 'save_draft'
  if (props.status === 'finalizing') return parsedStepPayload.value.baseKey || 'confirm_finalize'
  return 'context_prep'
})

const currentStepIndex = computed(() => {
  const index = pipelineSteps.findIndex((item) => item.key === currentStepKey.value)
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
    activeStepKey.value = newKey
  },
  { immediate: true }
)

const activeStepTraces = computed(() => {
  const key = activeStepKey.value || currentStepKey.value
  return props.generationTraces.filter((trace) => trace.node_key === key)
})

const activeTrace = computed(() => {
  const traces = activeStepTraces.value
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
  if (props.status === 'failed') {
    if (key === currentStepKey.value) {
      return { tone: 'failed', label: '失败' }
    }
    if (index < currentStepIndex.value) {
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

const moveToBackground = async () => {
  await globalAlert.showSuccess('已切换为后台生成，章节完成后会在列表中显示状态。', '已转入后台')
}

const cancelGeneration = async () => {
  const confirmed = await globalAlert.showConfirm(
    '当前版本暂不支持中途取消生成。你可以先转入后台，或等待本轮生成完成后再处理。',
    '暂不支持取消',
  )
  if (confirmed) {
    await globalAlert.showAlert('建议使用"转入后台生成"避免阻塞当前写作。', 'info', '提示')
  }
}

const toggleNotify = async () => {
  notifyWhenDone.value = !notifyWhenDone.value
  localStorage.setItem('writing-desk-notify-when-done', notifyWhenDone.value ? '1' : '0')
  if (notifyWhenDone.value) {
    await globalAlert.showSuccess('已开启完成通知。', '通知已开启')
  } else {
    await globalAlert.showAlert('已关闭完成通知。', 'info', '通知已关闭')
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
  background-color: var(--md-error);
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

/* 失败卡片样式 */
.chapter-console__failed-card {
  border: 1px solid color-mix(in srgb, var(--md-error) 24%, var(--md-outline-variant));
  border-radius: var(--md-radius-sm);
  background: color-mix(in srgb, var(--md-surface) 96%, transparent);
  box-shadow: var(--md-elevation-1);
  padding: var(--md-spacing-4);
}

.chapter-console__failed-head {
  display: flex;
  align-items: center;
  gap: var(--md-spacing-3);
}

.chapter-console__failed-icon-wrap {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background-color: var(--md-error-container);
  display: grid;
  place-items: center;
}

.chapter-console__failed-icon {
  width: 22px;
  height: 22px;
  color: var(--md-error);
}

.chapter-console__failed-head h4 {
  margin: 0;
  color: var(--md-on-surface);
  font-size: var(--md-title-medium);
  white-space: nowrap;
}

.chapter-console__failed-title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--md-spacing-2);
  flex: 1;
}

.chapter-console__failed-reason-inline {
  color: var(--md-error);
  font-size: var(--md-body-medium);
  font-weight: 500;
  margin-left: 12px;
  background-color: color-mix(in srgb, var(--md-error) 8%, transparent);
  border: 1px solid color-mix(in srgb, var(--md-error) 18%, transparent);
  padding: 6px 12px;
  border-radius: var(--md-radius-md, 4px);
  line-height: 1.5;
}

@media (max-width: 833px) {
  .chapter-console__failed-title-row {
    flex-direction: column;
    align-items: flex-start;
  }
  .chapter-console__failed-reason-inline {
    margin-left: 0;
    margin-top: 6px;
  }
}

.chapter-console__failed-actions {
  margin-top: var(--md-spacing-4);
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--md-spacing-2);
}

.chapter-console__failed-actions .md-btn {
  min-height: 40px;
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
