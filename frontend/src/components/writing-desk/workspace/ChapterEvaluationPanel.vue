<!-- AIMETA P=章节评审反馈面板_多版本评阅展示|R=评审展示_呼叫评阅|NR=不含评审触发逻辑|E=component:ChapterEvaluationPanel|X=internal|A=评审面板|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="writing-workspace__evaluation-panel flex flex-col h-full overflow-y-auto">
    <div v-if="evaluation" class="space-y-6">
      <!-- 情况 A：解析 JSON 成功 -->
      <template v-if="parsedEvaluation">
        <!-- 格式 1: 含有 best_choice 或 evaluation 的多版本评阅 -->
        <div v-if="parsedEvaluation.best_choice || parsedEvaluation.evaluation" class="space-y-6">
          <div v-if="parsedEvaluation.best_choice" class="md-card md-card-filled p-4 m3-eval-best-choice-card">
            <p class="md-title-small font-semibold m3-eval-best-choice-title">🏆 最佳推荐：版本 {{ parsedEvaluation.best_choice }}</p>
            <p class="md-body-small mt-2 m3-eval-best-choice-reason" style="color: var(--md-on-surface)">
              {{ parsedEvaluation.reason_for_choice }}
            </p>
          </div>
          <div class="space-y-4">
            <div v-for="item in sortedEvaluationEntries" :key="item.key" class="md-card md-card-outlined p-4 m3-eval-version-card" style="border: 1px solid var(--md-outline); background: var(--md-surface-container-low)">
              <h5 class="md-title-medium font-semibold mb-2" style="font-family: var(--md-font-serif); color: var(--md-secondary)">
                版本 {{ item.versionNumber }} 评估
              </h5>
              <div class="prose prose-sm max-w-none md-on-surface space-y-3">
                <div v-if="item.result.overall_review">
                  <p class="font-semibold" style="color: var(--md-on-surface)">综合评价:</p>
                  <p style="color: var(--md-on-surface-variant)">{{ item.result.overall_review }}</p>
                </div>
                <div v-if="item.result.pros && item.result.pros.length">
                  <p class="font-semibold" style="color: var(--md-on-surface)">优点:</p>
                  <ul class="list-disc pl-5 space-y-1" style="color: var(--md-on-surface-variant)">
                    <li v-for="(pro, i) in item.result.pros" :key="`pro-${i}`">{{ pro }}</li>
                  </ul>
                </div>
                <div v-if="item.result.cons && item.result.cons.length">
                  <p class="font-semibold" style="color: var(--md-on-surface)">缺点:</p>
                  <ul class="list-disc pl-5 space-y-1" style="color: var(--md-on-surface-variant)">
                    <li v-for="(con, i) in item.result.cons" :key="`con-${i}`">{{ con }}</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 格式 2: 含有 scores 或 feedback/decision 的评分评阅 -->
        <div v-else-if="parsedEvaluation.scores || parsedEvaluation.feedback || parsedEvaluation.decision" class="space-y-6">
          <div v-if="parsedEvaluation.decision" class="md-card md-card-filled p-4 m3-eval-best-choice-card">
            <p class="md-title-small font-semibold m3-eval-best-choice-title">⚖️ 评阅大案决策</p>
            <p class="md-body-small mt-2" style="color: var(--md-on-surface)">{{ parsedEvaluation.decision }}</p>
          </div>

          <div v-if="parsedEvaluation.scores" class="grid grid-cols-2 md:grid-cols-3 gap-4">
            <div v-for="(score, key) in parsedEvaluation.scores" :key="key" class="writing-workspace__evaluation-card p-4" style="border: 1px solid var(--md-outline); background: var(--md-surface-container-low)">
              <h5 class="dimension-title" style="font-family: var(--md-font-serif); font-weight: bold; color: var(--md-secondary)">
                <span class="dimension-mark">✒️</span> {{ key }}
              </h5>
              <p class="dimension-desc md-display-small font-semibold mt-2" style="color: var(--md-primary)">
                {{ score }} <span class="text-sm font-normal text-muted" style="color: var(--md-on-surface-variant)">分</span>
              </p>
            </div>
          </div>

          <div v-if="parsedEvaluation.feedback" class="writing-workspace__evaluation-card is-suggestion-card p-4" style="border: 1px solid var(--md-outline); background: var(--md-surface-container-low)">
            <h5 class="dimension-title is-suggestion" style="font-family: var(--md-font-serif); font-weight: bold; color: var(--md-secondary)">
              <span class="dimension-mark">💡</span> 评阅意见反馈
            </h5>
            <div class="prose prose-sm max-w-none mt-2 whitespace-pre-wrap" style="color: var(--md-on-surface-variant)" v-html="parseMarkdown(parsedEvaluation.feedback)"></div>
          </div>
        </div>

        <!-- 格式 3: 原作者脑补的 summary / dimensions / suggestions 格式 -->
        <div v-else class="space-y-6">
          <!-- 评审大字号金石综合评价 -->
          <div v-if="parsedEvaluation.summary" class="writing-workspace__evaluation-hero">
            <div class="hero-seal">
              <span>評</span>
            </div>
            <div class="hero-text">
              <h4>本章综合评阅报告</h4>
              <p class="md-body-medium">
                {{ parsedEvaluation.summary }}
              </p>
            </div>
          </div>

          <!-- 各项维度细分卡片 -->
          <div v-if="parsedEvaluation.dimensions" class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div
              v-for="(item, key) in parsedEvaluation.dimensions"
              :key="key"
              class="writing-workspace__evaluation-card"
            >
              <h5 class="dimension-title">
                <span class="dimension-mark">✒️</span>
                {{ key }}
              </h5>
              <p class="dimension-desc md-body-small">
                {{ item.analysis || item }}
              </p>
            </div>
          </div>

          <!-- 优化改进建议 -->
          <div v-if="parsedEvaluation.suggestions" class="writing-workspace__evaluation-card is-suggestion-card">
            <h5 class="dimension-title is-suggestion">
              <span class="dimension-mark">💡</span>
              大案改进意见
            </h5>
            <ul class="suggestion-list">
              <li v-for="(suggestion, sIdx) in parsedEvaluation.suggestions" :key="sIdx">
                {{ suggestion }}
              </li>
            </ul>
          </div>
        </div>
      </template>

      <!-- 情况 B：解析 JSON 失败，直接作为 Markdown/文本渲染 -->
      <div v-else class="prose prose-sm max-w-none md-on-surface p-6 m3-eval-markdown-container rounded-sm" style="border: 1px dashed var(--md-outline); background: var(--md-surface-container-low)" v-html="parseMarkdown(evaluation)"></div>
    </div>
    <div v-else class="h-full flex flex-col justify-center items-center py-12">
      <div class="text-center space-y-4 max-w-sm">
        <span class="text-4xl">⚖️</span>
        <h4 class="md-title-large font-semibold">尚无本章评阅报告</h4>
        <p class="md-body-medium md-on-surface-variant">
          阁主可呼叫 AI 评阅官，对当前已完成的章节正文进行全方位结构、文笔和剧情连贯性评阅。
        </p>
        <button
          type="button"
          class="md-btn md-btn-filled md-ripple"
          style="background-color: var(--md-secondary); color: var(--md-on-secondary)"
          :disabled="evaluatingChapter !== null"
          @click="$emit('evaluateChapter')"
        >
          <span>{{ evaluatingChapter !== null ? '正在分析评审中...' : '呼叫 AI 评阅官' }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import DOMPurify from 'dompurify'
import { marked } from 'marked'

interface Props {
  evaluation: string | null | undefined
  evaluatingChapter: number | null
}

const props = defineProps<Props>()

defineEmits(['evaluateChapter'])

const parsedEvaluation = computed(() => {
  const evalStr = props.evaluation
  if (!evalStr) return null
  try {
    let data = JSON.parse(evalStr)
    if (typeof data === 'string') {
      data = JSON.parse(data)
    }
    return data
  } catch (error) {
    console.error('Failed to parse evaluation JSON in ChapterEvaluationPanel:', error)
    return null
  }
})

const getEvaluationVersionNumber = (versionKey: string | number): number => {
  const normalizedKey = String(versionKey)
  const match = normalizedKey.match(/\d+/)
  return match ? Number.parseInt(match[0], 10) : 0
}

const sortedEvaluationEntries = computed(() => {
  const evaluation = parsedEvaluation.value?.evaluation
  if (!evaluation || typeof evaluation !== 'object' || Array.isArray(evaluation)) {
    return []
  }

  // 多版本编号必须和候选版本数组一致：version1 对应 availableVersions[0]。
  return Object.entries(evaluation)
    .map(([key, result]) => ({
      key,
      result: result as Record<string, any>,
      versionNumber: getEvaluationVersionNumber(key),
    }))
    .sort((a, b) => a.versionNumber - b.versionNumber)
})

const parseMarkdown = (text: string | null | undefined): string => {
  if (!text) return ''
  try {
    let cleaned = text
      .replace(/\\n/g, '\n')
      .replace(/\\"/g, '"')
      .replace(/\\'/g, "'")
      .replace(/\\\\/g, '\\')

    let parsed = ''
    if (marked && typeof marked.parse === 'function') {
      parsed = marked.parse(cleaned, { breaks: true }) as string
    } else if (typeof marked === 'function') {
      parsed = (marked as any)(cleaned, { breaks: true }) as string
    } else {
      parsed = cleaned
    }

    return DOMPurify.sanitize(parsed, {
      USE_PROFILES: { html: true },
    })
  } catch (error) {
    console.error('Failed to parse Markdown in ChapterEvaluationPanel:', error)
    return DOMPurify.sanitize(text, {
      USE_PROFILES: { html: true },
    })
  }
}
</script>

<style scoped>
/* ==========================================================================
   AI 评阅分析面板
   ========================================================================== */
.writing-workspace__evaluation-panel {
  padding-right: var(--md-spacing-2);
  height: 100%;
}

.writing-workspace__evaluation-hero {
  display: flex;
  align-items: flex-start;
  gap: var(--md-spacing-4);
  padding: var(--md-spacing-4);
  border: 3px double var(--md-outline);
  border-radius: var(--md-radius-xs);
  background-color: var(--md-surface-container-low); /* 竹纸底 */
}

.writing-workspace__evaluation-hero .hero-seal {
  width: 38px;
  height: 38px;
  border: 1.5px solid var(--md-secondary);
  border-radius: 50%;
  display: grid;
  place-items: center;
  color: var(--md-secondary);
  font-family: var(--md-font-serif);
  font-size: 16px;
  font-weight: bold;
  background-color: rgba(184, 60, 50, 0.05);
  flex-shrink: 0;
  transform: rotate(-10deg);
  box-shadow: inset 1px 1px 0px rgba(184, 60, 50, 0.2);
}

.writing-workspace__evaluation-hero .hero-text {
  flex: 1;
  min-width: 0;
}

.writing-workspace__evaluation-hero h4 {
  margin: 0 0 6px;
  font-family: var(--md-font-serif);
  font-weight: bold;
  font-size: 16px;
  color: var(--md-primary-dark);
  letter-spacing: 0.05em;
}

.writing-workspace__evaluation-hero p {
  margin: 0;
  color: var(--md-on-surface);
  line-height: 1.6;
}

.writing-workspace__evaluation-card {
  padding: var(--md-spacing-4);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-xs);
  background-color: var(--md-surface);
  transition: border-color 0.2s ease;
}

.writing-workspace__evaluation-card:hover {
  border-color: var(--md-outline);
}

.writing-workspace__evaluation-card .dimension-title {
  margin: 0 0 var(--md-spacing-3);
  font-family: var(--md-font-serif);
  font-weight: 700;
  font-size: 14.5px;
  color: var(--md-primary-dark);
  display: flex;
  align-items: center;
  gap: 6px;
  border-bottom: 1.5px solid var(--md-outline-variant);
  padding-bottom: 4px;
}

.dimension-mark {
  font-size: 14px;
}

.dimension-desc {
  margin: 0;
  color: var(--md-on-surface);
  line-height: 1.6;
  text-justify: inter-character;
}

.writing-workspace__evaluation-card.is-suggestion-card {
  border: 1.5px solid var(--md-outline);
  background-color: var(--md-surface-container-low);
}

.dimension-title.is-suggestion {
  color: var(--md-secondary) !important;
  border-bottom-color: var(--md-outline) !important;
}

.suggestion-list {
  margin: 0;
  padding-left: 20px;
  list-style-type: decimal;
  color: var(--md-on-surface);
  line-height: 1.7;
  font-size: 13.5px;
  font-weight: 500;
}

.suggestion-list li {
  margin-bottom: 8px;
}

.suggestion-list li:last-child {
  margin-bottom: 0;
}
</style>
