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
  // AI 长卷限宽约 70ch 行长（DESIGN 正文行长 65–75ch），用户对话保持 max-w-[75%] 靠右对齐
  const baseClass = `${isAI ? 'w-full max-w-[70ch]' : 'max-w-[75%]'} p-4 fade-in`
  const typeClass = isAI ? 'chat-bubble-ai' : 'chat-bubble-user'
  return `${baseClass} ${typeClass}`
})
</script>

<style scoped>
/* 「手撕毛边宣纸」聊天气泡：灵感模式气泡样式的唯一真相源，
   全局 brand-visuals.css / misc-base.css 的覆写段落已删除，故不再需要 !important 互搏。
   仅 font-family 保留 !important，以抵御全局 annotation.css 对 .chat-bubble-ai 的楷体覆写。 */

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
  box-shadow: 1px 1px 0px color-mix(in srgb, var(--md-secondary) 15%, transparent); /* 微印章硬影 */
}

/* 「手撕毛边宣纸」 AI 气泡 */
.chat-bubble-ai {
  background-color: var(--md-surface);
  color: var(--md-on-surface);
  /* 精细的多边形剪裁模拟参差不齐的手撕宣纸毛边 */
  clip-path: polygon(
    0% 2%, 8% 0.5%, 19% 1.5%, 31% 0.5%, 44% 1.8%, 56% 0.8%, 69% 1.5%, 81% 0.5%, 93% 1.8%, 100% 2%, 
    99.2% 15%, 100% 32%, 98.8% 48%, 99.5% 65%, 98.5% 82%, 99.2% 98%, 
    91% 99.2%, 79% 98.2%, 66% 99.2%, 54% 98.5%, 41% 99.2%, 29% 98.2%, 16% 99.2%, 0% 98%,
    0.8% 81%, 0% 63%, 1.2% 46%, 0% 28%, 0.8% 12%
  );
  padding: 1.25rem 2rem 1.25rem 1.5rem;
  border: none;
  box-shadow: none;
  /* 搭配 drop-shadow 滤镜产生形状完美的硬偏置拓片影（明暗主题自适应） */
  filter: drop-shadow(3px 3px 0px color-mix(in srgb, var(--md-on-surface) 12%, transparent));
  /* 显式声明 will-change，提前提升图层防止高频重绘卡顿 */
  will-change: filter, transform;
  /* 字体使用清隽宋体（保留 !important 抵御全局 annotation.css 的楷体覆写） */
  font-family: var(--md-font-serif) !important;
  font-size: 15px;
  line-height: 1.6;
  letter-spacing: 0.03em;
  position: relative;
  animation: ink-fade-in 0.8s cubic-bezier(0.22, 1, 0.36, 1) forwards;
}

/* 段落内超链接：焦墨虚线下划线，hover 焦墨化实（不落朱砂） */
:deep(.prose a) {
  color: var(--md-primary-dark);
  text-decoration: none;
  border-bottom: 1px dashed var(--md-primary);
  transition:
    color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.25s cubic-bezier(0.22, 1, 0.36, 1);
  padding-bottom: 1px;
}

:deep(.prose a:hover) {
  color: var(--md-primary);
  border-bottom: 1px solid var(--md-primary);
}

/* 夹批朱印方章，金石点睛（适度内缩，避让 clip-path 毛边剪裁区） */
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
  box-shadow: 0.5px 0.5px 0px color-mix(in srgb, var(--md-secondary) 15%, transparent);
}

/* 焦墨手书用户气泡 */
.chat-bubble-user {
  background-color: var(--md-primary); /* 焦墨底色 */
  color: var(--md-on-primary);
  border-radius: var(--md-radius-xs); /* 方直微圆角 */
  padding: 0.85rem 1.25rem;
  border: 1px solid var(--md-outline);
  /* 朱砂小落款右下硬影（明暗主题自适应） */
  box-shadow: 3px 3px 0px color-mix(in srgb, var(--md-secondary) 22%, transparent);
  font-family: var(--md-font-kai);
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
