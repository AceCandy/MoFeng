<!-- AIMETA P=写作台_AI助手侧栏|R=章节建议_快捷操作|NR=不含正文编辑|E=component:WDAssistantPanel|X=ui|A=侧栏组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <aside class="wd-ai" aria-label="AI 编辑助手">
    <div class="wd-ai__panel">
      <template v-if="isCompletedChapter">
        <section class="wd-ai__real-summary-shell" aria-label="章节实际内容梳理">
          <div
            v-if="realSummaryBlocks.length"
            class="wd-ai__real-summary-blocks"
          >
            <article
              v-for="block in realSummaryBlocks"
              :key="block.id"
              class="wd-ai__real-summary-card"
            >
              <h3 v-if="block.title">{{ block.title }}</h3>
              <div
                v-if="block.html"
                class="wd-ai__real-summary-body"
                v-html="block.html"
              ></div>
            </article>
          </div>
          <p v-else class="wd-ai__paragraph">
            本章已完成，等待系统补齐章节梳理。
          </p>
        </section>
      </template>

      <template v-else>
        <section class="wd-ai__section">
          <header class="wd-ai__head">
            <p>本章目标</p>
            <strong>{{ chapterGoal }}</strong>
          </header>
        </section>

        <section class="wd-ai__section">
          <header class="wd-ai__head">
            <p>情绪基调</p>
            <strong>{{ emotionTone }}</strong>
          </header>
        </section>

        <section class="wd-ai__section">
          <header class="wd-ai__head">
            <p>重点人物</p>
            <strong>{{ keyCharacters }}</strong>
          </header>
        </section>

        <section class="wd-ai__section">
          <header class="wd-ai__head">
            <p>伏笔提醒</p>
          </header>
          <p class="wd-ai__paragraph">{{ foreshadowingReminder }}</p>
        </section>

        <section class="wd-ai__section">
          <header class="wd-ai__head">
            <p>风险提醒</p>
          </header>
          <ul class="wd-ai__risk-list">
            <li v-for="item in risks" :key="item">{{ item }}</li>
          </ul>
        </section>

        <section class="wd-ai__section">
          <header class="wd-ai__head">
            <p>项目态势</p>
            <strong>{{ projectStatus }}</strong>
          </header>
          <div class="wd-ai__project-stats">
            <div>
              <span>已完成章节</span>
              <strong>{{ completedChapters }} / {{ totalChapters }}</strong>
            </div>
            <div>
              <span>待推进章节</span>
              <strong>{{ pendingChapters }}</strong>
            </div>
            <div>
              <span>当前阶段</span>
              <strong>{{ projectStage }}</strong>
            </div>
          </div>
        </section>
      </template>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Chapter, ChapterOutline, NovelProject } from '@/api/novel'
import DOMPurify from 'dompurify'
import { marked } from 'marked'

interface Props {
  project: NovelProject | null
  selectedChapterNumber: number | null
  selectedChapter: Chapter | null
  selectedChapterOutline: ChapterOutline | null
}

const props = defineProps<Props>()

const completedChapters = computed(() => {
  return (
    props.project?.chapters?.filter((chapter) => chapter.generation_status === 'successful').length ||
    0
  )
})

const totalChapters = computed(() => {
  return props.project?.blueprint?.chapter_outline?.length || 0
})

const pendingChapters = computed(() => Math.max(totalChapters.value - completedChapters.value, 0))

const projectStage = computed(() => {
  if (!props.project) return '项目加载中'
  if (totalChapters.value > 0 && completedChapters.value >= totalChapters.value) return '完稿收束'
  if (completedChapters.value > 0) return '持续创作中'
  return '蓝图筹备中'
})

const projectStatus = computed(() => {
  if (!props.project) return '未就绪'
  if (completedChapters.value === 0) return '创作准备阶段'
  if (pendingChapters.value > 0) return '长篇推进阶段'
  return '成稿整理阶段'
})

const isCompletedChapter = computed(() => {
  return props.selectedChapter?.generation_status === 'successful'
})

const realSummary = computed(() => {
  return props.selectedChapter?.real_summary?.trim() || ''
})

const cleanSummaryText = (text: string) =>
  text
    .replace(/\\n/g, '\n')
    .replace(/\\"/g, '"')
    .replace(/\\'/g, "'")
    .replace(/\\\\/g, '\\')
    .trim()

const renderMarkdown = (text: string): string => {
  try {
    const parsed = marked.parse(text, { breaks: true }) as string
    return DOMPurify.sanitize(parsed, {
      USE_PROFILES: { html: true },
    })
  } catch (error) {
    console.error('解析章节梳理失败:', error)
    return DOMPurify.sanitize(text, {
      USE_PROFILES: { html: true },
    })
  }
}

const cleanTitle = (title: string): string => {
  if (!title) return ''
  return title
    // 去除 1. 2、 一、 二. 等
    .replace(/^\s*([一二三四五六七八九十百]+|[\d]+)[\s.、:-]*/, '')
    // 去除 【1】 【一】
    .replace(/^\s*【([一二三四五六七八九十百]+|[\d]+)】\s*/, '')
    // 去除 "第X章" / "第X个"
    .replace(/^\s*第[一二三四五六七八九十百\d]+[章节个部分回][\s.、:-]*/, '')
    .trim()
}

const realSummaryBlocks = computed(() => {
  const text = cleanSummaryText(realSummary.value)
  if (!text) return []

  const lines = text.split(/\r?\n/)
  const hasHeadings = lines.some((line) => /^\s{0,3}#{1,4}\s+/.test(line))

  if (!hasHeadings) {
    return text
      .split(/\n{2,}/)
      .map((content) => content.trim())
      .filter(Boolean)
      .map((content, index) => ({
        id: `summary-block-${index}`,
        title: '',
        html: renderMarkdown(content),
      }))
  }

  const blocks: Array<{ id: string; title: string; html: string }> = []
  let currentTitle = ''
  let buffer: string[] = []

  const pushBlock = () => {
    const content = buffer.join('\n').trim()
    if (!currentTitle && !content) return
    blocks.push({
      id: `summary-block-${blocks.length}`,
      title: cleanTitle(currentTitle),
      html: content ? renderMarkdown(content) : '',
    })
  }

  for (const line of lines) {
    const heading = line.match(/^\s{0,3}#{1,4}\s+(.+?)\s*#*\s*$/)
    if (heading) {
      pushBlock()
      currentTitle = heading[1].trim()
      buffer = []
      continue
    }
    buffer.push(line)
  }

  pushBlock()
  return blocks
})

const chapterGoal = computed(() => {
  if (props.selectedChapterNumber === 76) {
    return '让林烬第一次意识到十万次死亡不是终点，而是旧系统留下的触发阈值。'
  }
  return '推动主线冲突，并让本章结尾为下一章留下明确推进抓手。'
})

const emotionTone = computed(() => {
  if (props.selectedChapterNumber === 76) {
    return '压迫、临界、疑惑、爆发前夜'
  }
  return '压迫、推进、悬念递增'
})

const keyCharacters = computed(() => {
  if (props.selectedChapterNumber === 76) {
    return '林烬、白芷、沈无渊、旧系统'
  }

  const names = props.project?.blueprint?.characters?.slice(0, 4).map((item) => item.name) || []
  if (names.length > 0) {
    return names.join('、')
  }
  return '待补充'
})

const foreshadowingReminder = computed(() => {
  if (props.selectedChapterNumber === 76) {
    return '第12章的灰色计数、第43章的服务器异常提示、第61章的白芷记忆残留需要在本章产生呼应。'
  }
  return '请在本章至少推进一条旧伏笔状态，避免出现纯气氛段落。'
})

const risks = computed(() => {
  if (props.selectedChapterNumber === 76) {
    return [
      '不要重复解释死亡计数的基础规则。',
      '白芷的记忆残留需要保持克制。',
      '本章应该推进主线，而不是只做氛围铺垫。',
    ]
  }

  return [
    '避免重复交代已知设定，优先推动新信息。',
    '确保关键角色行为与前文章节一致。',
    '章节结尾必须留出下章可执行目标。',
  ]
})
</script>

<style scoped>
/* ============================================
   墨风古典辅助面板样式（古籍笺纸单页）
   ============================================ */
.wd-ai {
  min-width: 0;
  height: 100%;
}

/* 恢复外部边框：采用与整体框架完美呼应的淡墨单线边框，平整熟宣大底 */
.wd-ai__panel {
  height: 100%;
  overflow-y: auto;
  border: 1px solid var(--md-outline);
  border-radius: var(--md-radius-sm);
  background-color: var(--md-surface); /* 熟宣纸白底色 */
  box-shadow: var(--md-elevation-1);
  padding: var(--md-spacing-5) var(--md-spacing-5);
}

/* 优雅的细微滚动条 */
.wd-ai__panel::-webkit-scrollbar {
  width: 5px;
}

.wd-ai__panel::-webkit-scrollbar-thumb {
  background-color: var(--md-outline-variant);
  border-radius: var(--md-radius-full);
}

/* ============================================
   未完成章节 - 写作案头参数模块 (平铺信笺乌丝栏，常驻稳重无 Hover)
   ============================================ */
.wd-ai__section {
  padding: 0 0 var(--md-spacing-5) 0;
  margin-bottom: var(--md-spacing-5);
  border: none;
  border-bottom: 1px dashed color-mix(in srgb, var(--md-outline) 50%, transparent); /* 淡墨虚线栏线分割 */
  background-color: transparent; /* 融入大底 */
  border-radius: 0;
}

.wd-ai__section:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.wd-ai__head p,
.wd-ai__head strong {
  margin: 0;
}

/* 小标题升级为“常驻朱砂题签”：左侧朱批细线，微红浅玉沙笺底色，醒目优雅 */
.wd-ai__head p {
  color: var(--md-primary); /* 焦墨 */
  font-family: var(--md-font-kai); /* 古雅楷体 */
  font-size: var(--md-label-large);
  font-weight: 700 !important;
  letter-spacing: 0.06em;
  display: flex;
  align-items: center;
  padding: var(--md-spacing-2) var(--md-spacing-3);
  background-color: color-mix(in srgb, var(--md-secondary) 6%, var(--md-surface-dim)); /* 微红题签底色 */
  border-left: 3px solid var(--md-secondary); /* 左侧朱砂描红题签线 */
  border-radius: var(--md-radius-xs);
  margin-bottom: var(--md-spacing-3);
}

.wd-ai__head strong {
  margin-top: 8px;
  display: block;
  color: var(--md-primary); /* 焦墨 */
  font-family: var(--md-font-serif);
  font-size: var(--md-body-large);
  line-height: 1.65;
  letter-spacing: 0.02em;
}

.wd-ai__paragraph {
  margin: var(--md-spacing-3) 0 0;
  color: var(--md-on-surface-variant);
  font-family: var(--md-font-serif);
  font-size: var(--md-body-medium);
  line-height: 1.8;
  letter-spacing: 0.01em;
}

/* 列表符号 */
.wd-ai__risk-list {
  margin: var(--md-spacing-3) 0 0;
  padding: 0;
  list-style-type: none;
}

.wd-ai__risk-list li {
  position: relative;
  padding-left: 14px;
  color: var(--md-on-surface-variant);
  font-family: var(--md-font-serif);
  font-size: var(--md-body-medium);
  line-height: 1.8;
}

.wd-ai__risk-list li::before {
  content: '※';
  position: absolute;
  left: 0;
  color: var(--md-secondary); /* 常驻朱砂警示符 */
  font-size: 11px;
  top: 1px;
}

.wd-ai__risk-list li + li {
  margin-top: var(--md-spacing-2);
}

/* ============================================
   已完成章节 - 章节实际内容梳理（平铺书页分割，常驻稳重无 Hover）
   ============================================ */
.wd-ai__real-summary-shell {
  min-height: 100%;
  padding: 0;
  background: transparent;
}

.wd-ai__real-summary-blocks {
  display: grid;
  gap: 0;
}

/* 纯净书页排版，带常驻淡墨虚线栏线 */
.wd-ai__real-summary-card {
  padding: 0 0 var(--md-spacing-5) 0;
  margin-bottom: var(--md-spacing-5);
  border: none;
  border-bottom: 1px dashed color-mix(in srgb, var(--md-outline) 50%, transparent);
  background-color: transparent;
  border-radius: 0;
  box-shadow: none;
}

.wd-ai__real-summary-card:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

/* 模块标题升级为“常驻朱砂题签”：带极淡红玉沙底色与朱砂红左侧题签线，极度明显且国风韵味十足 */
.wd-ai__real-summary-card h3 {
  margin: 0 0 var(--md-spacing-4) 0;
  padding: var(--md-spacing-2) var(--md-spacing-3);
  color: var(--md-primary); /* 焦墨 */
  font-family: var(--md-font-kai); /* 古雅楷体 */
  font-size: var(--md-title-medium);
  line-height: 1.5;
  letter-spacing: 0.06em;
  font-weight: 700 !important;
  display: flex;
  align-items: center;
  background-color: color-mix(in srgb, var(--md-secondary) 6%, var(--md-surface-dim)); /* 题签微红浅底 */
  border-left: 3px solid var(--md-secondary); /* 左侧朱砂题签侧线 */
  border-radius: var(--md-radius-xs);
}

.wd-ai__real-summary-body {
  color: var(--md-on-surface);
  font-family: var(--md-font-serif);
  font-size: var(--md-body-medium);
  line-height: 1.85;
  letter-spacing: 0.01em;
}

.wd-ai__real-summary-body :deep(p) {
  margin: 0 0 var(--md-spacing-3);
}

.wd-ai__real-summary-body :deep(p:last-child) {
  margin-bottom: 0;
}

/* 朱砂双色套印手抄朱批：正文加粗 strong 常驻朱砂红楷书，视觉特色拉满 */
.wd-ai__real-summary-body :deep(strong) {
  color: var(--md-secondary) !important;
  font-family: var(--md-font-kai) !important;
  font-weight: 700 !important;
  letter-spacing: 0.02em;
  padding: 0 1px;
}

/* 优雅的朱砂点列表 */
.wd-ai__real-summary-body :deep(ul) {
  list-style-type: none;
  padding-left: 0;
  margin: var(--md-spacing-2) 0 var(--md-spacing-3);
}

.wd-ai__real-summary-body :deep(li) {
  position: relative;
  padding-left: 14px;
  color: var(--md-on-surface-variant);
  line-height: 1.8;
}

.wd-ai__real-summary-body :deep(li::before) {
  content: '·';
  position: absolute;
  left: 0;
  color: var(--md-secondary); /* 常驻朱红批注点 */
  font-weight: bold;
  font-size: 1.4em;
  line-height: 1;
  top: -2px;
}

.wd-ai__real-summary-body :deep(li + li) {
  margin-top: var(--md-spacing-1);
}

/* ============================================
   项目全局统计栏 (平铺信笺分割)
   ============================================ */
.wd-ai__project-stats {
  margin-top: var(--md-spacing-4);
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--md-spacing-3);
}

.wd-ai__project-stats div {
  border: none;
  border-bottom: 1px dashed color-mix(in srgb, var(--md-outline) 50%, transparent);
  border-radius: 0;
  background-color: transparent;
  padding: 0 0 var(--md-spacing-3) 0;
  box-shadow: none;
}

.wd-ai__project-stats div:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.wd-ai__project-stats span {
  display: block;
  color: var(--md-secondary); /* 常驻朱砂 */
  font-family: var(--md-font-display);
  font-size: var(--md-label-small);
  font-weight: 600;
  letter-spacing: 0.03em;
}

.wd-ai__project-stats strong {
  display: block;
  margin-top: 6px;
  color: var(--md-primary);
  font-family: var(--md-font-serif);
  font-size: var(--md-body-large);
  letter-spacing: 0.02em;
}
</style>
