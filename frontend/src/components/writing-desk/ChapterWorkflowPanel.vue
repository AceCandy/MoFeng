<!-- AIMETA P=章节工作流状态与命令面板|R=状态文本_候选选版_allowed命令与风险确认|NR=不请求API_不持有Chapter实体|E=component:ChapterWorkflowPanel|X=ui|A=workflow-status|D=vue|S=dom,state|RD=./README.ai -->
<template>
  <section
    class="chapter-workflow"
    :class="`chapter-workflow--${tone}`"
    :role="isAlert ? 'alert' : 'status'"
    :aria-live="isAlert ? 'assertive' : 'polite'"
    :aria-busy="pending ? 'true' : 'false'"
    aria-atomic="true"
  >
    <header class="chapter-workflow__header">
      <div class="chapter-workflow__copy">
        <p class="chapter-workflow__eyebrow">章节工作流</p>
        <h3>{{ stateCopy.title }}</h3>
        <p>{{ error || stateCopy.description }}</p>
        <p v-if="transportCopy" class="chapter-workflow__transport">
          {{ transportCopy }}
        </p>
      </div>

      <div v-if="hasActions" class="chapter-workflow__actions" aria-label="章节工作流操作">
        <button
          v-if="phase === 'idle' || phase === 'cancelled'"
          type="button"
          class="md-btn md-btn-filled md-ripple"
          data-action="start"
          :disabled="pending"
          @click="emit('start')"
        >
          {{ pending ? '正在提交...' : '开始生成' }}
        </button>
        <button
          v-if="canRetry"
          type="button"
          class="md-btn md-btn-filled md-ripple"
          data-action="retry"
          :disabled="pending"
          @click="emit('retry')"
        >
          {{ pending ? '正在提交...' : '重试工作流' }}
        </button>
        <button
          v-if="canRetryExternal"
          type="button"
          class="md-btn md-btn-filled md-ripple"
          data-action="retry-external"
          :disabled="pending"
          @click="confirmExternalRetry"
        >
          确认风险并重试
        </button>
        <button
          v-if="canRetryProjection"
          type="button"
          class="md-btn md-btn-filled md-ripple"
          data-action="retry-projection"
          :disabled="pending"
          @click="emit('retryProjection')"
        >
          {{ pending ? '正在提交...' : '重试同步' }}
        </button>
        <button
          v-if="phase === 'fatal'"
          type="button"
          class="md-btn md-btn-filled md-ripple"
          data-action="resync"
          :disabled="pending"
          @click="emit('resync')"
        >
          重新同步
        </button>
        <button
          v-if="canCancel"
          type="button"
          class="md-btn md-btn-outlined md-ripple"
          data-action="cancel"
          :disabled="pending"
          @click="emit('cancel')"
        >
          取消本轮
        </button>
      </div>
    </header>

    <div v-if="phase === 'waitingForSelection'" class="chapter-workflow__selection">
      <p v-if="candidates.length === 0" class="chapter-workflow__syncing">
        候选版本同步中
      </p>
      <template v-else>
        <div class="chapter-workflow__candidate-list" role="radiogroup" aria-label="章节候选版本">
          <button
            v-for="(candidate, index) in candidates"
            :key="candidate.id"
            type="button"
            role="radio"
            class="chapter-workflow__candidate"
            :class="{ 'is-selected': selectedCandidateId === candidate.id }"
            :aria-checked="selectedCandidateId === candidate.id"
            :aria-label="`候选版本 ${index + 1}`"
            :tabindex="selectedCandidateId === candidate.id ? 0 : -1"
            @click="selectedCandidateId = candidate.id"
            @keydown="onCandidateKeydown(index, $event)"
          >
            <span class="chapter-workflow__candidate-label">
              {{ candidate.version_label || `版本 ${index + 1}` }}
            </span>
            <span class="chapter-workflow__candidate-preview">
              {{ preview(candidate.content) }}
            </span>
          </button>
        </div>
        <button
          v-if="canSelect"
          type="button"
          class="md-btn md-btn-filled md-ripple chapter-workflow__select"
          data-action="select"
          :disabled="pending || selectedCandidateId === null"
          @click="selectCandidate"
        >
          {{ pending ? '正在提交...' : '选定并继续' }}
        </button>
      </template>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type {
  ChapterWorkflowCommand,
} from '@/api/chapterWorkflow'
import type { ChapterVersionSelection } from '@/api/novel'
import type {
  ChapterWorkflowPhase,
  ChapterWorkflowTransportPhase,
} from '@/composables/chapterWorkflowMachine'
import { globalAlert } from '@/composables/useAlert'

type WorkflowPanelPhase = ChapterWorkflowPhase | 'booting' | 'fatal'

interface Props {
  phase: WorkflowPanelPhase
  transport: ChapterWorkflowTransportPhase
  allowedCommands: readonly ChapterWorkflowCommand[]
  pending: boolean
  error: string | null
  retryActivityKey: string | null
  candidates: ChapterVersionSelection[]
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (event: 'start'): void
  (event: 'selectVersion', versionId: number): void
  (event: 'retry'): void
  (event: 'retryExternal', activityKey: string): void
  (event: 'retryProjection'): void
  (event: 'cancel'): void
  (event: 'resync'): void
}>()

const selectedCandidateId = ref<number | null>(null)

const stateCopy = computed(() => {
  switch (props.phase) {
    case 'booting':
      return { title: '正在恢复章节状态', description: '正在读取最近一次工作流事实。' }
    case 'idle':
      return { title: '尚未开始生成', description: '本章可以开始新的生成工作流。' }
    case 'submitting':
      return { title: '正在提交生成请求', description: '请求已锁定，请稍候。' }
    case 'running':
      return { title: '章节生成中', description: '生成、评审与候选整理正在后台推进。' }
    case 'waitingForSelection':
      return { title: '请选择候选版本', description: '选定后将进入正文提交与派生数据同步。' }
    case 'finalizing':
      return { title: '正在提交正文', description: '已接受选版，正在写入章节修订。' }
    case 'projectionPending':
      return { title: '正文已提交', description: '正在同步摘要、记忆与检索数据。' }
    case 'succeeded':
      return { title: '章节工作流已完成', description: '正文与必要派生数据已经就绪。' }
    case 'failed':
      return { title: '本轮需要处理', description: '请按服务端允许的动作恢复本轮工作流。' }
    case 'cancelled':
      return { title: '本轮已取消', description: '可以重新开始新的章节工作流。' }
    case 'superseded':
      return { title: '正在切换到最新运行', description: '本轮已被后续运行替代。' }
    case 'fatal':
      return { title: '章节状态暂不可信', description: '无法确认当前工作流事实，请重新同步。' }
  }
  return { title: '章节状态暂不可信', description: '无法确认当前工作流事实，请重新同步。' }
})

const tone = computed(() => {
  if (props.phase === 'fatal' || props.phase === 'failed') return 'error'
  if (props.phase === 'waitingForSelection' || props.phase === 'projectionPending') return 'pending'
  if (props.phase === 'succeeded') return 'success'
  return 'neutral'
})

const isAlert = computed(() => props.phase === 'fatal' || props.phase === 'failed')
const canSelect = computed(() => props.allowedCommands.includes('select'))
const canRetry = computed(() => props.allowedCommands.includes('retry'))
const canRetryProjection = computed(() => props.allowedCommands.includes('retry_projection'))
const canCancel = computed(() => props.allowedCommands.includes('cancel'))
const canRetryExternal = computed(() =>
  props.allowedCommands.includes('retry_external') && props.retryActivityKey !== null,
)
const hasActions = computed(() =>
  props.phase === 'idle'
  || props.phase === 'cancelled'
  || props.phase === 'fatal'
  || canRetry.value
  || canRetryProjection.value
  || canRetryExternal.value
  || canCancel.value,
)

const transportCopy = computed(() => {
  if (props.phase === 'booting' || props.phase === 'idle' || props.phase === 'fatal') return null
  if (props.transport === 'polling') return '实时连接不可用，正在轮询同步。'
  if (props.transport === 'reconnecting') return '实时连接已中断，正在重连。'
  if (props.transport === 'connecting') return '正在建立实时连接。'
  if (props.transport === 'disconnected') return '实时连接暂未建立。'
  return null
})

const preview = (content: string) => {
  const normalized = content.replace(/\s+/g, ' ').trim()
  return normalized.length > 120 ? `${normalized.slice(0, 120)}...` : normalized
}

const selectCandidate = () => {
  if (!canSelect.value || props.pending || selectedCandidateId.value === null) return
  emit('selectVersion', selectedCandidateId.value)
}

const onCandidateKeydown = (index: number, event: KeyboardEvent) => {
  const lastIndex = props.candidates.length - 1
  let nextIndex: number | null = null

  if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
    nextIndex = index === lastIndex ? 0 : index + 1
  } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
    nextIndex = index === 0 ? lastIndex : index - 1
  } else if (event.key === 'Home') {
    nextIndex = 0
  } else if (event.key === 'End') {
    nextIndex = lastIndex
  }

  if (nextIndex === null) return
  event.preventDefault()
  if (nextIndex === index) return
  selectedCandidateId.value = props.candidates[nextIndex].id
  const currentRadio = event.currentTarget
  if (!(currentRadio instanceof HTMLButtonElement)) return
  currentRadio.parentElement
    ?.querySelectorAll<HTMLButtonElement>('[role="radio"]')[nextIndex]
    ?.focus()
}

const confirmExternalRetry = async () => {
  if (!canRetryExternal.value || props.retryActivityKey === null || props.pending) return
  const confirmed = await globalAlert.showConfirm(
    '上一次外部模型调用可能已经发生。再次提交可能产生重复调用与费用，确认承担该风险后重试吗？',
    '确认外部重试风险',
  )
  if (confirmed) emit('retryExternal', props.retryActivityKey)
}

watch(
  () => props.candidates.map((candidate) => candidate.id),
  (ids) => {
    if (selectedCandidateId.value !== null && ids.includes(selectedCandidateId.value)) return
    selectedCandidateId.value = ids[0] ?? null
  },
  { immediate: true },
)
</script>

<style scoped>
.chapter-workflow {
  display: grid;
  gap: var(--md-spacing-4);
  padding: var(--md-spacing-5);
  border-bottom: 1px solid var(--md-outline-variant);
  background: var(--md-surface-container-low);
  color: var(--md-on-surface);
}

.chapter-workflow--error {
  background: var(--md-error-container);
}

.chapter-workflow--pending {
  background: var(--md-surface-container);
}

.chapter-workflow--success {
  background: var(--md-success-container);
}

.chapter-workflow__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--md-spacing-5);
}

.chapter-workflow__copy {
  min-width: 0;
  max-width: 72ch;
}

.chapter-workflow__eyebrow,
.chapter-workflow__copy h3,
.chapter-workflow__copy p {
  margin: 0;
  letter-spacing: 0;
}

.chapter-workflow__eyebrow {
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-small);
  font-weight: 600;
}

.chapter-workflow__copy h3 {
  margin-top: var(--md-spacing-1);
  font-family: var(--md-font-serif);
  font-size: var(--md-title-large);
}

.chapter-workflow__copy h3 + p {
  margin-top: var(--md-spacing-2);
  color: var(--md-on-surface-variant);
  line-height: 1.65;
}

.chapter-workflow__transport {
  margin-top: var(--md-spacing-2) !important;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.chapter-workflow__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--md-spacing-2);
}

.chapter-workflow__actions .md-btn,
.chapter-workflow__select {
  min-height: 40px;
  white-space: normal;
}

.chapter-workflow__selection {
  display: grid;
  gap: var(--md-spacing-3);
}

.chapter-workflow__syncing {
  margin: 0;
  padding: var(--md-spacing-4) 0;
  color: var(--md-on-surface-variant);
}

.chapter-workflow__candidate-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 240px), 1fr));
  gap: var(--md-spacing-3);
}

.chapter-workflow__candidate {
  min-width: 0;
  min-height: 112px;
  padding: var(--md-spacing-4);
  border: 1px solid var(--md-outline);
  border-radius: var(--md-radius-sm);
  background: var(--md-surface);
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.chapter-workflow__candidate:hover,
.chapter-workflow__candidate:focus-visible {
  border-color: var(--md-primary);
}

.chapter-workflow__candidate:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}

.chapter-workflow__candidate.is-selected {
  border-color: var(--md-primary);
  box-shadow: 2px 2px 0 var(--md-outline);
}

.chapter-workflow__candidate-label,
.chapter-workflow__candidate-preview {
  display: block;
  letter-spacing: 0;
}

.chapter-workflow__candidate-label {
  font-weight: 700;
}

.chapter-workflow__candidate-preview {
  margin-top: var(--md-spacing-2);
  overflow-wrap: anywhere;
  color: var(--md-on-surface-variant);
  line-height: 1.6;
}

.chapter-workflow__select {
  justify-self: end;
}

@media (max-width: 700px) {
  .chapter-workflow {
    padding: var(--md-spacing-4);
  }

  .chapter-workflow__header {
    flex-direction: column;
  }

  .chapter-workflow__actions,
  .chapter-workflow__select {
    width: 100%;
    justify-self: stretch;
  }

  .chapter-workflow__actions .md-btn,
  .chapter-workflow__select {
    flex: 1 1 100%;
  }
}
</style>
