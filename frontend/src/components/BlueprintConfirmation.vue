<!-- AIMETA P=蓝图确认_蓝图确认对话框|R=确认操作|NR=不含编辑功能|E=component:BlueprintConfirmation|X=internal|A=确认对话框|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="blueprint-confirm fade-in" data-provenance="ai">
    <h2 class="blueprint-confirm__title">信息收集完成！</h2>

    <div class="blueprint-confirm__body">
      <!-- 极富设计感的卡片式大纲卡片流，使内容按照块逻辑严谨区分 -->
      <div class="blueprint-confirm__cards-container">
        <div 
          v-for="(block, idx) in parsedBlocks" 
          :key="idx" 
          class="blueprint-confirm__card-wrapper"
        >
          <div 
            class="blueprint-confirm__card"
            :class="{ 'blueprint-confirm__card--intro': block.title === '故事蓝图引言' }"
          >
            <!-- 金石落印，微倾斜的红泥闲章 -->
            <div class="blueprint-confirm__card-seal">
              {{ idxToChinese(idx) }}
            </div>

            <!-- 正规版块卡片头部（引言卡片隐藏大标题，呈现错落有致之美） -->
            <h3 v-if="block.title !== '故事蓝图引言'" class="blueprint-confirm__card-title">
              {{ block.title }}
            </h3>
            
            <!-- 卡片正文 Markdown 内容 -->
            <div class="blueprint-confirm__card-content prose" v-html="block.content"></div>
          </div>
        </div>
      </div>

      <p class="blueprint-confirm__hint mt-6">
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

      <div class="blueprint-confirm__loading-text" role="status" aria-live="polite">
        <h3 class="blueprint-confirm__loading-title">{{ loadingText }}</h3>
        <p class="blueprint-confirm__loading-desc">AI正在为您精心打造独特的故事蓝图...</p>

        <div class="blueprint-confirm__progress">
          <div
            class="blueprint-confirm__progress-track"
            role="progressbar"
            aria-label="蓝图生成进度"
            aria-valuemin="0"
            aria-valuemax="100"
            :aria-valuenow="Math.round(progress)"
          >
            <div
              class="blueprint-confirm__progress-bar"
              :class="{ 'blueprint-confirm__progress-bar--done': progress >= 100 }"
              :style="{ '--blueprint-progress-scale': progressScale }"
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
import type { BlueprintGenerationResponse } from '@/api/novel'

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

const idxToChinese = (idx: number): string => {
  if (idx === 0) return '启'
  const chineseNums = ['', '壹', '贰', '叁', '肆', '伍', '陆', '柒', '捌', '玖', '拾']
  return chineseNums[idx] || String(idx)
}

const emit = defineEmits<{
  blueprintGenerated: [response: BlueprintGenerationResponse]
  back: []
}>()

const generateBlueprintMutation = useGenerateBlueprintMutation(() => props.projectId)
const isGenerating = ref(false)
const progress = ref(0)
const timeElapsed = ref(0)
const maxTime = 480 // 与后端蓝图生成超时保持一致

let progressTimer: NodeJS.Timeout | null = null
let timeoutTimer: NodeJS.Timeout | null = null

// 辅助渲染并净化 Markdown 的内部逻辑
const renderMarkdown = (text: string): string => {
  const parsed = marked.parse(text)
  const html = typeof parsed === 'string' ? parsed : ''
  return DOMPurify.sanitize(html, {
    USE_PROFILES: { html: true },
  })
}

interface BlueprintBlock {
  title: string
  content: string
}

// 动态将大篇幅 Markdown 文本按照标题切分为独立的 Vue 古雅卡片块
const parsedBlocks = computed<BlueprintBlock[]>(() => {
  const rawText = props.aiMessage || ''
  if (!rawText) return []

  // 正则匹配传统中式大写序号“一、”、“二、”等标题行或 Markdown 标题行
  const blockRegex = /\n(?:#+\s+)?([一二三四五六七八九十]+[、.．\s]\s*[^\n]+)/g
  
  const blocks: BlueprintBlock[] = []
  const matches: { index: number; title: string; textIndex: number }[] = []
  
  let match
  while ((match = blockRegex.exec(rawText)) !== null) {
    matches.push({
      index: match.index,
      title: match[1].trim(),
      textIndex: match.index + match[0].length
    })
  }

  // 降级兼容：如未找到国风大写序号，寻找标准的 Markdown H2/H3 标题
  if (matches.length === 0) {
    const mdTitleRegex = /\n(?:#+\s+)([^\n]+)/g
    while ((match = mdTitleRegex.exec(rawText)) !== null) {
      matches.push({
        index: match.index,
        title: match[1].trim(),
        textIndex: match.index + match[0].length
      })
    }
  }

  // 兜底方案：如果没有找到任何明显的模块标题，直接整体作为一个块卡片
  if (matches.length === 0) {
    return [{
      title: '小说概念蓝图',
      content: renderMarkdown(rawText)
    }]
  }

  // 1. 抽取蓝图开篇引言部分
  const introText = rawText.slice(0, matches[0].index).trim()
  if (introText) {
    blocks.push({
      title: '故事蓝图引言',
      content: renderMarkdown(introText)
    })
  }

  // 2. 切分剩余的国风模块卡片
  for (let i = 0; i < matches.length; i++) {
    const current = matches[i]
    const next = matches[i + 1]
    const endPos = next ? next.index : rawText.length
    const blockContent = rawText.slice(current.textIndex, endPos).trim()
    
    blocks.push({
      title: current.title,
      content: renderMarkdown(blockContent)
    })
  }

  return blocks
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
const progressScale = computed(() => Math.max(0, Math.min(100, progress.value)) / 100)

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

  // 与后端蓝图生成超时保持一致
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
  padding: var(--md-spacing-6) var(--md-spacing-8);
  background-color: var(--md-surface);
  border-radius: var(--md-radius-xs) !important; /* 界格微直角 */
  border: 1px solid var(--md-jiege) !important; /* 1px 界格发线，与稿纸同构 */
  box-shadow: var(--md-elevation-paper-1) !important;
  /* 弹性布局一屏内高贴合收敛，绝不发生视口下溢，击杀看不全 Bug */
  height: 100%;
  max-height: calc(var(--app-viewport-unit) - 120px) !important;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
}

.blueprint-confirm__title {
  font-size: var(--md-headline-small);
  font-weight: 700;
  letter-spacing: 0.05em; /* 碑拓骨力：大标题拉开字距 */
  text-align: center;
  color: var(--md-primary);
  margin-bottom: var(--md-spacing-4);
  flex-shrink: 0; /* 标题固定不缩窄 */
}

.blueprint-confirm__body {
  text-align: center;
  margin-bottom: var(--md-spacing-4);
  flex: 1; /* 弹性占据全部剩余高度 */
  overflow-y: auto; /* 允许纵向平滑滚动 */
  padding-right: var(--md-spacing-2);
  min-height: 0; /* flex 内部 overflow 滚动必须 */
  
  /* 剔除多余粗重进度条/滚动条视觉，完美呈现大张宣纸 */
  -ms-overflow-style: none;
  scrollbar-width: none;
}

.blueprint-confirm__body::-webkit-scrollbar {
  display: none;
}

/* ============================================
   极致中式古风“手撕宣纸信笺手札”卡片排版
   ============================================ */
.blueprint-confirm__cards-container {
  display: flex;
  flex-direction: column;
  gap: 20px; /* 严格物理间距，隔离认知负荷 */
  max-width: 900px;
  margin: 0 auto;
  padding: var(--md-spacing-2) var(--md-spacing-4);
}

/* 卡片外壳：硬影清零，hover 仅保留轻微上浮 */
.blueprint-confirm__card-wrapper {
  transition: transform 0.3s cubic-bezier(0.22, 1, 0.36, 1);
  will-change: transform;
}

.blueprint-confirm__card-wrapper:hover {
  transform: translateY(-2px);
}

/* AI 蓝图稿卡片：描红三信号之 wash 底 + 1px 描红界栏，直边取代手撕毛边 */
.blueprint-confirm__card {
  background-color: var(--md-miaohong-wash);
  border: 1px solid var(--md-miaohong-line);
  border-radius: var(--md-radius-xs);
  padding: var(--md-spacing-6) var(--md-spacing-8);
  text-align: left;
  position: relative;
}

/* 引言卡片专属：洗色略深的晕染，错落雅致 */
.blueprint-confirm__card--intro {
  background: linear-gradient(
    135deg,
    var(--md-miaohong-wash) 70%,
    var(--md-miaohong-line) 100%
  );
}

/* 右上角钤印金石闲章（微倾斜阳刻） */
.blueprint-confirm__card-seal {
  position: absolute;
  top: 18px;
  right: 22px;
  width: 38px;
  height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid var(--md-secondary);
  color: var(--md-secondary);
  font-family: var(--md-font-display);
  font-size: 19px;
  font-weight: 900;
  line-height: 1;
  transform: rotate(-8deg);
  user-select: none;
  background-color: color-mix(in srgb, var(--md-secondary) 2%, transparent);
  /* 印章一律无影 */
  transition:
    background-color 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    color 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.3s cubic-bezier(0.22, 1, 0.36, 1);
  z-index: 10;
}

.blueprint-confirm__card-wrapper:hover .blueprint-confirm__card-seal {
  transform: rotate(-4deg);
  color: var(--md-secondary);
  border-color: var(--md-secondary);
}

/* 卡片标题：AI 草稿挂描红 + 真楷 */
.blueprint-confirm__card-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: var(--md-font-kai);
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 0.03em;
  color: var(--md-miaohong-strong);
  margin-bottom: var(--md-spacing-4);
  border-bottom: 1px dashed var(--md-miaohong-line);
  padding-bottom: var(--md-spacing-2);
  margin-top: 0;
  padding-right: 50px; /* 留出印章的安全区域 */
}

/* 卡片正文：描红界格行线与行高精准锁定，AI 稿正文同挂描红 + 真楷 */
.blueprint-confirm__card-content {
  text-align: justify;
  text-justify: inter-ideograph;
  font-family: var(--md-font-kai);
  color: var(--md-miaohong);
  /* 淡朱横格底纹底图 */
  background-image: repeating-linear-gradient(
    to bottom,
    transparent,
    transparent 27px,
    var(--md-miaohong-line) 27px,
    var(--md-miaohong-line-strong) 28px
  );
  background-size: 100% 28px;
  padding: 14px 0; /* 精密微调内边距确保首行刚好落于红格线上 */
}

/* 让卡片内部的段落、列表精准契合 28px 朱丝栏 */
.blueprint-confirm__card-content :deep(p) {
  line-height: 28px;
  margin-bottom: 28px; /* 段落间距强制为 1 行格子高度，杜绝错位 */
  text-indent: 2em; /* 优雅的首行缩进 */
  text-align: left;
}

.blueprint-confirm__card-content :deep(p:last-child) {
  margin-bottom: 0;
}

.blueprint-confirm__card-content :deep(ol),
.blueprint-confirm__card-content :deep(ul) {
  padding-left: 24px;
  margin-top: 0;
  margin-bottom: 28px;
  text-align: left;
}

.blueprint-confirm__card-content :deep(li) {
  line-height: 28px;
  margin-bottom: 0; /* 列表项内部折行，仍能贴合底线 */
}

.blueprint-confirm__card-content :deep(blockquote) {
  border: 1px dashed var(--md-miaohong-line);
  border-left: 1px solid var(--md-miaohong-line-strong);
  background-color: var(--md-miaohong-wash);
  padding: 14px 18px;
  margin: 14px 0;
  border-radius: var(--md-radius-xs);
  text-align: left;
  line-height: 28px;
}

.blueprint-confirm__hint {
  font-size: var(--md-body-small);
  color: var(--md-on-surface-variant);
}

/* ============================================
   极致中国风 Loading “水墨太极气流”
   ============================================ */
.blueprint-confirm__loading {
  text-align: center;
  padding: var(--md-spacing-8) 0;
}

.blueprint-confirm__spinner {
  position: relative;
  width: 6.5rem;
  height: 6.5rem;
  margin: 0 auto var(--md-spacing-6);
  background: radial-gradient(circle, color-mix(in srgb, var(--md-secondary) 4%, transparent) 0%, transparent 70%);
  border-radius: 50%;
}

/* 飞舞在太极外圈的泼墨风暴气旋环线 */
.blueprint-confirm__spinner-track {
  position: absolute;
  inset: 0;
  border: 2px dashed color-mix(in srgb, var(--md-on-surface) 15%, transparent);
  border-top-color: transparent;
  border-bottom-color: transparent;
  border-radius: 50%;
  animation: md-spin 2.6s linear infinite;
}

/* 朱砂红泥与焦墨交织的阴阳太极流转 */
.blueprint-confirm__spinner-fill {
  position: absolute;
  inset: 0.9rem;
  border: 3px solid transparent;
  border-top-color: var(--md-secondary); /* 朱砂红 */
  border-bottom-color: color-mix(in srgb, var(--md-on-surface) 80%, transparent); /* 焦墨 */
  border-radius: 50%;
  animation: tai-chi-spin 1.5s cubic-bezier(0.42, 0, 0.58, 1) infinite;
}

.blueprint-confirm__spinner-fill--done {
  border-top-color: var(--md-success);
  border-bottom-color: var(--md-success);
  animation: none;
}

/* 核心焦墨描边圆盘（朱砂罕用：不再实心朱盘） */
.blueprint-confirm__spinner-center {
  position: absolute;
  inset: 1.9rem;
  border-radius: 50%;
  background-color: var(--md-surface);
  border: 2px solid var(--md-primary); /* 焦墨描边 */
  color: var(--md-primary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.blueprint-confirm__spinner-center--done {
  background-color: var(--md-success);
  border-color: var(--md-success);
  color: var(--md-on-success);
  box-shadow: none;
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
  border-radius: var(--md-radius-xs); /* 微直角，不用胶囊 */
  overflow: hidden;
}

.blueprint-confirm__progress-bar {
  width: 100%;
  height: 100%;
  background-color: var(--md-primary);
  border-radius: var(--md-radius-xs);
  transform-origin: left center;
  transform: scaleX(var(--blueprint-progress-scale, 0));
  transition: transform 1s ease-out;
  will-change: transform;
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
  border-radius: var(--md-radius-xs); /* 微直角方印 */
  background-color: var(--md-secondary); /* 朱砂实底落印钮（提交类主动作） */
  color: var(--md-on-secondary); /* 熟宣字 */
  border: 1px solid var(--md-secondary-dark);
  box-shadow: none; /* 落印钮静息无影 */
  transition: background-color 0.15s, box-shadow 0.15s;
}

.blueprint-confirm__generate-btn:hover:not(:disabled) {
  background-color: var(--md-secondary-dark);
  box-shadow: var(--md-elevation-paper-1);
}

.blueprint-confirm__generate-btn:active:not(:disabled) {
  box-shadow: none; /* 按下影清零，印落纸面 */
}

/* ============================================
   深夜案头自适应（暗色模式）
   说明：描红洗色与界栏均为明暗自适应 token，
   此处只保留暗色下刻意加深卡面的设计决策。
   ============================================ */
:root[data-theme='dark'] .blueprint-confirm__card {
  background-color: var(--md-surface-dim);
}

:root[data-theme='dark'] .blueprint-confirm__card--intro {
  background: linear-gradient(
    135deg,
    var(--md-surface-dim) 70%,
    var(--md-miaohong-line) 100%
  );
}

/* 传统太极流转动画与飞旋气流 */
@keyframes tai-chi-spin {
  to { transform: rotate(360deg); }
}

@keyframes md-spin {
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

/* 窄屏案头：小屏留白收敛，手撕卡片防溢出 */
@media (max-width: 640px) {
  .blueprint-confirm {
    padding: var(--md-spacing-4);
  }

  .blueprint-confirm__cards-container {
    padding: var(--md-spacing-1) var(--md-spacing-2);
  }

  .blueprint-confirm__card {
    padding: var(--md-spacing-4);
  }

  .blueprint-confirm__card-seal {
    top: 12px;
    right: 14px;
    width: 32px;
    height: 32px;
    font-size: 16px;
  }

  .blueprint-confirm__card-title {
    padding-right: 42px;
  }
}
</style>
