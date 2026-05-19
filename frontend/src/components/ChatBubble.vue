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
  
  // 处理斜体文本 *text*
  parsed = parsed.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>')
  
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
  const baseClass = 'max-w-md lg:max-w-lg p-4 fade-in'
  const typeClass = props.type === 'ai' ? 'chat-bubble-ai' : 'chat-bubble-user'
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
  background-color: var(--md-primary-container);
  color: var(--md-on-primary-container);
  font-size: var(--md-label-small);
  font-weight: 700;
  border-radius: var(--md-radius-full);
  margin-right: 0.5rem;
}
</style>
