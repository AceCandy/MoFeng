<!-- AIMETA P=聊天气泡_对话消息展示|R=消息气泡|NR=不含输入功能|E=component:ChatBubble|X=internal|A=气泡组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div :class="wrapperClass">
    <div :class="bubbleClass">
      <!-- AI 消息支持 markdown 渲染 -->
      <div 
        v-if="type === 'ai'" 
        class="prose prose-sm max-w-none prose-headings:mt-2 prose-headings:mb-1 prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0"
        v-html="renderedMessage"
      ></div>
      <!-- 用户消息保持原样 -->
      <div v-else>{{ message }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import DOMPurify from 'dompurify'

interface Props {
  message: string
  type: 'user' | 'ai'
}

const props = defineProps<Props>()

// 简单的 markdown 解析函数
const parseMarkdown = (text: string): string => {
  if (!text) return ''
  
  // 处理转义字符
  let parsed = text
    .replace(/\\n/g, '\n')
    .replace(/\\\"/g, '"')
    .replace(/\\'/g, "'")
    .replace(/\\\\/g, '\\')
  
  // 处理加粗文本 **text**
  parsed = parsed.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
  
  // 处理斜体文本 *text*，采用匹配字符级还原，完美替代 Lookbehind 语法以规避低版本 WebKit 引擎致命白屏崩溃
  parsed = parsed.replace(/([^\*]|^)\*([^\*]+)\*(?!\*)/g, '$1<em>$2</em>')
  
  // 处理选项列表 A) text
  parsed = parsed.replace(/^([A-Z])\)\s*\*\*(.*?)\*\*(.*)/gm, '<div class="mb-2"><span class="chat-bubble__option-marker">$1</span><strong>$2</strong>$3</div>')
  
  // 处理普通换行
  parsed = parsed.replace(/\n/g, '<br>')
  
  // 处理多个连续的 <br> 标签为段落
  parsed = parsed.replace(/(<br\s*\/?>\s*){2,}/g, '</p><p class="mt-2">')
  
  // 包装在段落标签中
  if (!parsed.includes('<p>')) {
    parsed = `<p>${parsed}</p>`
  }

  return DOMPurify.sanitize(parsed, {
    USE_PROFILES: { html: true },
  })
}

const renderedMessage = computed(() => {
  if (props.type === 'ai') {
    return parseMarkdown(props.message)
  }
  return props.message
})

const wrapperClass = computed(() => {
  return `w-full flex ${props.type === 'ai' ? 'justify-start' : 'justify-end'}`
})

const bubbleClass = computed(() => {
  const isAI = props.type === 'ai'
  // AI 对话直接铺满（w-full max-w-none）以饱满展示长卷大纲，用户对话保持 max-w-[75%] 以便于靠右对齐
  const baseClass = `${isAI ? 'w-full max-w-none' : 'max-w-[75%]'} p-4 fade-in`
  const typeClass = isAI ? 'chat-bubble-ai' : 'chat-bubble-user'
  return `${baseClass} ${typeClass}`
})
</script>

<style scoped>
.chat-bubble__option-marker {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.5rem;
  height: 1.5rem;
  background-color: rgba(184, 60, 50, 0.08) !important; /* 朱砂淡染 */
  color: var(--md-secondary) !important; /* 朱砂红 */
  border: 1px solid var(--md-secondary) !important; /* 朱砂红细框 */
  border-radius: var(--md-radius-xs) !important; /* 金石方直印章 */
  font-size: var(--md-label-small);
  font-weight: 700;
  margin-right: 0.5rem;
  box-shadow: 1px 1px 0px rgba(184, 60, 50, 0.15) !important; /* 微印章硬影 */
}

/* 「手撕毛边宣纸」 AI 气泡重构 */
.chat-bubble-ai {
  background-color: var(--md-surface) !important;
  color: var(--md-on-surface) !important;
  /* 精细的多边形剪裁模拟参差不齐的手撕宣纸毛边 */
  clip-path: polygon(
    0% 2%, 8% 0.5%, 19% 1.5%, 31% 0.5%, 44% 1.8%, 56% 0.8%, 69% 1.5%, 81% 0.5%, 93% 1.8%, 100% 2%, 
    99.2% 15%, 100% 32%, 98.8% 48%, 99.5% 65%, 98.5% 82%, 99.2% 98%, 
    91% 99.2%, 79% 98.2%, 66% 99.2%, 54% 98.5%, 41% 99.2%, 29% 98.2%, 16% 99.2%, 0% 98%,
    0.8% 81%, 0% 63%, 1.2% 46%, 0% 28%, 0.8% 12%
  ) !important;
  padding: 1.25rem 2rem 1.25rem 1.5rem !important;
  border: none !important;
  box-shadow: none !important;
  /* 搭配 drop-shadow 滤镜产生形状完美的硬偏置拓片影 */
  filter: drop-shadow(3px 3px 0px rgba(28, 32, 34, 0.12)) !important;
  /* 显式声明will-change，提前提升图层防止高频重绘卡顿 */
  will-change: filter, transform !important;
  /* 字体使用清隽宋体 */
  font-family: var(--md-font-serif) !important;
  font-size: 15px !important;
  line-height: 1.6 !important;
  letter-spacing: 0.03em !important;
  position: relative !important;
  animation: ink-fade-in 0.8s cubic-bezier(0.22, 1, 0.36, 1) forwards !important;
}

/* 段落内超链接（Inline Link）古典竹青色手绘下划线微动效 */
:deep(.prose a) {
  color: var(--md-primary-dark) !important;
  text-decoration: none !important;
  border-bottom: 1px dashed var(--md-primary) !important;
  transition:
    background-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.25s cubic-bezier(0.22, 1, 0.36, 1) !important;
  padding-bottom: 1px !important;
}

:deep(.prose a:hover) {
  color: var(--md-secondary) !important;
  border-bottom: 1px solid var(--md-secondary) !important;
  text-shadow: 0.5px 0.5px 0px rgba(184, 60, 50, 0.1) !important;
}

/* 夹批朱印方章，金石点睛 */
.chat-bubble-ai::before {
  content: '文' !important;
  position: absolute !important;
  right: 18px !important;
  top: 14px !important;
  font-family: var(--md-font-serif) !important;
  font-size: 9px !important;
  font-weight: bold !important;
  color: rgba(184, 60, 50, 0.28) !important;
  border: 1px solid rgba(184, 60, 50, 0.28) !important;
  border-radius: 2px !important; /* 方形朱砂微印章 */
  width: 14px !important;
  height: 14px !important;
  display: grid !important;
  place-items: center !important;
  line-height: 1 !important;
  box-shadow: 0.5px 0.5px 0px rgba(184, 60, 50, 0.15) !important;
}

/* 焦墨手书用户气泡重构 */
.chat-bubble-user {
  background-color: var(--md-primary) !important; /* 焦墨底色 */
  color: var(--md-on-primary) !important;
  border-radius: var(--md-radius-xs) !important; /* 方直微圆角 */
  padding: 0.85rem 1.25rem !important;
  border: 1px solid var(--md-outline) !important;
  /* 朱砂小落款右下硬影 */
  box-shadow: 3px 3px 0px rgba(184, 60, 50, 0.22) !important;
  font-family: var(--md-font-kai) !important;
  font-size: 15px !important;
  letter-spacing: 0.02em !important;
  animation: ink-fade-in 0.8s cubic-bezier(0.22, 1, 0.36, 1) forwards !important;
}

/* 模拟熟宣水墨渐显：从模糊、淡色到清晰凝重 */
@keyframes ink-fade-in {
  0% {
    opacity: 0;
    transform: translateY(8px);
  }
  100% {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
