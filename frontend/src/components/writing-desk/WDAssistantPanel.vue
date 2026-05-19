<!-- AIMETA P=写作台_AI助手侧栏|R=章节建议_快捷操作|NR=不含正文编辑|E=component:WDAssistantPanel|X=ui|A=侧栏组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <aside class="wd-ai" aria-label="AI 编辑助手">
    <div class="wd-ai__panel">
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
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Chapter, ChapterOutline, NovelProject } from '@/api/novel'

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
.wd-ai {
  min-width: 0;
  height: 100%;
}

.wd-ai__panel {
  height: 100%;
  overflow-y: auto;
  border: 1px solid color-mix(in srgb, var(--md-outline-variant) 80%, transparent);
  border-radius: var(--md-radius-xl);
  background-color: color-mix(in srgb, var(--md-surface) 95%, var(--md-surface-container-low));
  box-shadow: 0 2px 8px rgba(38, 47, 61, 0.05);
}

.wd-ai__section {
  padding: var(--md-spacing-4);
  border-bottom: 1px solid color-mix(in srgb, var(--md-outline-variant) 62%, transparent);
}

.wd-ai__section:last-child {
  border-bottom: 0;
}

.wd-ai__head p,
.wd-ai__head strong {
  margin: 0;
}

.wd-ai__head p {
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-small);
}

.wd-ai__head strong {
  margin-top: 6px;
  display: block;
  color: var(--md-on-surface);
  font-size: var(--md-body-large);
  line-height: 1.6;
}

.wd-ai__paragraph {
  margin: var(--md-spacing-3) 0 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
  line-height: 1.7;
}

.wd-ai__risk-list {
  margin: var(--md-spacing-3) 0 0;
  padding: 0 0 0 1.2rem;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
  line-height: 1.7;
}

.wd-ai__risk-list li + li {
  margin-top: 6px;
}

.wd-ai__project-stats {
  margin-top: var(--md-spacing-3);
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--md-spacing-2);
}

.wd-ai__project-stats div {
  border: 1px solid color-mix(in srgb, var(--md-outline-variant) 56%, transparent);
  border-radius: var(--md-radius-md);
  background-color: color-mix(in srgb, var(--md-surface-container-low) 76%, transparent);
  padding: var(--md-spacing-3);
}

.wd-ai__project-stats span {
  display: block;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.wd-ai__project-stats strong {
  display: block;
  margin-top: 5px;
  color: var(--md-on-surface);
  font-size: var(--md-label-large);
}
</style>
