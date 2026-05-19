<!-- AIMETA P=蓝图确认_蓝图确认对话框|R=确认操作|NR=不含编辑功能|E=component:BlueprintConfirmation|X=internal|A=确认对话框|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="blueprint-confirm fade-in">
    <h2 class="blueprint-confirm__title">信息收集完成！</h2>

    <div class="blueprint-confirm__body">
      <div
        class="prose prose-lg max-w-none mx-auto mb-4"
        style="color: var(--md-on-surface-variant)"
        v-html="renderedAiMessage"
      ></div>
      <p class="blueprint-confirm__hint">
        我们已经收集了足够的信息来为您创建详细的小说蓝图。点击下方按钮开始生成您的专属故事大纲。
      </p>
    </div>

    <!-- 加载状态 -->
    <div v-if="isGenerating" class="blueprint-confirm__loading">
      <div class="blueprint-confirm__spinner">
        <div class="blueprint-confirm__spinner-track"></div>
        <div
          class="blueprint-confirm__spinner-fill"
          :class="{ 'blueprint-confirm__spinner-fill--done': progress >= 100 }"
        ></div>
        <div
          class="blueprint-confirm__spinner-center"
          :class="{ 'blueprint-confirm__spinner-center--done': progress >= 100 }"
        >
          <svg
            v-if="progress >= 100"
            class="w-5 h-5"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fill-rule="evenodd"
              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
              clip-rule="evenodd"
            ></path>
          </svg>
          <svg
            v-else
            class="w-5 h-5"
            fill="currentColor"
            viewBox="0 0 20 20"
            style="opacity: 0.8"
          >
            <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
          </svg>
        </div>
      </div>

      <div class="blueprint-confirm__loading-text">
        <h3 class="blueprint-confirm__loading-title">{{ loadingText }}</h3>
        <p class="blueprint-confirm__loading-desc">AI正在为您精心打造独特的故事蓝图...</p>

        <div class="blueprint-confirm__progress">
          <div class="blueprint-confirm__progress-track">
            <div
              class="blueprint-confirm__progress-bar"
              :class="{ 'blueprint-confirm__progress-bar--done': progress >= 100 }"
              :style="{ width: `${progress}%` }"
            ></div>
          </div>
        </div>

        <div class="blueprint-confirm__tip">
          <svg class="inline w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
            <path
              fill-rule="evenodd"
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
              clip-rule="evenodd"
            ></path>
          </svg>
          AI正在分析您的创意偏好，生成过程需要一些时间，请耐心等待...
        </div>
      </div>
    </div>

    <!-- 操作按钮 -->
    <div v-else class="blueprint-confirm__actions">
      <button
        @click="generateBlueprint"
        :disabled="isGenerating"
        class="md-btn md-btn-filled md-ripple blueprint-confirm__generate-btn"
      >
        <span class="flex items-center justify-center">
          <svg class="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
            <path
              d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"
            ></path>
          </svg>
          开始创建蓝图
        </span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { useGenerateBlueprintMutation } from '@/queries/novel'
import { globalAlert } from '@/composables/useAlert'

// 配置 marked
marked.setOptions({
  gfm: true, // 启用 GitHub 风格语法
  breaks: true, // 将单个换行视为 <br>
})

interface Props {
  aiMessage: string
  projectId?: string | null
}

const props = defineProps<Props>()

const emit = defineEmits<{
  blueprintGenerated: [response: any]
  back: []
}>()

const generateBlueprintMutation = useGenerateBlueprintMutation(() => props.projectId)
const isGenerating = ref(false)
const progress = ref(0)
const timeElapsed = ref(0)
const maxTime = 180 // 180秒超时

let progressTimer: NodeJS.Timeout | null = null
let timeoutTimer: NodeJS.Timeout | null = null

// 渲染 Markdown
const renderedAiMessage = computed(() => {
  const parsed = marked.parse(props.aiMessage)
  const html = typeof parsed === 'string' ? parsed : ''
  return DOMPurify.sanitize(html, {
    USE_PROFILES: { html: true },
  })
})

// 动态加载文本
const loadingText = computed(() => {
  if (progress.value >= 100) {
    return '生成完成！正在准备展示...'
  }

  const messages = [
    '正在分析故事结构...',
    '构建角色关系网络...',
    '生成情节发展脉络...',
    '完善世界观设定...',
    '优化章节安排...',
    '最后润色细节...',
  ]

  const index = Math.floor((progress.value / 100) * messages.length)
  return messages[Math.min(index, messages.length - 1)]
})

// 剩余时间计算
const timeRemaining = computed(() => {
  return Math.max(0, maxTime - timeElapsed.value)
})

const generateBlueprint = async () => {
  isGenerating.value = true
  progress.value = 0
  timeElapsed.value = 0

  // 启动进度条动画
  progressTimer = setInterval(() => {
    timeElapsed.value += 0.1

    // 非线性进度增长，前面快后面慢
    const normalizedTime = timeElapsed.value / maxTime
    if (normalizedTime < 0.7) {
      // 前70%时间内进度到80%
      progress.value = Math.min(80, (normalizedTime / 0.7) * 80)
    } else {
      // 后30%时间内从80%到95%
      const remainingProgress = (normalizedTime - 0.7) / 0.3
      progress.value = Math.min(95, 80 + remainingProgress * 15)
    }
  }, 100)

  // 60秒超时
  timeoutTimer = setTimeout(() => {
    clearTimers()
    isGenerating.value = false
    globalAlert.showError('生成超时，请稍后重试。如果问题持续，请检查网络连接。', '生成超时')
  }, maxTime * 1000)

  try {
    const response = await generateBlueprintMutation.mutateAsync()

    // API成功后，快速完成进度条到100%
    if (progressTimer) {
      clearInterval(progressTimer)
      progressTimer = null
    }

    // 动画到100%并显示完成状态
    progress.value = 100

    // 等待一下让用户看到100%完成状态，然后再切换界面
    await new Promise((resolve) => setTimeout(resolve, 800))

    // 清理并重置状态
    clearTimers()
    isGenerating.value = false

    // 通知父组件生成完成
    emit('blueprintGenerated', response)
  } catch (error) {
    console.error('生成蓝图失败:', error)
    clearTimers()
    isGenerating.value = false
    globalAlert.showError(
      `生成蓝图失败: ${error instanceof Error ? error.message : '未知错误'}`,
      '生成失败',
    )
  }
}

const clearTimers = () => {
  if (progressTimer) {
    clearInterval(progressTimer)
    progressTimer = null
  }
  if (timeoutTimer) {
    clearTimeout(timeoutTimer)
    timeoutTimer = null
  }
}

onUnmounted(() => {
  clearTimers()
})
</script>

<style scoped>
.blueprint-confirm {
  padding: var(--md-spacing-8);
  background-color: var(--md-surface);
  border-radius: var(--md-radius-xl);
  border: 1px solid var(--md-outline-variant);
  box-shadow: var(--md-elevation-2);
}

.blueprint-confirm__title {
  font-size: var(--md-headline-small);
  font-weight: 700;
  text-align: center;
  color: var(--md-on-surface);
  margin-bottom: var(--md-spacing-6);
}

.blueprint-confirm__body {
  text-align: center;
  margin-bottom: var(--md-spacing-8);
}

.blueprint-confirm__hint {
  font-size: var(--md-body-small);
  color: var(--md-on-surface-variant);
}

.blueprint-confirm__loading {
  text-align: center;
  padding: var(--md-spacing-8) 0;
}

.blueprint-confirm__spinner {
  position: relative;
  width: 5rem;
  height: 5rem;
  margin: 0 auto var(--md-spacing-6);
}

.blueprint-confirm__spinner-track {
  position: absolute;
  inset: 0;
  border: 3px solid var(--md-outline-variant);
  border-radius: var(--md-radius-full);
}

.blueprint-confirm__spinner-fill {
  position: absolute;
  inset: 0;
  border: 3px solid transparent;
  border-top-color: var(--md-primary);
  border-right-color: var(--md-primary);
  border-radius: var(--md-radius-full);
  animation: blueprint-spin 1s linear infinite;
}

.blueprint-confirm__spinner-fill--done {
  border-top-color: var(--md-success);
  border-right-color: var(--md-success);
  animation: none;
}

.blueprint-confirm__spinner-center {
  position: absolute;
  inset: 1rem;
  border-radius: var(--md-radius-full);
  background-color: var(--md-primary);
  color: var(--md-on-primary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.blueprint-confirm__spinner-center--done {
  background-color: var(--md-success);
}

.blueprint-confirm__loading-title {
  font-size: var(--md-title-medium);
  font-weight: 600;
  color: var(--md-on-surface);
  margin-bottom: var(--md-spacing-2);
}

.blueprint-confirm__loading-desc {
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-medium);
  margin-bottom: var(--md-spacing-4);
}

.blueprint-confirm__progress {
  max-width: 20rem;
  margin: 0 auto var(--md-spacing-6);
}

.blueprint-confirm__progress-track {
  width: 100%;
  height: 6px;
  background-color: var(--md-surface-container);
  border-radius: var(--md-radius-full);
  overflow: hidden;
}

.blueprint-confirm__progress-bar {
  height: 100%;
  background-color: var(--md-primary);
  border-radius: var(--md-radius-full);
  transition: width 1s ease-out;
}

.blueprint-confirm__progress-bar--done {
  background-color: var(--md-success);
}

.blueprint-confirm__tip {
  padding: var(--md-spacing-3) var(--md-spacing-4);
  background-color: var(--md-surface-container-low);
  border-radius: var(--md-radius-sm);
  border: 1px solid var(--md-outline-variant);
  font-size: var(--md-body-small);
  color: var(--md-on-surface-variant);
  max-width: 28rem;
  margin: 0 auto;
}

.blueprint-confirm__actions {
  text-align: center;
}

.blueprint-confirm__generate-btn {
  padding: var(--md-spacing-3) var(--md-spacing-8);
  font-weight: 600;
}

@keyframes blueprint-spin {
  to { transform: rotate(360deg); }
}

@media (prefers-reduced-motion: reduce) {
  .blueprint-confirm__spinner-fill {
    animation: none;
    opacity: 0.7;
  }
}

.blueprint-confirm__loading-text {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--md-spacing-2);
}
</style>
