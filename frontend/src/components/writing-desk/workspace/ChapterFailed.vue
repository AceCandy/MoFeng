<!-- AIMETA P=生成失败_生成错误状态|R=错误提示_重试|NR=不含生成逻辑|E=component:ChapterFailed|X=internal|A=错误状态|D=vue|S=dom|RD=./README.ai -->
<template>
  <section class="chapter-failed">
    <article class="chapter-failed__card">
      <div class="chapter-failed__head">
        <div class="chapter-failed__icon-wrap">
          <svg class="chapter-failed__icon" fill="currentColor" viewBox="0 0 20 20">
            <path
              fill-rule="evenodd"
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
              clip-rule="evenodd"
            ></path>
          </svg>
        </div>
        <div>
          <h3>第{{ chapterNumber }}章生成异常</h3>
          <p>{{ failureScenario.title }}</p>
        </div>
      </div>

      <p class="chapter-failed__desc">{{ failureScenario.description }}</p>

      <div class="chapter-failed__actions">
        <button
          type="button"
          @click="$emit('generateChapter', chapterNumber)"
          :disabled="generatingChapter === chapterNumber"
          class="md-btn md-btn-filled md-ripple disabled:opacity-50"
        >
          {{ generatingChapter === chapterNumber ? '重试中...' : '重试生成本章' }}
        </button>
      </div>

      <details class="chapter-failed__detail">
        <summary>查看错误上下文</summary>
        <p>状态：{{ generationStatus }}</p>
        <p>阶段：{{ generationStep || '未知阶段' }}</p>
      </details>
    </article>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { formatChapterGenerationError } from '@/utils/chapter'

interface Props {
  chapterNumber: number
  generatingChapter: number | null
  generationStatus?: string | null
  generationStep?: string | null
}

const props = withDefaults(defineProps<Props>(), {
  generationStatus: 'failed',
  generationStep: '',
})

defineEmits(['generateChapter'])

const failureReason = computed(() => {
  const step = (props.generationStep || '').trim()
  if (!step || /^[a-z_]+(?:\|.*)?$/i.test(step)) {
    return ''
  }
  return formatChapterGenerationError(step)
})

const failureScenario = computed(() => {
  const step = (props.generationStep || '').toLowerCase()

  if (failureReason.value) {
    return {
      title: '已定位错误原因',
      description: failureReason.value,
    }
  }

  if (props.generationStatus === 'evaluation_failed') {
    return {
      title: '质量评审未通过',
      description: '当前草稿在一致性或质量评分上未通过，可以重新生成本章后再评审。',
    }
  }

  if (step.includes('timeout') || step.includes('time_out')) {
    return {
      title: '模型超时',
      description: '模型响应超时，可能是瞬时拥塞或模型负载过高。',
    }
  }

  if (step.includes('context') || step.includes('length') || step.includes('token')) {
    return {
      title: '上下文过长',
      description: '本章输入上下文超出稳定范围，请精简前文摘要后再点击重试。',
    }
  }

  if (step.includes('persist') || step.includes('save')) {
    return {
      title: '保存失败',
      description: '草稿生成后写入版本库失败，请确认当前章节状态后再点击重试生成。',
    }
  }

  return {
    title: '生成流程中断',
    description: '本轮草稿生成未完成，可直接重试本章生成。',
  }
})
</script>

<style scoped>
.chapter-failed {
  min-height: 420px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.chapter-failed__card {
  width: min(100%, 860px);
  border: 1px solid color-mix(in srgb, var(--md-error) 24%, var(--md-outline-variant));
  border-radius: var(--md-radius-xl);
  background: color-mix(in srgb, var(--md-surface) 96%, transparent);
  box-shadow: var(--md-elevation-1);
  padding: var(--md-spacing-5);
}

.chapter-failed__head {
  display: flex;
  align-items: center;
  gap: var(--md-spacing-3);
}

.chapter-failed__icon-wrap {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background-color: var(--md-error-container);
  display: grid;
  place-items: center;
}

.chapter-failed__icon {
  width: 24px;
  height: 24px;
  color: var(--md-error);
}

.chapter-failed__head h3 {
  margin: 0;
  color: var(--md-on-surface);
  font-size: var(--md-title-large);
}

.chapter-failed__head p {
  margin: 5px 0 0;
  color: var(--md-error);
  font-size: var(--md-body-small);
  font-weight: 600;
}

.chapter-failed__desc {
  margin: var(--md-spacing-4) 0 0;
  color: var(--md-on-surface-variant);
  line-height: 1.7;
}

.chapter-failed__actions {
  margin-top: var(--md-spacing-4);
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--md-spacing-2);
}

.chapter-failed__actions .md-btn {
  min-height: 44px;
}

.chapter-failed__detail {
  margin-top: var(--md-spacing-4);
  border-top: 1px solid var(--md-outline-variant);
  padding-top: var(--md-spacing-3);
}

.chapter-failed__detail summary {
  cursor: pointer;
  color: var(--md-primary-dark);
  font-weight: 600;
}

.chapter-failed__detail p {
  margin: 6px 0 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

</style>
