<!-- AIMETA P=灵感模式_AI对话创作|R=对话创作界面|NR=不含写作台功能|E=route:/inspiration#component:InspirationMode|X=ui|A=对话界面|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="flex items-center justify-center min-h-screen p-4">
    <div class="w-full max-w-6xl mx-auto">
      <!-- 灵感模式交互界面 -->
      <div
        v-if="!showBlueprintConfirmation && !showBlueprint"
        class="h-[90vh] max-h-[950px] flex flex-col bg-white rounded-2xl shadow-2xl overflow-hidden fade-in"
      >
        <!-- 头部 -->
        <div class="p-4 border-b border-gray-200">
          <div class="flex justify-between items-center">
            <div class="flex items-center gap-2">
              <span class="relative flex h-3 w-3">
                <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                <span class="relative inline-flex rounded-full h-3 w-3 bg-indigo-500"></span>
              </span>
              <span class="text-sm font-medium text-indigo-600">与“文思”对话中...</span>
            </div>
            <div class="flex items-center gap-4">
              <span v-if="currentTurn > 0" class="text-sm font-medium text-gray-500 bg-gray-100 px-2 py-1 rounded-md">
                第 {{ currentTurn }} 轮
              </span>
              <button
                @click="handleRestart"
                title="重新开始"
                class="text-gray-400 hover:text-indigo-600 transition-colors"
              >
                <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
                </svg>
              </button>
              <button
                @click="exitConversation"
                title="返回首页"
                class="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  class="h-6 w-6"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        <!-- 聊天区域 -->
        <div class="flex-1 p-6 overflow-y-auto space-y-6 relative" ref="chatArea">
          <transition name="fade">
            <InspirationLoading v-if="isInitialLoading" />
          </transition>
          <ChatBubble
            v-for="(message, index) in chatMessages"
            :key="index"
            :message="message.content"
            :type="message.type"
          />
          <div v-if="isAssistantResponding && !isInitialLoading" class="w-full flex justify-start">
            <div class="chat-bubble-ai max-w-md lg:max-w-lg p-4 shadow-md fade-in">
              <div class="flex items-center gap-3 text-sm text-gray-600">
                <span>文思正在组织灵感</span>
                <span class="flex gap-1" aria-hidden="true">
                  <span class="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse"></span>
                  <span class="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" style="animation-delay: 0.15s"></span>
                  <span class="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" style="animation-delay: 0.3s"></span>
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- 输入区域 -->
        <div class="p-4 border-t border-gray-200 bg-gray-50">
          <ConversationInput
            :ui-control="currentUIControl"
            :loading="novelStore.isLoading || isInitialLoading || isCheckingModelConfig || !conversationStarted"
            @submit="handleUserInput"
          />
        </div>
      </div>

      <!-- 蓝图确认界面 -->
      <BlueprintConfirmation
        v-if="showBlueprintConfirmation"
        :ai-message="confirmationMessage"
        @blueprint-generated="handleBlueprintGenerated"
        @back="backToConversation"
      />

      <!-- 大纲展示界面 -->
      <BlueprintDisplay
        v-if="showBlueprint"
        :blueprint="completedBlueprint"
        :ai-message="blueprintMessage"
        @confirm="handleConfirmBlueprint"
        @regenerate="handleRegenerateBlueprint"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useNovelStore } from '@/stores/novel'
import type { UIControl, Blueprint } from '@/api/novel'
import { getLLMConfigBundle } from '@/api/llm'
import ChatBubble from '@/components/ChatBubble.vue'
import ConversationInput from '@/components/ConversationInput.vue'
import BlueprintConfirmation from '@/components/BlueprintConfirmation.vue'
import BlueprintDisplay from '@/components/BlueprintDisplay.vue'
import InspirationLoading from '@/components/InspirationLoading.vue'
import { globalAlert } from '@/composables/useAlert'

interface ChatMessage {
  content: string
  type: 'user' | 'ai'
}

const INSPIRATION_OPENING_MESSAGE = `灵感已经落座。

告诉我，它最初是什么？一个画面、一句对白、一个人物，或者一种挥之不去的感觉都可以。`

const INSPIRATION_INITIAL_UI_CONTROL: UIControl = {
  type: 'text_input',
  placeholder: '描述你的第一个灵感火花...',
}

const router = useRouter()
const route = useRoute()
const novelStore = useNovelStore()

const conversationStarted = ref(false)
const isInitialLoading = ref(true)
const showBlueprintConfirmation = ref(false)
const showBlueprint = ref(false)
const chatMessages = ref<ChatMessage[]>([])
const currentUIControl = ref<UIControl | null>(null)
const currentTurn = ref(0)
const completedBlueprint = ref<Blueprint | null>(null)
const confirmationMessage = ref('')
const blueprintMessage = ref('')
const chatArea = ref<HTMLElement>()
const isCheckingModelConfig = ref(false)
const isAssistantResponding = ref(false)

const hasRequiredModelConfig = async () => {
  const bundle = await getLLMConfigBundle()
  const hasLLMModel = bundle.models.some(model => model.is_enabled && Boolean(model.capabilities.chat))
    || Boolean(bundle.legacy?.llm_provider_model?.trim())
  const hasEmbeddingModel = bundle.models.some(model => model.is_enabled && Boolean(model.capabilities.embedding))
    || Boolean(bundle.legacy?.embedding_provider_model?.trim())
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

// 清空所有状态，开始新的灵感对话
const resetInspirationMode = () => {
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
  
  // 清空 store 中的当前项目和对话状态
  novelStore.setCurrentProject(null)
  novelStore.currentConversationState = {}
}

const exitConversation = async () => {
  const confirmed = await globalAlert.showConfirm('确定要退出灵感模式吗？当前进度可能会丢失。', '退出确认')
  if (confirmed) {
    resetInspirationMode()
    router.push('/workspace')
  }
}

const handleRestart = async () => {
  const confirmed = await globalAlert.showConfirm('确定要重新开始吗？当前对话内容将会丢失。', '重新开始确认')
  if (confirmed) {
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
    await novelStore.createProject('未命名灵感', '开始灵感模式')

    // 首句是固定引导语，项目创建完成后立即展示；真正的 AI 生成从用户首答开始。
    await showLocalOpeningMessage()
  } catch (error) {
    console.error('启动灵感模式失败:', error)
    globalAlert.showError(`无法开始灵感模式: ${error instanceof Error ? error.message : '未知错误'}`, '启动失败')
    resetInspirationMode()
    router.push('/workspace')
  }
}

const restoreConversation = async (projectId: string) => {
  isInitialLoading.value = true
  try {
    await novelStore.loadProject(projectId)
    const project = novelStore.currentProject
    if (project && project.conversation_history) {
      conversationStarted.value = true
      chatMessages.value = project.conversation_history.map((item): ChatMessage | null => {
        if (item.role === 'user') {
          try {
            const userInput = JSON.parse(item.content)
            return { content: userInput.value, type: 'user' }
          } catch {
            return { content: item.content, type: 'user' }
          }
        } else { // assistant
          try {
            const assistantOutput = JSON.parse(item.content)
            return { content: assistantOutput.ai_message, type: 'ai' }
          } catch {
            return { content: item.content, type: 'ai' }
          }
        }
      }).filter((msg): msg is ChatMessage => msg !== null && msg.content !== null) // 过滤掉空的 user message

      const lastAssistantMsgStr = project.conversation_history.filter(m => m.role === 'assistant').pop()?.content
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
      // 计算当前轮次
      currentTurn.value = project.conversation_history.filter(m => m.role === 'assistant').length
      if (currentTurn.value === 0 && chatMessages.value.length === 0) {
        await showLocalOpeningMessage()
      }
      await scrollToBottom()
    }
  } catch (error) {
    console.error('恢复对话失败:', error)
    globalAlert.showError(`无法恢复对话: ${error instanceof Error ? error.message : '未知错误'}`, '加载失败')
    resetInspirationMode()
  } finally {
    isInitialLoading.value = false
  }
}

const handleUserInput = async (userInput: any) => {
  const isFirstAssistantTurn = currentTurn.value === 0 && chatMessages.value.length === 0
  try {
    // 如果有用户输入，添加到聊天记录
    if (userInput && userInput.value) {
      chatMessages.value.push({
        content: userInput.value,
        type: 'user'
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
          type: 'ai'
        })
        assistantMessageIndex = chatMessages.value.length - 1
      }
      chatMessages.value[assistantMessageIndex].content += delta
      await scrollToBottom()
    }

    const response = await novelStore.sendConversationStream(userInput, (delta) => {
      void appendAssistantDelta(delta)
    })

    // 首次加载完成后，关闭加载动画
    if (isInitialLoading.value) {
      isInitialLoading.value = false
    }

    // 如果模型没有提前吐出 ai_message 字段，最终结果仍然兜底展示。
    if (assistantMessageIndex === null) {
      chatMessages.value.push({
        content: response.ai_message,
        type: 'ai'
      })
    } else {
      chatMessages.value[assistantMessageIndex].content = response.ai_message
    }
    currentTurn.value++

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
    // 确保在出错时也停止初始加载状态
    if (isInitialLoading.value) {
      isInitialLoading.value = false
    }
    globalAlert.showError(`抱歉，与AI连接时遇到问题: ${error instanceof Error ? error.message : '未知错误'}`, '通信失败')
    if (isFirstAssistantTurn) {
      resetInspirationMode()
      router.push('/workspace')
    }
  } finally {
    isAssistantResponding.value = false
  }
}

const handleGenerateBlueprint = async () => {
  try {
    const response = await novelStore.generateBlueprint()
    handleBlueprintGenerated(response)
  } catch (error) {
    console.error('生成蓝图失败:', error)
    globalAlert.showError(`生成蓝图失败: ${error instanceof Error ? error.message : '未知错误'}`, '生成失败')
  }
}

const handleBlueprintGenerated = (response: any) => {
  console.log('收到蓝图生成完成事件:', response)
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
    await novelStore.saveBlueprint(completedBlueprint.value)
    // 跳转到写作工作台
    if (novelStore.currentProject) {
      router.push(`/projects/${novelStore.currentProject.id}/write`)
    }
  } catch (error) {
    console.error('保存蓝图失败:', error)
    globalAlert.showError(`保存蓝图失败: ${error instanceof Error ? error.message : '未知错误'}`, '保存失败')
  }
}

const scrollToBottom = async () => {
  await nextTick()
  if (chatArea.value) {
    chatArea.value.scrollTop = chatArea.value.scrollHeight
  }
}

onMounted(async () => {
  const projectId = route.query.project_id as string
  if (projectId) {
    const hasRequiredConfig = await ensureModelConfigOrRedirect()
    if (!hasRequiredConfig) {
      isInitialLoading.value = false
      return
    }
    await restoreConversation(projectId)
  } else {
    // 直接进入灵感模式，不再停留在二次确认入口页
    await startConversation()
  }
})
</script>
