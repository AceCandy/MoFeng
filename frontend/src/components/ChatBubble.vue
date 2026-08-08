<!-- AIMETA P=聊天气泡_对话消息展示|R=消息气泡|NR=不含输入功能|E=component:ChatBubble|X=internal|A=气泡组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div :class="wrapperClass">
    <div :class="bubbleClass" :data-provenance="type === 'ai' ? 'ai' : 'ink'">
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
  // AI 长卷限宽约 70ch 行长（DESIGN 正文行长 65–75ch），用户对话保持 max-w-[75%] 靠右对齐
  const baseClass = `${isAI ? 'w-full max-w-[70ch]' : 'max-w-[75%]'} p-4 fade-in`
  const typeClass = isAI ? 'chat-bubble-ai' : 'chat-bubble-user'
  return `${baseClass} ${typeClass}`
})
</script>

<style scoped>
/* 描红界格气泡：AI=淡朱真楷+wash底+左缘界栏三信号（data-provenance="ai"），
   作家=焦墨宋体落墨（data-provenance="ink"）。灵感模式气泡样式的唯一真相源，
   全局 brand-visuals.css / misc-base.css 的覆写段落已删除，故不再需要 !important 互搏。
   仅 font-family 保留 !important，以抵御全局 annotation.css 对 .chat-bubble-ai 的覆写。 */

/* 选项字头朱砂小方章（由 v-html 注入，须经 :deep 方能命中 scoped 样式） */
:deep(.chat-bubble__option-marker) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.5rem;
  height: 1.5rem;
  background-color: color-mix(in srgb, var(--md-secondary) 8%, transparent); /* 朱砂淡染 */
  color: var(--md-secondary);
  border: 1px solid var(--md-secondary);
  border-radius: var(--md-radius-xs); /* 金石方直印章 */
  font-size: var(--md-label-small);
  font-weight: 700;
  margin-right: 0.5rem;
  box-shadow: none; /* 印面压纸不浮起 */
}

/* 描红稿 AI 气泡：直边稿纸 + 淡朱真楷 + wash 底 + 左缘 1px 界栏（三信号） */
.chat-bubble-ai {
  background-color: var(--md-miaohong-wash);
  color: var(--md-miaohong);
  border: none;
  border-left: 1px solid var(--md-miaohong-line-strong);
  border-radius: var(--md-radius-xs);
  padding: 1.25rem 2rem 1.25rem 1.5rem;
  box-shadow: none; /* 稿面静息无影 */
  /* 字体使用真楷（保留 !important 抵御全局 annotation.css 的覆写；AI 文本即草稿） */
  font-family: var(--md-font-kai) !important;
  font-size: 15px;
  line-height: 1.6;
  letter-spacing: 0.03em;
  position: relative;
  animation: ink-fade-in 0.8s cubic-bezier(0.22, 1, 0.36, 1) forwards;
}

/* 段落内超链接：描红系虚线下划线，hover 加深（AI 文本不出权责色之外） */
:deep(.prose a) {
  color: var(--md-miaohong-strong);
  text-decoration: none;
  border-bottom: 1px dashed var(--md-miaohong-line-strong);
  transition:
    color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.25s cubic-bezier(0.22, 1, 0.36, 1);
  padding-bottom: 1px;
}

:deep(.prose a:hover) {
  color: var(--md-miaohong-strong);
  border-bottom: 1px solid var(--md-miaohong-strong);
}

/* 夹批朱印方章，金石点睛 */
.chat-bubble-ai::before {
  content: '文';
  position: absolute;
  right: 24px;
  top: 16px;
  font-family: var(--md-font-serif);
  font-size: 9px;
  font-weight: bold;
  color: color-mix(in srgb, var(--md-secondary) 30%, transparent);
  border: 1px solid color-mix(in srgb, var(--md-secondary) 30%, transparent);
  border-radius: 2px; /* 方形朱砂微印章 */
  width: 14px;
  height: 14px;
  display: grid;
  place-items: center;
  line-height: 1;
  box-shadow: none; /* 印面压纸不浮起 */
}

/* 焦墨落墨用户气泡：作家文本=焦墨宋体（data-provenance="ink"） */
.chat-bubble-user {
  background-color: var(--md-primary); /* 焦墨底色 */
  color: var(--md-on-primary);
  border-radius: var(--md-radius-xs); /* 方直微圆角 */
  padding: 0.85rem 1.25rem;
  border: 1px solid var(--md-outline);
  box-shadow: none; /* 落墨静息无影 */
  font-family: var(--md-font-serif);
  font-size: 15px;
  letter-spacing: 0.02em;
  animation: ink-fade-in 0.8s cubic-bezier(0.22, 1, 0.36, 1) forwards;
}

/* 发送失败态：丹砂虚线框 + 丹砂文字，语义与朱砂落款区分（供父级标记失败消息时启用） */
.chat-bubble--failed {
  border: 1px dashed var(--md-error);
  box-shadow: none;
  color: var(--md-error-text);
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
