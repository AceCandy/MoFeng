<template>
  <article class="chapter-console__preview-card">
    <header>
      <h4>实时草稿预览</h4>
      <span>{{ previewModeLabel }}</span>
    </header>

    <!-- 描红稿纸舞台（仅生成中亮台）：横向行线只铺在本容器内（行线不出稿纸）；
         预览文字三信号齐备（淡朱色 + 真楷体 + wash 底与左缘 1px 界栏 + data-provenance="ai"），
         段落随进度渐次浮现；完成/待确认/回溯时舞台安静退场为静态预览 -->
    <div
      v-if="previewParagraphs.length > 0"
      class="chapter-console__preview-body"
      :class="{ 'is-grinding': isGenerating }"
      :data-provenance="isGenerating ? 'ai' : undefined"
    >
      <p
        v-for="(paragraph, index) in previewParagraphs"
        :key="`preview-${index}`"
        class="chapter-console__draft-paragraph"
        :class="{ 'is-streaming': index === previewParagraphs.length - 1 }"
        :style="{ animationDelay: `${index * 100}ms` }"
      >
        {{ paragraph }}
        <span
          v-if="isGenerating && index === previewParagraphs.length - 1"
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
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  chapterContentPreview?: string | null
  /** 工作流是否活跃推进中：进行中段落渐次浮现 + 流光标，完成后静态落定 */
  isGenerating?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  chapterContentPreview: '',
  isGenerating: false,
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
</script>

<style scoped>
/* 卡片骨架：源自 ChapterGenerating 与其余 card 共享的 border/radius/bg/shadow/padding/h4，
   scoped 隔离下父组件选择器不再作用于本组件元素，故在此重复声明 */
.chapter-console__preview-card {
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-sm);
  background: color-mix(in srgb, var(--md-surface) 96%, transparent);
  box-shadow: var(--md-elevation-paper-1); /* 浮起纸影 */
  padding: var(--md-spacing-4);
}

.chapter-console__preview-card h4 {
  margin: 0;
  color: var(--md-on-surface);
  font-size: var(--md-title-medium);
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

/* 研墨舞台亮台（仅生成中）：横向描红行线 + 左右朱丝栏 + 熟宣底，行线只在本容器内 */
.chapter-console__preview-body.is-grinding {
  --paper-line: 27px; /* 稿纸行线节奏，同 chapter-paper 行笺 */
  padding: var(--md-spacing-3) var(--md-spacing-4);
  background:
    /* 左右朱丝栏竖线（各 1px 描红边栏，贴容器左右缘） */
    linear-gradient(to bottom, var(--md-miaohong-line-strong), var(--md-miaohong-line-strong)) left top / 1px 100% no-repeat local,
    linear-gradient(to bottom, var(--md-miaohong-line-strong), var(--md-miaohong-line-strong)) right top / 1px 100% no-repeat local,
    /* 横向描红行线底，--paper-line 循环 */
    repeating-linear-gradient(
      to bottom,
      transparent 0,
      transparent calc(var(--paper-line) - 1px),
      var(--md-miaohong-line) calc(var(--paper-line) - 1px),
      var(--md-miaohong-line) var(--paper-line)
    ) local,
    linear-gradient(var(--md-surface), var(--md-surface));
  background-attachment: local;
}

/* 生成中预览段落 = AI 描红稿三信号（缺一不可）：淡朱色 + 真楷体 + wash 底与左缘 1px 界栏；
   15px × 1.8 = 27px，与稿纸行线同节奏防相位漂移 */
.chapter-console__preview-body.is-grinding .chapter-console__draft-paragraph {
  color: var(--md-miaohong);
  font-family: var(--md-font-kai);
  font-size: var(--md-body-large);
  line-height: 1.8;
  background-color: var(--md-miaohong-wash);
  border-left: 1px solid var(--md-miaohong-line-strong);
  padding: 0 var(--md-spacing-2);
  /* 段落随生成进度渐次浮现：opacity 0→1 + 微量 translateY，stagger 由各行 animation-delay 级进 */
  animation: chapter-draft-emerge var(--md-duration-medium) var(--md-easing-standard) both;
}

.chapter-console__preview-body p.is-streaming {
  color: color-mix(in srgb, var(--md-on-surface) 92%, var(--md-primary-dark));
}

/* 正在生成的一段：描红加深一档，示“笔在此处” */
.chapter-console__preview-body.is-grinding p.is-streaming {
  color: var(--md-miaohong-strong);
}

.chapter-console__cursor {
  margin-left: 2px;
  color: var(--md-miaohong-strong);
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

/* 描红段落渐次浮现：仅 opacity + 微量 translateY */
@keyframes chapter-draft-emerge {
  from {
    opacity: 0;
    transform: translateY(4px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .chapter-console__cursor {
    animation: none;
  }

  /* 描红段落直落终态：静态稿纸，无浮现动效 */
  .chapter-console__preview-body.is-grinding .chapter-console__draft-paragraph {
    animation: none;
  }
}
</style>
