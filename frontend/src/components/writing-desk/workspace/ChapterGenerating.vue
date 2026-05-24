<!-- AIMETA P=生成中_章节生成进度|R=进度展示_流式输出|NR=不含生成逻辑|E=component:ChapterGenerating|X=internal|A=生成状态|D=vue|S=dom|RD=./README.ai -->
<template>
  <section class="chapter-console" aria-label="AI章节生成控制台">
    <header class="chapter-console__header">
      <div>
        <h3 class="chapter-console__title">
          第{{ chapterNumber }}章：{{ chapterTitle || '未命名章节' }}
        </h3>
        <p class="chapter-console__status-line">
          状态：{{ statusText.status }}
          <span>·</span>
          <span>字数：{{ generatedWordCount }} 字</span>
        </p>
      </div>
      <span class="chapter-console__state-badge">{{ statusText.badge }}</span>
    </header>

    <article class="chapter-console__summary-card">
      <p class="chapter-console__summary-label">当前摘要</p>
      <p class="chapter-console__summary-body">"{{ displaySummary }}"</p>
    </article>

    <article class="chapter-console__task-card">
      <h4>生成任务状态</h4>
      <p class="chapter-console__task-title">AI 编辑正在构建第{{ chapterNumber }}章第一版草稿</p>
      <div class="chapter-console__task-grid">
        <div>
          <span>当前阶段</span>
          <strong>{{ activeStageLabel }}</strong>
        </div>
        <div>
          <span>已完成</span>
          <strong>{{ completedSteps }} / {{ pipelineSteps.length }} 步</strong>
        </div>
        <div>
          <span>预计剩余</span>
          <strong>{{ etaText }}</strong>
        </div>
        <div>
          <span>已耗时</span>
          <strong>{{ elapsedText }}</strong>
        </div>
      </div>
    </article>

    <article class="chapter-console__pipeline-card" aria-label="阶段式生成流水线">
      <h4>阶段式生成流水线</h4>
      <ol class="chapter-console__pipeline">
        <li
          v-for="(item, index) in pipelineSteps"
          :key="item.key"
          :class="[
            'chapter-console__pipeline-item',
            `is-${stepState(item.key, index).tone}`,
            { 'is-current': stepState(item.key, index).tone === 'in-progress' },
          ]"
        >
          <div class="chapter-console__pipeline-marker">
            <span class="chapter-console__dot"></span>
          </div>
          <div class="chapter-console__pipeline-content">
            <p class="chapter-console__pipeline-title">{{ item.label }}</p>
            <p class="chapter-console__pipeline-state">{{ stepState(item.key, index).label }}</p>
          </div>
        </li>
      </ol>
    </article>

    <article class="chapter-console__explain-card">
      <h4>当前阶段说明</h4>
      <p>{{ stageExplanation }}</p>
    </article>

    <article class="chapter-console__preview-card">
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

    <details class="chapter-console__log" :open="showLog" @toggle="syncLogOpen">
      <summary>{{ showLog ? '收起生成日志' : '查看生成日志' }}</summary>
      <div class="chapter-console__log-body">
        <p><strong>阶段编码：</strong>{{ statusDetails.stageKey }}</p>
        <p><strong>输入：</strong>{{ statusDetails.inputs }}</p>
        <p><strong>输出：</strong>{{ statusDetails.outputs }}</p>
        <p><strong>下一步：</strong>{{ statusDetails.next }}</p>
        <p v-if="runtimeDetailText"><strong>补充信息：</strong>{{ runtimeDetailText }}</p>
      </div>
    </details>

    <footer class="chapter-console__actions">
      <button type="button" class="md-btn md-btn-outlined md-ripple" @click="moveToBackground">
        转入后台生成
      </button>
      <button type="button" class="md-btn md-btn-outlined md-ripple" @click="cancelGeneration">
        取消生成
      </button>
      <button type="button" class="md-btn md-btn-text md-ripple" @click="toggleLog">
        {{ showLog ? '收起生成日志' : '查看生成日志' }}
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
import type { Chapter } from '@/api/novel'
import { globalAlert } from '@/composables/useAlert'
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
}

const props = withDefaults(defineProps<Props>(), {
  chapterTitle: '',
  chapterSummary: '',
  chapterContentPreview: '',
})

const clockNow = ref(Date.now())
const localStartAt = ref(Date.now())
const showLog = ref(false)
const notifyWhenDone = ref(false)
let timer: number | null = null

const STAGE_CONFIG: Record<
  'generating' | 'evaluating' | 'selecting',
  { start: number; end: number; expectedSeconds: number; label: string }
> = {
  generating: { start: 8, end: 78, expectedSeconds: 190, label: '生成正文' },
  evaluating: { start: 78, end: 92, expectedSeconds: 55, label: '检查连贯性' },
  selecting: { start: 92, end: 98, expectedSeconds: 38, label: '等待确认' },
}

const PIPELINE_LABELS: Record<string, string> = {
  context_prep: '整理前文',
  director_mission: '规划剧情',
  rag_retrieval: '调用设定',
  draft_generation: '生成正文',
  quality_review: '检查连贯性',
  persist_versions: '保存草稿',
  waiting_for_confirm: '等待确认',
  selecting_version: '等待确认',
}

const pipelineSteps = [
  { key: 'context_prep', label: '整理前文' },
  { key: 'director_mission', label: '规划剧情' },
  { key: 'rag_retrieval', label: '调用设定' },
  { key: 'draft_generation', label: '生成正文' },
  { key: 'quality_review', label: '检查连贯性' },
  { key: 'persist_versions', label: '保存草稿' },
  { key: 'waiting_for_confirm', label: '等待确认' },
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
    next: '检查连贯性',
  },
  quality_review: {
    summary: '检查人物一致性、叙事逻辑与语义连贯性。',
    inputs: '候选正文版本',
    outputs: '评审结果',
    next: '保存草稿',
  },
  persist_versions: {
    summary: '将新草稿写入版本库并保留历史版本。',
    inputs: '候选版本 + 评审结果',
    outputs: '新版本 Vx',
    next: '等待确认',
  },
  waiting_for_confirm: {
    summary: '草稿保存完成，等待你确认采纳。',
    inputs: '新草稿版本',
    outputs: '待确认状态',
    next: '完成后进入正文查看',
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

const currentStepKey = computed(() => {
  const stepKey = parsedStepPayload.value.baseKey
  if (stepKey) return stepKey
  if (props.status === 'evaluating') return 'quality_review'
  if (props.status === 'selecting') return 'waiting_for_confirm'
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

const generatedWordCount = computed(() => countNonWhitespaceChars(props.chapterContentPreview || ''))

const backendProgress = computed(() => {
  if (props.generationProgress === null || props.generationProgress === undefined) return null
  if (!Number.isFinite(props.generationProgress)) return null
  return Math.max(0, Math.min(100, props.generationProgress))
})

const currentStageConfig = computed(() => {
  if (
    props.status === 'generating' ||
    props.status === 'evaluating' ||
    props.status === 'selecting'
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

const statusText = computed(() => {
  if (props.status === 'generating') {
    return {
      status: '生成第一版草稿中',
      badge: '草稿构建中',
    }
  }
  if (props.status === 'evaluating') {
    return {
      status: '质量评审中',
      badge: '质量检查',
    }
  }
  if (props.status === 'selecting') {
    return {
      status: '结果收敛中',
      badge: '保存与确认',
    }
  }
  return {
    status: '处理中',
    badge: '处理中',
  }
})

const displaySummary = computed(() => {
  const summary = (props.chapterSummary || '').trim()
  if (summary) return summary
  if (props.chapterNumber === 76) {
    return '当死亡计数逼近十万，所有忽略过那串灰字的人都隐约生出不安，像整座服务器都在等待某个古老约定兑现。'
  }
  return '系统正在根据本章目标、人物关系与伏笔信息生成第一版草稿。'
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

const stageExplanation = computed(() => {
  return '正在根据本章任务、前文摘要、人物状态和伏笔信息生成第一版正文。系统会保留原章节，新内容将保存为新的草稿版本。'
})

const statusDetails = computed(() => {
  const key = currentStepKey.value
  const detail = STEP_DETAILS[key] ?? {
    summary: '正在处理当前章节请求。',
    inputs: '系统自动组装',
    outputs: '处理中',
    next: '请稍候',
  }

  return {
    ...detail,
    stageKey: parsedStepPayload.value.raw || key,
  }
})

const runtimeDetailText = computed(() => {
  const meta = parsedStepPayload.value.meta
  const details: string[] = []
  if (meta.v) details.push(`版本进度 ${meta.v}`)
  if (meta.g) details.push(`护栏触发 ${meta.g} 条`)
  if (meta.p === 'gen') details.push('正在生成段落文本')
  return details.join('，')
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

const toggleLog = () => {
  showLog.value = !showLog.value
}

const syncLogOpen = (event: Event) => {
  showLog.value = (event.currentTarget as HTMLDetailsElement).open
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
      await globalAlert.showSuccess(`第${props.chapterNumber}章草稿已生成，可回到写作台确认版本。`, '生成完成')
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
  border-radius: var(--md-radius-lg);
  background: color-mix(in srgb, var(--md-surface) 96%, transparent);
  box-shadow: var(--md-elevation-1);
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
.chapter-console__task-card,
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

.chapter-console__task-card h4,
.chapter-console__pipeline-card h4,
.chapter-console__explain-card h4,
.chapter-console__preview-card h4 {
  margin: 0;
  color: var(--md-on-surface);
  font-size: var(--md-title-medium);
}

.chapter-console__task-title {
  margin: var(--md-spacing-2) 0 0;
  color: var(--md-on-surface);
  font-weight: 600;
}

.chapter-console__task-grid {
  margin-top: var(--md-spacing-3);
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--md-spacing-3);
}

.chapter-console__task-grid div {
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-md);
  background-color: var(--md-surface-container-low);
  padding: var(--md-spacing-3);
}

.chapter-console__task-grid span {
  display: block;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.chapter-console__task-grid strong {
  display: block;
  margin-top: 5px;
  color: var(--md-on-surface);
  font-size: var(--md-label-large);
}

.chapter-console__pipeline {
  margin: var(--md-spacing-3) 0 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-2);
}

.chapter-console__pipeline-item {
  display: flex;
  gap: var(--md-spacing-3);
  align-items: center;
  padding: var(--md-spacing-3);
  border-radius: var(--md-radius-md);
  border: 1px solid var(--md-outline-variant);
  background-color: var(--md-surface-container-low);
}

.chapter-console__pipeline-marker {
  width: 20px;
  display: flex;
  justify-content: center;
}

.chapter-console__dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background-color: var(--md-outline);
}

.chapter-console__pipeline-title,
.chapter-console__pipeline-state {
  margin: 0;
}

.chapter-console__pipeline-title {
  color: var(--md-on-surface);
  font-weight: 600;
}

.chapter-console__pipeline-state {
  margin-top: 3px;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.chapter-console__pipeline-item.is-done .chapter-console__dot {
  background-color: var(--md-success);
}

.chapter-console__pipeline-item.is-in-progress {
  border-color: color-mix(in srgb, var(--md-primary) 34%, var(--md-outline-variant));
  background-color: color-mix(in srgb, var(--md-primary-container) 58%, var(--md-surface-container-low));
}

.chapter-console__pipeline-item.is-in-progress .chapter-console__dot {
  background-color: var(--md-primary);
  animation: pulse-dot 1.3s ease-out infinite;
}

.chapter-console__pipeline-item.is-in-progress .chapter-console__pipeline-state {
  color: var(--md-on-primary-container);
}

.chapter-console__pipeline-item.is-failed {
  border-color: color-mix(in srgb, var(--md-error) 44%, var(--md-outline-variant));
  background-color: var(--md-error-container);
}

.chapter-console__pipeline-item.is-failed .chapter-console__dot {
  background-color: var(--md-error);
}

.chapter-console__explain-card p {
  margin: var(--md-spacing-2) 0 0;
  color: var(--md-on-surface-variant);
  line-height: 1.7;
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

@keyframes pulse-dot {
  0% {
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--md-primary) 35%, transparent);
  }

  100% {
    box-shadow: 0 0 0 4px color-mix(in srgb, var(--md-primary) 0%, transparent);
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

@media (prefers-reduced-motion: reduce) {
  .chapter-console__pipeline-item.is-in-progress .chapter-console__dot,
  .chapter-console__cursor {
    animation: none;
  }
}

@media (max-width: 1199px) {
  .chapter-console__task-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 833px) {
  .chapter-console__task-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .chapter-console__header {
    flex-direction: column;
    align-items: flex-start;
  }

  .chapter-console__actions {
    flex-direction: column;
  }

  .chapter-console__actions .md-btn {
    width: 100%;
  }
}
</style>
