<!-- AIMETA P=灵感模式_AI对话创作|R=对话创作界面|NR=不含写作台功能|E=route:/inspiration#component:InspirationMode|X=ui|A=对话界面|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="inspiration-page">
    <div class="inspiration-page__container">
      <Transition name="ink-stage" mode="out-in">
        <!-- 阶段 1：灵感模式交互界面 -->
        <div
          v-if="!showBlueprintConfirmation && !showBlueprint"
          key="chat"
          class="inspiration-chat"
        >
          <!-- 左侧聊天主体 -->
          <div class="inspiration-chat__main">
            <!-- 头部 -->
            <header class="inspiration-chat__header">
              <div class="flex justify-between items-center">
                <div class="inspiration-chat__heading">
                  <span class="inspiration-chat__status-dot" aria-hidden="true"></span>
                  <div>
                    <h1 class="md-label-large inspiration-chat__title">与“文思”对话中</h1>
                    <span v-if="currentProject" class="inspiration-chat__context">
                      《{{ currentProject.title }}》 · {{ conversationStageLabel }}
                    </span>
                  </div>
                </div>
                <div class="flex items-center gap-4">
                  <span v-if="currentTurn > 0" class="inspiration-chat__turn-badge">
                    第 {{ currentTurn }} 轮
                  </span>
                  <button
                    @click="handleRestart"
                    title="重新开始"
                    class="md-btn md-btn-text md-ripple inspiration-header-btn"
                    aria-label="重新开始对话"
                  >
                    <span class="inspiration-header-btn__label">[ 始 ]</span> 重开
                  </button>
                  <button
                    @click="exitConversation"
                    title="返回首页"
                    class="md-btn md-btn-text md-ripple inspiration-header-btn"
                    aria-label="退出灵感模式"
                  >
                    <span class="inspiration-header-btn__label">[ 归 ]</span> 退出
                  </button>
                </div>
              </div>
            </header>

            <!-- 聊天区域 -->
            <div class="inspiration-chat__messages" ref="chatArea">
              <transition name="md-fade">
                <InspirationLoading v-if="isInitialLoading" />
              </transition>
              <ChatBubble
                v-for="(message, index) in chatMessages"
                :id="`chat-bubble-${index}`"
                :key="index"
                :message="message.content"
                :type="message.type"
              />
            </div>

            <!-- 输入区域 -->
            <div class="inspiration-chat__input">
              <ConversationInput
                v-model="inspirationDraft"
                :ui-control="currentUIControl"
                :loading="
                  inspirationRequestPending ||
                  isInitialLoading ||
                  isCheckingModelConfig ||
                  !conversationStarted
                "
                @submit="handleUserInput"
                @blur="flushDraft"
              />
              <p v-if="draftSyncMessage" class="inspiration-chat__draft-status" aria-live="polite">
                {{ draftSyncMessage }}
              </p>
            </div>
          </div>

          <!-- 中间古雅挂轴式对话进度轴 -->
          <nav
            class="inspiration-chat__timeline"
            aria-label="对话进度轴"
            v-if="userSpeechNodes.length > 0"
          >
            <div class="timeline-line"></div>
            <div class="timeline-nodes">
              <button
                v-for="(node, nodeIdx) in userSpeechNodes"
                :key="nodeIdx"
                @click="scrollToUserMessage(node.chatIndex, nodeIdx)"
                class="timeline-node-btn"
                :class="{ 'is-active': activeNodeIndex === nodeIdx }"
                :title="node.previewText"
              >
                <span class="timeline-node-seal">{{ node.numLabel }}</span>
                <div class="timeline-node-tooltip">{{ node.tooltipText }}</div>
              </button>
            </div>
          </nav>

          <!-- 右侧：文思灵感要素词笺画轴 -->
          <details class="inspiration-chat__ledger" aria-label="排演脉络" open>
            <summary class="ledger-header border-b">
              <span class="ledger-eyebrow">文思灵感词笺</span>
              <span class="ledger-stamp">收放</span>
            </summary>
            
            <div class="ledger-content">
              <ul class="ledger-items">
                <!-- 要素 1：核心意象 -->
                <li class="ledger-item" :class="{ 'is-active': currentTurn >= 1 }">
                  <div class="ledger-item__seal">意</div>
                  <div class="ledger-item__body">
                    <h4 class="ledger-item__title">核心意象</h4>
                    <p class="ledger-item__desc">
                      {{
                        currentTurn >= 1
                          ? extractedCoreIdea || '落笔有声，灵感之火正在凝聚成形...'
                          : '阁主未曾落笔，灵感初蒙...'
                      }}
                    </p>
                  </div>
                </li>

                <!-- 要素 2：时空背景 -->
                <li class="ledger-item" :class="{ 'is-active': currentTurn >= 2 }">
                  <div class="ledger-item__seal">境</div>
                  <div class="ledger-item__body">
                    <h4 class="ledger-item__title">时空背景</h4>
                    <p class="ledger-item__desc">
                      {{
                        currentTurn >= 2
                          ? '时空骨架初现，文思正勾勒江山画卷...'
                          : '待阁主勾勒故事舞台...'
                      }}
                    </p>
                  </div>
                </li>

                <!-- 要素 3：核心冲突 -->
                <li class="ledger-item" :class="{ 'is-active': currentTurn >= 3 }">
                  <div class="ledger-item__seal">鋒</div>
                  <div class="ledger-item__body">
                    <h4 class="ledger-item__title">主要冲突</h4>
                    <p class="ledger-item__desc">
                      {{
                        currentTurn >= 3
                          ? '矛盾暗影交锋，大纲隐显刀刻之锋芒...'
                          : '待戏剧冲突破土萌发...'
                      }}
                    </p>
                  </div>
                </li>

                <!-- 要素 4：章节蓝图 -->
                <li class="ledger-item" :class="{ 'is-active': currentTurn >= 4 }">
                  <div class="ledger-item__seal">章</div>
                  <div class="ledger-item__body">
                    <h4 class="ledger-item__title">章节大纲</h4>
                    <p class="ledger-item__desc">
                      {{
                        currentTurn >= 4
                          ? '万川归海，大纲即将落款成卷，请落座...'
                          : '待文思集腋成裘，凝成章节蓝图...'
                      }}
                    </p>
                  </div>
                </li>
              </ul>
              
              <!-- 底部国风点晴说明 -->
              <div class="ledger-footer mt-auto">
                <p>「笔底生墨，大纲渐润」</p>
              </div>
            </div>
          </details>
        </div>

        <!-- 阶段 2：蓝图确认界面 -->
        <BlueprintConfirmation
          v-else-if="showBlueprintConfirmation"
          key="confirm"
          :ai-message="confirmationMessage"
          :project-id="currentProject?.id || null"
          @blueprint-generated="handleBlueprintGenerated"
          @back="backToConversation"
        />

        <!-- 阶段 3：大纲展示界面 -->
        <BlueprintDisplay
          v-else-if="showBlueprint"
          key="display"
          :blueprint="completedBlueprint"
          :ai-message="blueprintMessage"
          @confirm="handleConfirmBlueprint"
          @regenerate="handleRegenerateBlueprint"
        />
      </Transition>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import type { UIControl, Blueprint, NovelProject } from '@/api/novel'
import type { CreationContext } from '@/api/creationContexts'
import { HttpRequestError } from '@/utils/errors'
import {
  useConverseConceptStreamMutation,
  useCreateNovelMutation,
  useDeleteNovelsMutation,
  useGenerateBlueprintMutation,
  useNovelProjectQuery,
  useSaveBlueprintMutation,
} from '@/queries/novel'
import {
  useCreationContextsQuery,
  usePatchCreationContextMutation,
} from '@/queries/creationContexts'
import { useLLMConfigBundleQuery } from '@/queries/llm'
import { useAuthStore } from '@/stores/auth'
import ChatBubble from '@/components/ChatBubble.vue'
import ConversationInput from '@/components/ConversationInput.vue'
import BlueprintConfirmation from '@/components/BlueprintConfirmation.vue'
import BlueprintDisplay from '@/components/BlueprintDisplay.vue'
import InspirationLoading from '@/components/InspirationLoading.vue'
import { globalAlert } from '@/composables/useAlert'
import { decodeConversationHistory } from '@/utils/novelContract'
import {
  loadInspirationDraftBackup,
  removeInspirationDraftBackup,
  saveInspirationDraftBackup,
} from '@/utils/creationDraft'

interface ChatMessage {
  content: string
  type: 'user' | 'ai'
}

const INSPIRATION_OPENING_MESSAGE = `灵感已经落座。

告诉我，它最初是什么？一个画面、一句对白、一个人物，或者一种挥之不去的感觉都可以。`

const INSPIRATION_INITIAL_UI_CONTROL: UIControl = {
  type: 'text_input',
  placeholder: '起笔于此，写下您最初的灵感火花...',
}

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const conversationStarted = ref(false)
const isInitialLoading = ref(true)
const showBlueprintConfirmation = ref(false)
const showBlueprint = ref(false)
const chatMessages = ref<ChatMessage[]>([])
const currentUIControl = ref<UIControl | null>(null)
const currentTurn = ref(0)
const inspirationDraft = ref('')
const completedBlueprint = ref<Blueprint | null>(null)
const confirmationMessage = ref('')
const blueprintMessage = ref('')

// 动态提取阁主的第一个灵感火花作为核心意象展示
const extractedCoreIdea = computed(() => {
  const userMsg = chatMessages.value.find((m) => m.type === 'user')
  if (!userMsg) return ''
  const val = userMsg.content.trim()
  return val.length > 28 ? val.slice(0, 26) + '...' : val
})
const chatArea = ref<HTMLElement>()
const activeNodeIndex = ref<number | null>(null)

interface UserSpeechNode {
  chatIndex: number
  numLabel: string
  previewText: string
  tooltipText: string
}

// 动态计算以阁主发言为骨架的进度轴节点
const userSpeechNodes = computed<UserSpeechNode[]>(() => {
  const chineseNumbers = [
    '壹',
    '贰',
    '叁',
    '肆',
    '伍',
    '陆',
    '柒',
    '捌',
    '玖',
    '拾',
    '拾壹',
    '拾贰',
    '拾叁',
    '拾肆',
    '拾伍',
  ]
  return chatMessages.value
    .map((msg, index) => ({ msg, index }))
    .filter(({ msg }) => msg.type === 'user')
    .map(({ msg, index }, idx) => {
      const numLabel = chineseNumbers[idx] || String(idx + 1)
      const plainText = msg.content.trim()
      const preview = plainText.length > 18 ? plainText.slice(0, 16) + '...' : plainText
      return {
        chatIndex: index,
        numLabel,
        previewText: preview,
        tooltipText: `【第${numLabel}步】 ${preview}`,
      }
    })
})

// 平滑滚动定位到阁主某次具体的发言位置
const scrollToUserMessage = (chatIndex: number, nodeIdx: number) => {
  activeNodeIndex.value = nodeIdx
  const el = document.getElementById(`chat-bubble-${chatIndex}`)
  if (el) {
    el.scrollIntoView({
      behavior: 'smooth',
      block: 'center',
    })
  }
}
const isCheckingModelConfig = ref(false)
const isAssistantResponding = ref(false)
const activeProjectId = ref<string | null>(null)
const currentProject = ref<NovelProject | null>(null)
const conversationStageLabel = computed(() => {
  if (currentTurn.value === 0) return '落笔起意'
  if (currentTurn.value < 2) return '凝聚核心意象'
  if (currentTurn.value < 4) return '搭建故事骨架'
  return '确认章节蓝图'
})
// 【强类型守卫】：将 any 替换为未定义属性的防御性安全字典或专属类型，杜绝类型逃逸
const currentConversationState = ref<Record<string, unknown>>({})

const projectQuery = useNovelProjectQuery(activeProjectId)
const contextsQuery = useCreationContextsQuery()
const patchContextMutation = usePatchCreationContextMutation()
const createNovelMutation = useCreateNovelMutation()
const deleteNovelsMutation = useDeleteNovelsMutation()
const converseConceptStreamMutation = useConverseConceptStreamMutation(
  () => currentProject.value?.id,
)
const generateBlueprintMutation = useGenerateBlueprintMutation(() => currentProject.value?.id)
const saveBlueprintMutation = useSaveBlueprintMutation(() => currentProject.value?.id)
const llmConfigBundleQuery = useLLMConfigBundleQuery()
const activeCreationContext = computed(() => {
  const projectId = currentProject.value?.id ?? activeProjectId.value
  return contextsQuery.data.value?.find((context) => context.project_id === projectId) ?? null
})

const inspirationRequestPending = computed(
  () =>
    createNovelMutation.isPending.value ||
    deleteNovelsMutation.isPending.value ||
    projectQuery.isFetching.value ||
    converseConceptStreamMutation.isPending.value ||
    generateBlueprintMutation.isPending.value ||
    saveBlueprintMutation.isPending.value,
)

const DRAFT_SYNC_DELAY_MS = 500
type DraftSyncState = 'idle' | 'pending' | 'syncing' | 'local'

interface DraftSyncRequest {
  userId: number
  projectId: string
  turn: number
  value: string
  revision: number
}

const draftSyncState = ref<DraftSyncState>('idle')
const draftSyncMessage = computed(() => {
  if (draftSyncState.value === 'local') return '已保存在本机，联网后同步'
  if (draftSyncState.value === 'pending' || draftSyncState.value === 'syncing') {
    return '正在同步草稿…'
  }
  return ''
})

let draftSyncTimer: ReturnType<typeof setTimeout> | null = null
let draftSyncPromise: Promise<void> | null = null
let queuedDraftSync: DraftSyncRequest | null = null
let draftRevision = 0
let localDraftDirty = false
let applyingDraft = false

const clearDraftSyncTimer = () => {
  if (draftSyncTimer !== null) {
    clearTimeout(draftSyncTimer)
    draftSyncTimer = null
  }
}

const setDraftWithoutSync = (value: string) => {
  applyingDraft = true
  inspirationDraft.value = value
  applyingDraft = false
}

const getDraftScope = () => {
  const userId = authStore.user?.id
  const projectId = currentProject.value?.id ?? activeProjectId.value
  if (userId == null || !projectId) return null
  return { userId, projectId, turn: currentTurn.value }
}

const isCurrentDraftRequest = (request: DraftSyncRequest) => {
  const scope = getDraftScope()
  return (
    scope?.userId === request.userId &&
    scope.projectId === request.projectId &&
    scope.turn === request.turn
  )
}

const removeDraftBackupBeforeTurn = (
  userId: number,
  projectId: string,
  authoritativeTurn: number,
) => {
  const backup = loadInspirationDraftBackup(userId, projectId)
  if (backup && backup.inspirationTurn < authoritativeTurn) {
    removeInspirationDraftBackup(userId, projectId)
  }
}

const stageDraftSync = (value: string): DraftSyncRequest | null => {
  const scope = getDraftScope()
  if (!scope) return null
  draftRevision += 1
  const request = { ...scope, value, revision: draftRevision }
  queuedDraftSync = request
  localDraftDirty = true
  saveInspirationDraftBackup({
    userId: request.userId,
    projectId: request.projectId,
    inspirationTurn: request.turn,
    value: request.value,
    savedAt: Date.now(),
  })
  return request
}

const isOnline = () => typeof navigator === 'undefined' || navigator.onLine

const runDraftSync = (): Promise<void> => {
  if (draftSyncPromise) return draftSyncPromise
  draftSyncPromise = (async () => {
    while (queuedDraftSync) {
      const request = queuedDraftSync
      queuedDraftSync = null
      if (isCurrentDraftRequest(request)) draftSyncState.value = 'syncing'
      try {
        const context = await patchContextMutation.mutateAsync({
          projectId: request.projectId,
          patch: {
            surface: 'inspiration',
            inspiration_draft: request.value || null,
            inspiration_turn: request.turn,
          },
        })
        const authoritativeTurn = context.inspiration_turn
        if (authoritativeTurn != null && authoritativeTurn > request.turn) {
          removeDraftBackupBeforeTurn(request.userId, request.projectId, authoritativeTurn)
          const nextRequest = queuedDraftSync as DraftSyncRequest | null
          if (
            nextRequest?.projectId === request.projectId &&
            nextRequest.turn < authoritativeTurn
          ) {
            queuedDraftSync = null
          }
          if (isCurrentDraftRequest(request)) {
            localDraftDirty = false
            setDraftWithoutSync('')
            draftSyncState.value = 'idle'
          }
          continue
        }
        if (
          !queuedDraftSync &&
          isCurrentDraftRequest(request) &&
          draftRevision === request.revision
        ) {
          removeInspirationDraftBackup(request.userId, request.projectId)
          localDraftDirty = false
          draftSyncState.value = 'idle'
        }
      } catch {
        if (isCurrentDraftRequest(request)) draftSyncState.value = 'local'
        const nextRequest = queuedDraftSync as DraftSyncRequest | null
        if (
          nextRequest &&
          (nextRequest.projectId !== request.projectId || nextRequest.turn !== request.turn)
        ) {
          continue
        }
        break
      }
    }
  })().finally(() => {
    draftSyncPromise = null
  })
  return draftSyncPromise
}

const queueDraftSync = (value: string, immediate = false) => {
  if (!stageDraftSync(value)) return
  clearDraftSyncTimer()
  if (!isOnline()) {
    draftSyncState.value = 'local'
    return
  }
  draftSyncState.value = 'pending'
  if (immediate) {
    void runDraftSync()
    return
  }
  draftSyncTimer = setTimeout(() => {
    draftSyncTimer = null
    void runDraftSync()
  }, DRAFT_SYNC_DELAY_MS)
}

const flushDraft = async () => {
  clearDraftSyncTimer()
  if (!queuedDraftSync && !draftSyncPromise && localDraftDirty) {
    stageDraftSync(inspirationDraft.value)
  }
  if (!isOnline()) {
    if (localDraftDirty) draftSyncState.value = 'local'
    return
  }
  await runDraftSync()
}

const resetDraftSyncState = () => {
  clearDraftSyncTimer()
  queuedDraftSync = null
  draftRevision += 1
  localDraftDirty = false
  draftSyncState.value = 'idle'
  setDraftWithoutSync('')
}

const markInspirationSurface = async (projectId: string) => {
  try {
    return await patchContextMutation.mutateAsync({
      projectId,
      patch: { surface: 'inspiration' },
    })
  } catch {
    return null
  }
}

const restoreDraft = (projectId: string, context: CreationContext | null) => {
  const userId = authStore.user?.id
  if (userId == null) return
  const backup = loadInspirationDraftBackup(userId, projectId)
  if (backup && backup.inspirationTurn !== currentTurn.value) {
    removeInspirationDraftBackup(userId, projectId)
  }
  const validBackup = backup?.inspirationTurn === currentTurn.value ? backup : null
  const remoteDraft =
    context?.inspiration_turn === currentTurn.value ? (context.inspiration_draft ?? '') : ''
  setDraftWithoutSync(validBackup?.value ?? remoteDraft)
  localDraftDirty = Boolean(validBackup)
  draftSyncState.value = validBackup ? 'local' : 'idle'
  if (validBackup) queueDraftSync(validBackup.value, true)
}

watch(
  inspirationDraft,
  (value) => {
    if (!applyingDraft) queueDraftSync(value)
  },
  { flush: 'sync' },
)

const hasRequiredModelConfig = async () => {
  const result = await llmConfigBundleQuery.refetch()
  if (result.error) {
    throw result.error
  }
  const bundle = result.data
  if (!bundle) {
    return false
  }
  const hasLLMModel =
    bundle.models.some((model) => model.is_enabled && Boolean(model.capabilities.chat)) ||
    Boolean(bundle.legacy?.llm_provider_model?.trim())
  const hasEmbeddingModel =
    bundle.models.some((model) => model.is_enabled && Boolean(model.capabilities.embedding)) ||
    Boolean(bundle.legacy?.embedding_provider_model?.trim())
  return hasLLMModel && hasEmbeddingModel
}

const redirectToSettingsForModelConfig = async () => {
  globalAlert.showAlert(
    '请先在设置中配置并保存 LLM Model 与向量 Model，然后再开启灵感模式。',
    'info',
    '需要先完成模型配置',
  )
  await router.push({
    name: 'settings',
    query: {
      source: 'inspiration',
      reason: 'missing_models',
    },
  })
}

const ensureModelConfigOrRedirect = async () => {
  if (isCheckingModelConfig.value) {
    return false
  }

  isCheckingModelConfig.value = true
  try {
    const configReady = await hasRequiredModelConfig()
    if (configReady) {
      return true
    }
    await redirectToSettingsForModelConfig()
    return false
  } catch (error) {
    console.error('检查模型配置失败:', error)
    globalAlert.showError(
      `检查模型配置失败: ${error instanceof Error ? error.message : '未知错误'}`,
      '配置检查失败',
    )
    return false
  } finally {
    isCheckingModelConfig.value = false
  }
}

const readUnfinishedInspirationProjectId = (error: unknown): string | null => {
  if (!(error instanceof HttpRequestError) || error.status !== 409) {
    return null
  }

  const payload = error.payload
  if (!payload || typeof payload !== 'object') {
    return null
  }

  const detail = (payload as Record<string, unknown>).detail
  if (!detail || typeof detail !== 'object') {
    return null
  }

  const record = detail as Record<string, unknown>
  if (record.code !== 'unfinished_inspiration') {
    return null
  }

  return typeof record.project_id === 'string' && record.project_id ? record.project_id : null
}

// 清空所有状态，开始新的灵感对话
const resetInspirationMode = () => {
  resetDraftSyncState()
  conversationStarted.value = false
  isInitialLoading.value = false
  showBlueprintConfirmation.value = false
  showBlueprint.value = false
  chatMessages.value = []
  currentUIControl.value = null
  currentTurn.value = 0
  isAssistantResponding.value = false
  completedBlueprint.value = null
  confirmationMessage.value = ''
  blueprintMessage.value = ''

  activeProjectId.value = null
  currentProject.value = null
  currentConversationState.value = {}
}

const exitConversation = async () => {
  const confirmed = await globalAlert.showConfirm(
    '已发送的对话会保留；未发送草稿会优先同步，网络不可用时在本机保护 24 小时。确定退出吗？',
    '退出确认',
  )
  if (confirmed) {
    await flushDraft()
    resetInspirationMode()
    await router.push('/workspace')
  }
}

const handleRestart = async () => {
  const confirmed = await globalAlert.showConfirm(
    '确定要重新开始吗？当前对话内容将会丢失。',
    '重新开始确认',
  )
  if (confirmed) {
    const projectId = currentProject.value?.id ?? activeProjectId.value
    if (projectId) {
      try {
        await deleteNovelsMutation.mutateAsync([projectId])
        const userId = authStore.user?.id
        if (userId != null) removeInspirationDraftBackup(userId, projectId)
      } catch (error) {
        globalAlert.showError(
          `无法重新开始: ${error instanceof Error ? error.message : '删除旧灵感失败'}`,
          '重开失败',
        )
        return
      }
    }
    await startConversation()
  }
}

const backToConversation = () => {
  showBlueprintConfirmation.value = false
}

const showLocalOpeningMessage = async () => {
  isInitialLoading.value = false
  if (chatMessages.value.length === 0) {
    chatMessages.value.push({
      content: INSPIRATION_OPENING_MESSAGE,
      type: 'ai',
    })
  }
  currentUIControl.value = INSPIRATION_INITIAL_UI_CONTROL
  await scrollToBottom()
}

const startConversation = async () => {
  isInitialLoading.value = true
  const canStartConversation = await ensureModelConfigOrRedirect()
  if (!canStartConversation) {
    isInitialLoading.value = false
    return
  }

  // 重置所有状态，开始全新的对话
  resetInspirationMode()
  conversationStarted.value = true
  isInitialLoading.value = true

  try {
    const project = await createNovelMutation.mutateAsync({
      title: '未命名灵感',
      initialPrompt: '开始灵感模式',
    })
    currentProject.value = project
    activeProjectId.value = project.id
    currentConversationState.value = {}
    await router.replace({
      name: 'inspiration-mode',
      query: { ...route.query, project_id: project.id },
    })
    await markInspirationSurface(project.id)

    // 首句是固定引导语，项目创建完成后立即展示；真正的 AI 生成从用户首答开始。
    await showLocalOpeningMessage()
  } catch (error) {
    console.error('启动灵感模式失败:', error)
    const existingProjectId = readUnfinishedInspirationProjectId(error)
    if (existingProjectId) {
      resetInspirationMode()
      globalAlert.showAlert(
        '你已有未完成的灵感对话，已为你恢复上次进度。',
        'info',
        '继续未完成灵感',
      )
      await router.replace({
        name: 'inspiration-mode',
        query: { project_id: existingProjectId },
      })
      await restoreConversation(existingProjectId)
      return
    }

    globalAlert.showError(
      `无法开始灵感模式: ${error instanceof Error ? error.message : '未知错误'}`,
      '启动失败',
    )
    resetInspirationMode()
    router.push('/workspace')
  }
}

const restoreConversation = async (projectId: string) => {
  isInitialLoading.value = true
  try {
    activeProjectId.value = projectId
    await nextTick()
    const [result, contextsResult] = await Promise.all([
      projectQuery.refetch(),
      contextsQuery.refetch(),
    ])
    const project = result.data ?? projectQuery.data.value ?? null
    currentProject.value = project
    currentConversationState.value = {}
    if (project) {
      const conversationHistory = decodeConversationHistory(project.conversation_history)
      conversationStarted.value = true
      currentTurn.value = conversationHistory.filter((m) => m.role === 'assistant').length
      chatMessages.value = conversationHistory
        .map((item): ChatMessage | null => {
          if (item.role === 'user') {
            try {
              const userInput = JSON.parse(item.content)
              return { content: userInput.value, type: 'user' }
            } catch {
              return { content: item.content, type: 'user' }
            }
          } else {
            // assistant
            try {
              const assistantOutput = JSON.parse(item.content)
              return { content: assistantOutput.ai_message, type: 'ai' }
            } catch {
              return { content: item.content, type: 'ai' }
            }
          }
        })
        .filter((msg): msg is ChatMessage => msg !== null && msg.content !== null) // 过滤掉空的 user message

      const lastAssistantMsgStr = conversationHistory
        .filter((m) => m.role === 'assistant')
        .pop()?.content
      if (lastAssistantMsgStr) {
        const lastAssistantMsg = JSON.parse(lastAssistantMsgStr)

        if (lastAssistantMsg.is_complete) {
          // 如果对话已完成，直接显示蓝图确认界面
          confirmationMessage.value = lastAssistantMsg.ai_message
          showBlueprintConfirmation.value = true
        } else {
          // 否则，恢复对话
          currentUIControl.value = lastAssistantMsg.ui_control
        }
      }
      if (currentTurn.value === 0 && chatMessages.value.length === 0) {
        await showLocalOpeningMessage()
      }
      const listedContext =
        contextsResult.data?.find((context) => context.project_id === projectId) ??
        activeCreationContext.value
      const markedContext = await markInspirationSurface(projectId)
      restoreDraft(projectId, markedContext ?? listedContext ?? null)
      await scrollToBottom()
    }
  } catch (error) {
    console.error('恢复对话失败:', error)
    globalAlert.showError(
      `无法恢复对话: ${error instanceof Error ? error.message : '未知错误'}`,
      '加载失败',
    )
    resetInspirationMode()
  } finally {
    isInitialLoading.value = false
  }
}

let restoringRemoteProjectId: string | null = null
watch(
  () => [activeCreationContext.value, converseConceptStreamMutation.isPending.value] as const,
  ([context, conversationPending]) => {
    const projectId = currentProject.value?.id ?? activeProjectId.value
    if (!context || !projectId || !conversationStarted.value || conversationPending) return
    const remoteTurn = context.inspiration_turn
    if (remoteTurn == null) return
    if (remoteTurn > currentTurn.value) {
      const userId = authStore.user?.id
      if (userId != null) removeDraftBackupBeforeTurn(userId, projectId, remoteTurn)
      if (queuedDraftSync?.projectId === projectId && queuedDraftSync.turn < remoteTurn) {
        queuedDraftSync = null
      }
      localDraftDirty = false
      draftSyncState.value = 'idle'
      setDraftWithoutSync('')
      if (restoringRemoteProjectId !== projectId) {
        restoringRemoteProjectId = projectId
        void restoreConversation(projectId).finally(() => {
          if (restoringRemoteProjectId === projectId) restoringRemoteProjectId = null
        })
      }
      return
    }
    if (remoteTurn === currentTurn.value && !localDraftDirty) {
      setDraftWithoutSync(context.inspiration_draft ?? '')
    }
  },
  { flush: 'post' },
)

// 【强类型守卫】：定义明确的输入交互契约类型，支持空值安全以契合子组件声明，取代 any
const handleUserInput = async (
  userInput: { id?: string; value: string; [key: string]: unknown } | null,
) => {
  const messageCountBeforeRequest = chatMessages.value.length
  let conversationSaved = false
  try {
    // 如果有用户输入，添加到聊天记录
    if (userInput && userInput.value) {
      chatMessages.value.push({
        content: userInput.value,
        type: 'user',
      })
      await scrollToBottom()
    }

    isAssistantResponding.value = true
    await scrollToBottom()

    let assistantMessageIndex: number | null = null
    const appendAssistantDelta = async (delta: string) => {
      if (!delta) {
        return
      }
      if (assistantMessageIndex === null) {
        isAssistantResponding.value = false
        chatMessages.value.push({
          content: '',
          type: 'ai',
        })
        assistantMessageIndex = chatMessages.value.length - 1
      }
      chatMessages.value[assistantMessageIndex].content += delta
      await scrollToBottom()
    }

    if (!currentProject.value) {
      throw new Error('没有当前项目')
    }

    const response = await converseConceptStreamMutation.mutateAsync({
      userInput,
      conversationState: currentConversationState.value,
      onDelta: (delta) => {
        void appendAssistantDelta(delta)
      },
    })
    conversationSaved = true
    currentConversationState.value = response.conversation_state

    // 首次加载完成后，关闭加载动画
    if (isInitialLoading.value) {
      isInitialLoading.value = false
    }

    // 如果模型没有提前吐出 ai_message 字段，最终结果仍然兜底展示。
    if (assistantMessageIndex === null) {
      chatMessages.value.push({
        content: response.ai_message,
        type: 'ai',
      })
    } else {
      chatMessages.value[assistantMessageIndex].content = response.ai_message
    }
    currentTurn.value++
    setDraftWithoutSync('')
    queueDraftSync('', true)

    await scrollToBottom()

    if (response.is_complete && response.ready_for_blueprint) {
      // 对话完成，显示蓝图确认界面
      confirmationMessage.value = response.ai_message
      showBlueprintConfirmation.value = true
    } else if (response.is_complete) {
      // 向后兼容：直接生成蓝图（如果后端还没更新）
      await handleGenerateBlueprint()
    } else {
      // 继续对话
      currentUIControl.value = response.ui_control
    }
  } catch (error) {
    console.error('对话失败:', error)
    if (!conversationSaved) chatMessages.value.splice(messageCountBeforeRequest)
    // 确保在出错时也停止初始加载状态
    if (isInitialLoading.value) {
      isInitialLoading.value = false
    }
    globalAlert.showError(
      `抱歉，与AI连接时遇到问题: ${error instanceof Error ? error.message : '未知错误'}`,
      '通信失败',
    )
  } finally {
    isAssistantResponding.value = false
  }
}

const handleGenerateBlueprint = async () => {
  try {
    const response = await generateBlueprintMutation.mutateAsync()
    handleBlueprintGenerated(response)
  } catch (error) {
    console.error('生成蓝图失败:', error)
    globalAlert.showError(
      `生成蓝图失败: ${error instanceof Error ? error.message : '未知错误'}`,
      '生成失败',
    )
  }
}

// 【强类型守卫】：通过传入精准的类型，剔除 any
const handleBlueprintGenerated = (response: { blueprint: Blueprint; ai_message: string }) => {
  completedBlueprint.value = response.blueprint
  blueprintMessage.value = response.ai_message
  showBlueprintConfirmation.value = false
  showBlueprint.value = true
}

const handleRegenerateBlueprint = () => {
  showBlueprint.value = false
  showBlueprintConfirmation.value = true
}

const handleConfirmBlueprint = async () => {
  if (!completedBlueprint.value) {
    globalAlert.showError('蓝图数据缺失，请重新生成或稍后重试。', '保存失败')
    return
  }
  try {
    const project = await saveBlueprintMutation.mutateAsync(completedBlueprint.value)
    currentProject.value = project
    activeProjectId.value = project.id
    router.push(`/projects/${project.id}/write`)
  } catch (error) {
    console.error('保存蓝图失败:', error)
    globalAlert.showError(
      `保存蓝图失败: ${error instanceof Error ? error.message : '未知错误'}`,
      '保存失败',
    )
  }
}

let scrollFrameId: number | null = null
// 【高阶性能解耦】：采用 requestAnimationFrame 合并流式高载 DOM 滚动重绘，确保一帧内仅触发一次重排并带有平滑过渡
const scrollToBottom = async () => {
  await nextTick()
  if (!chatArea.value) return
  
  if (scrollFrameId !== null) {
    cancelAnimationFrame(scrollFrameId)
  }
  scrollFrameId = requestAnimationFrame(() => {
    if (chatArea.value) {
      chatArea.value.scrollTo({
        top: chatArea.value.scrollHeight,
        behavior: 'smooth',
      })
    }
    scrollFrameId = null
  })
}

const handleOnline = () => {
  void flushDraft()
}

onMounted(async () => {
  // 注入专属标识，极致限制外层 app-shell 溢出以击杀大滚动条，并去掉 app-shell__content 的 padding 实现无缝贴合
  document.body.classList.add('is-in-inspiration')
  window.addEventListener('online', handleOnline)
  
  const projectId = route.query.project_id as string
  if (projectId) {
    const hasRequiredConfig = await ensureModelConfigOrRedirect()
    if (!hasRequiredConfig) {
      isInitialLoading.value = false
      return
    }
    await restoreConversation(projectId)
  } else {
    await startConversation()
  }
})

onUnmounted(() => {
  window.removeEventListener('online', handleOnline)
  void flushDraft()
  // 组件卸载时，毫秒级无害恢复全局布局样式
  document.body.classList.remove('is-in-inspiration')
})
</script>

<style scoped>
/* 灵感模式激活时，将 body 及其 app-shell__content 容器的滚动与 padding 进行极致覆写，防止由于 1px 的计算误差引发的最右侧大滚动条 */
:global(body.is-in-inspiration) {
  overflow: hidden !important;
}

:global(body.is-in-inspiration .app-shell__content) {
  padding: 0 !important;
  overflow: hidden !important;
}

.inspiration-page {
  display: flex;
  align-items: flex-start !important; /* 向上靠，贴合顶栏导航 */
  justify-content: center;
  /* 精准扣除系统顶栏真实占位，使内容与浏览器视口完美等高 */
  height: calc(var(--app-viewport-unit) - var(--app-topbar-height)) !important;
  padding: var(--md-spacing-3) var(--md-spacing-5) var(--md-spacing-4) !important; /* 顶部收缩，紧贴导航 */
  /* 整页点阵底纹已焚稿退场（行线不出稿纸法则）：灵感面回归平净熟宣地 */
  background-color: var(--md-background) !important;
  overflow: hidden !important;
}

.inspiration-page__container {
  width: 100%;
  max-width: var(--app-content-max) !important; /* 全站统一内容最大宽度（宽屏自适应拓宽） */
  height: 100%; /* 高度占满视口 */
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
}

.inspiration-chat {
  height: 100%; /* 精准占满容器，不再叠加 max-height 上限避免自相矛盾 */
  display: flex;
  flex-direction: row !important; /* 核心：改为横向双栏结构 */
  background-color: var(--md-surface);
  /* 结构面：界格发线 + 微直角 + 熟宣柔影（双线框只留稿纸容器） */
  border-radius: var(--md-radius-xs) !important;
  border: 1px solid var(--md-jiege) !important;
  box-shadow: var(--md-elevation-paper-1) !important;
  overflow: hidden;
}

/* 左侧：聊天主体 */
.inspiration-chat__main {
  flex: 1 !important; /* 撑满全部剩余宽度，使对话框自适应拉大 */
  display: flex;
  flex-direction: column;
  height: 100%;
  border-right: 1px solid var(--md-outline-variant); /* 竹青界线 */
  background-color: var(--md-surface);
  min-width: 0;
}

.inspiration-chat__header {
  padding: var(--md-spacing-4);
  border-bottom: 1px solid var(--md-outline-variant);
  flex-shrink: 0;
}

.inspiration-chat__status-dot {
  width: 10px;
  height: 10px;
  border-radius: var(--md-radius-xs); /* 方点起笔印，微直角统一 */
  background-color: var(--md-primary);
}

.inspiration-chat__heading {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: var(--md-spacing-2);
}

.inspiration-chat__heading > div {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.inspiration-chat__context {
  overflow: hidden;
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-small);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.inspiration-chat__turn-badge {
  font-size: var(--md-label-medium);
  font-weight: 500;
  color: var(--md-on-surface-variant);
  background-color: var(--md-surface-container);
  padding: 4px 8px;
  border-radius: var(--md-radius-xs);
}

.inspiration-chat__messages {
  flex: 1;
  padding: var(--md-spacing-6);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-6);
  position: relative;
  min-height: 0; /* 确保弹性子项在有 overflow 时高度收敛 */
  
  /* 剔除右侧进度条/滚动条，并保留滚动功能，呈完美一案宣纸 */
  -ms-overflow-style: none !important;  /* IE and Edge */
  scrollbar-width: none !important;  /* Firefox */
}

.inspiration-chat__messages::-webkit-scrollbar {
  display: none !important; /* Chrome, Safari and Opera */
}

.inspiration-chat__input {
  padding: var(--md-spacing-4);
  border-top: 1px solid var(--md-outline-variant);
  background-color: var(--md-surface-container-low);
  flex-shrink: 0;
}

.inspiration-chat__draft-status {
  margin: var(--md-spacing-2) 0 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-small);
  overflow-wrap: anywhere;
}

/* 右侧：文思灵感词笺画轴 */
.inspiration-chat__ledger {
  flex: 0 0 320px !important; /* 固定宽 320px 挂载，其余给左侧主聊天区自适应 */
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: var(--md-surface-dim) !important; /* 用老宣纸底色形成极佳的视觉景深 */
  min-width: 300px;
  position: relative;
}

.inspiration-chat__ledger:not([open]) {
  flex-basis: 44px !important;
  max-height: 44px !important;
}

.inspiration-chat__ledger:not([open]) > .ledger-content {
  display: none !important;
}

.ledger-header {
  padding: var(--md-spacing-4) var(--md-spacing-5);
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--md-jiege) !important; /* 界格发线分隔 */
  flex-shrink: 0;
}

.ledger-eyebrow {
  font-family: var(--md-font-display) !important; /* 宋体标题 */
  font-size: var(--md-title-small);
  font-weight: 600;
  color: var(--md-primary);
  letter-spacing: 0.05em;
}

.ledger-stamp {
  font-family: var(--md-font-display) !important;
  font-size: var(--md-label-large);
  font-weight: 700;
  color: var(--md-secondary) !important; /* 朱砂印章标志 */
}

.ledger-content {
  flex: 1;
  padding: var(--md-spacing-5) var(--md-spacing-4);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  min-height: 0;
  
  /* 剔除挂轴右侧进度条/滚动条，保留滚动功能 */
  -ms-overflow-style: none !important;
  scrollbar-width: none !important;
}

.ledger-content::-webkit-scrollbar {
  display: none !important;
}

.ledger-items {
  padding: 0;
  margin: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-5);
}

/* 灵感卡片条目 */
.ledger-item {
  display: flex;
  gap: var(--md-spacing-3);
  padding: var(--md-spacing-3) var(--md-spacing-4);
  border-radius: var(--md-radius-xs) !important; /* 微直角 2px */
  border: 1px solid transparent;
  background-color: transparent;
  transition:
    background-color var(--md-duration-medium) var(--md-easing-standard),
    border-color var(--md-duration-medium) var(--md-easing-standard),
    box-shadow var(--md-duration-medium) var(--md-easing-standard),
    transform var(--md-duration-medium) var(--md-easing-standard);
  transform: scale(0.97);
}

/* 激活态：红泥落地，字迹化实 */
.ledger-item.is-active {
  background-color: var(--md-surface) !important; /* 变熟宣白 */
  border: 1px solid var(--md-jiege) !important; /* 界格发线 */
  box-shadow: var(--md-elevation-paper-1) !important; /* 熟宣柔影 */
  transform: scale(1);
}

/* 金石单字阳刻小方印 */
.ledger-item__seal {
  width: 26px;
  height: 26px;
  display: grid;
  place-items: center;
  font-family: var(--md-font-display) !important; /* 宋体 */
  font-weight: 900;
  font-size: 13px;
  border-radius: var(--md-radius-xs) !important; /* 2px */
  background-color: var(--md-surface-container-high);
  color: var(--md-on-surface-variant);
  border: 1px solid var(--md-outline-variant);
  flex-shrink: 0;
  transition:
    background-color 0.35s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.35s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.35s cubic-bezier(0.22, 1, 0.36, 1),
    color 0.35s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.35s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.35s cubic-bezier(0.22, 1, 0.36, 1);
}

.ledger-item.is-active .ledger-item__seal {
  background-color: color-mix(
    in srgb,
    var(--md-secondary) 8%,
    transparent
  ) !important; /* 红泥朱砂半透 */
  color: var(--md-secondary) !important;
  border-color: var(--md-secondary) !important;
  box-shadow: none !important; /* 印面压纸不浮起 */
  animation: ink-seal-press 0.45s cubic-bezier(0.19, 1, 0.22, 1) both;
}

.ledger-item__body {
  min-width: 0;
  flex: 1;
}

.ledger-item__title {
  margin: 0 0 4px;
  font-family: var(--md-font-display) !important; /* 碑拓宋体 */
  font-size: 14px;
  font-weight: 600;
  color: var(--md-primary);
  letter-spacing: 0.04em;
}

.ledger-item__desc {
  margin: 0;
  font-family: var(--md-font-kai) !important; /* 楷体 */
  font-size: 13px;
  line-height: 1.5;
  color: var(--md-on-surface-variant);
  word-wrap: break-word;
  word-break: break-all;
}

.ledger-footer {
  text-align: center;
  padding-top: var(--md-spacing-4);
  border-top: 1px dashed var(--md-outline-variant);
  color: var(--md-on-surface-variant);
  font-family: var(--md-font-kai) !important;
  font-size: 12px;
  letter-spacing: 0.08em;
  user-select: none;
  flex-shrink: 0;
}

@media (max-width: 1199px) {
  .inspiration-chat {
    flex-direction: column !important;
  }

  .inspiration-chat__timeline {
    display: none !important; /* 小屏同步收起 36px 进度轴，避免留白占位 */
  }

  .inspiration-chat__main {
    flex: 1;
    border-right: none;
  }
}

@media (max-width: 833px) {
  .inspiration-page {
    padding: max(var(--md-spacing-2), env(safe-area-inset-top))
      max(var(--md-spacing-2), env(safe-area-inset-right))
      max(var(--md-spacing-2), env(safe-area-inset-bottom))
      max(var(--md-spacing-2), env(safe-area-inset-left)) !important;
  }

  .inspiration-chat__header,
  .inspiration-chat__input {
    padding: var(--md-spacing-3);
  }

  /* 移动端头部拥挤时允许按钮行折行下沉，避免标题与操作挤压 */
  .inspiration-chat__header > div {
    flex-wrap: wrap;
    row-gap: var(--md-spacing-2);
  }

  .inspiration-chat__heading {
    flex: 1 1 100%;
  }

  .inspiration-chat__title {
    font-size: var(--md-title-medium);
  }
}

.inspiration-chat__title {
  font-family: var(--md-font-display); /* 碑拓宋体 */
  font-size: var(--md-title-large); /* 页面主标题升级 title 级 */
  font-weight: 600;
  letter-spacing: 0.03em; /* 碑拓骨力：小标题字距 */
  color: var(--md-primary);
}

/* 阶段视图水墨慢晕视差过渡 */
.ink-stage-enter-active,
.ink-stage-leave-active {
  transition: 
    opacity 0.4s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.4s cubic-bezier(0.22, 1, 0.36, 1);
}

.ink-stage-enter-from {
  opacity: 0;
  transform: translateY(12px) scale(0.995);
}

.ink-stage-leave-to {
  opacity: 0;
  transform: translateY(-8px) scale(0.995);
}

/* 头部操作按钮：常态松烟灰字标，hover 中性底 + 单枚朱砂落款，active 钤印微沉 */
.inspiration-header-btn {
  min-width: 0 !important;
  padding: 0 8px !important;
  height: 32px !important;
  display: inline-flex !important;
  align-items: center !important;
  gap: 4px !important;
  color: var(--md-on-surface-variant) !important;
  font-size: var(--md-label-medium) !important;
  font-family: var(--md-font-serif) !important;
  font-weight: 700 !important;
  transition:
    background-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.25s cubic-bezier(0.22, 1, 0.36, 1) !important;
  background: transparent !important;
  border: none !important;
  cursor: pointer !important;
}

.inspiration-header-btn:hover {
  background-color: var(--md-state-layer-hover) !important; /* 中性底 */
  color: var(--md-primary) !important; /* 焦墨文字，不落朱砂 */
}

.inspiration-header-btn:active {
  transform: translate(1px, 1px) !important;
  opacity: 0.8 !important;
}

.inspiration-header-btn:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}

.inspiration-header-btn__label {
  color: var(--md-on-surface-variant) !important; /* 常态松烟灰，与按钮文字同调 */
  font-weight: 900 !important;
  font-size: 14px !important;
  transition: color 0.25s cubic-bezier(0.22, 1, 0.36, 1) !important;
}

/* 悬浮时单枚朱砂落款，印章感收口于一处 */
.inspiration-header-btn:hover .inspiration-header-btn__label {
  color: var(--md-secondary) !important;
}

/* ============================================
   中间古雅挂轴式对话进度轴
   ============================================ */
.inspiration-chat__timeline {
  flex: 0 0 36px !important;
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
  background-color: var(--md-surface-dim) !important; /* 淡雅古风背景 */
  border-left: 1px solid var(--md-outline-variant) !important;
  border-right: 1px solid var(--md-outline-variant) !important;
  position: relative;
  padding: var(--md-spacing-6) 0 !important;
  z-index: 10;
}

/* 贯穿全高的墨晕丝绳细线 */
.timeline-line {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 50%;
  width: 1px;
  background-color: var(--md-outline-variant) !important; /* 极细墨晕线，代表思路脉络 */
  transform: translateX(-50%);
  z-index: 1;
}

.timeline-nodes {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--md-spacing-5);
  position: relative;
  z-index: 2;
  height: 100%;
  overflow-y: auto;
  /* 隐藏原生滚动条 */
  -ms-overflow-style: none !important;
  scrollbar-width: none !important;
  width: 100%;
}

.timeline-nodes::-webkit-scrollbar {
  display: none !important;
}

/* 进度节点方章按钮（与词笺方印统一微直角） */
.timeline-node-btn {
  width: 22px;
  height: 22px;
  border-radius: var(--md-radius-xs) !important; /* 方形节点章 */
  border: 1px solid var(--md-outline-variant) !important; /* 常态墨晕描边 */
  background-color: var(--md-surface) !important;
  color: var(--md-primary-dark) !important;
  display: grid;
  place-items: center;
  cursor: pointer;
  position: relative;
  transition:
    background-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.25s cubic-bezier(0.22, 1, 0.36, 1) !important;
  box-shadow: none !important; /* 静息无影 */
}

.timeline-node-seal {
  font-family: var(--md-font-serif) !important;
  font-size: 10px !important;
  font-weight: 700 !important;
  line-height: 1 !important;
}

/* 激活或悬浮状态：方形朱砂描边小印（激活指示），无影不浮起 */
.timeline-node-btn:hover,
.timeline-node-btn.is-active {
  background-color: color-mix(
    in srgb,
    var(--md-secondary) 8%,
    transparent
  ) !important; /* 朱砂淡染 */
  border-color: var(--md-secondary) !important; /* 朱砂描边 */
  color: var(--md-secondary) !important;
  transform: scale(1.15);
  box-shadow: none !important;
}

.timeline-node-btn:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}

/* 极致精美的 Tooltip 悬浮标签 */
.timeline-node-tooltip {
  position: absolute;
  right: 44px; /* 悬浮在左侧聊天界面上 */
  top: 50%;
  transform: translateY(-50%) translateX(6px);
  background-color: var(--md-surface) !important;
  color: var(--md-on-surface) !important;
  border: 1px solid var(--md-outline) !important;
  box-shadow: var(--md-elevation-paper-2) !important; /* 悬浮层柔影 */
  padding: 6px 12px !important;
  border-radius: var(--md-radius-xs) !important;
  font-family: var(--md-font-serif) !important; /* 落定标签用宋体 */
  font-size: 13px !important;
  white-space: nowrap;
  pointer-events: none;
  opacity: 0;
  transition:
    background-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.25s cubic-bezier(0.22, 1, 0.36, 1) !important;
  z-index: 100;
}

/* 悬停或键盘聚焦时展示 Tooltip，略带优雅的从右往左滑入效果 */
.timeline-node-btn:hover .timeline-node-tooltip,
.timeline-node-btn:focus-visible .timeline-node-tooltip {
  opacity: 1;
  transform: translateY(-50%) translateX(0);
}

@keyframes ink-seal-press {
  0% {
    opacity: 0;
    transform: scale(1.3) translateY(-4px);
  }
  65% {
    opacity: 0.95;
    transform: scale(0.92) translateY(1.5px);
  }
  100% {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}
</style>
