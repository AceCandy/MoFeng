<!-- AIMETA P=写作台头部_顶部导航栏|R=导航_操作按钮|NR=不含内容区域|E=component:WDHeader|X=ui|A=头部组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <header class="writing-header flex-shrink-0 z-30">
    <div class="writing-header__inner">
      <div class="writing-header__row">
        <!-- 左侧：项目信息 -->
        <div class="writing-header__project">
          <button
            type="button"
            @click="$emit('goBack')"
            class="md-icon-btn md-ripple writing-header__back"
            aria-label="返回小说档案"
            title="返回小说档案"
          >
            <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path
                fill-rule="evenodd"
                d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L4.414 9H17a1 1 0 110 2H4.414l5.293 5.293a1 1 0 010 1.414z"
                clip-rule="evenodd"
              ></path>
            </svg>
          </button>
          <div class="writing-header__title-block">
            <h1 class="md-title-large font-semibold truncate">
              {{ project?.title || '加载中...' }}
            </h1>
            <div class="writing-header__meta md-body-small md-on-surface-variant">
              <span>{{ project?.blueprint?.genre || '--' }}</span>
              <span aria-hidden="true">•</span>
              <span>{{ progress }}% 完成</span>
              <span aria-hidden="true" class="writing-header__desktop-meta">•</span>
              <span class="writing-header__desktop-meta"
                >{{ completedChapters }}/{{ totalChapters }} 章</span
              >
            </div>
          </div>
        </div>

        <div v-if="showAssistantToggle" class="writing-header__actions">
          <button
            type="button"
            class="md-btn md-btn-outlined md-ripple writing-header__assistant-toggle"
            :aria-pressed="assistantOpen ? 'true' : 'false'"
            @click="$emit('toggleAssistant')"
          >
            {{ assistantButtonLabel }}
          </button>
        </div>
      </div>

      <div
        class="writing-header__progress"
        role="progressbar"
        :aria-valuenow="clampedProgress"
        aria-valuemin="0"
        aria-valuemax="100"
        :aria-label="`写作进度 ${clampedProgress}%`"
      >
        <span :style="{ '--wd-progress-scale': clampedProgressScale }"></span>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { NovelProject } from '@/api/novel'

interface Props {
  project: NovelProject | null
  progress: number
  completedChapters: number
  totalChapters: number
  showAssistantToggle?: boolean
  assistantOpen?: boolean
  assistantDrawerMode?: boolean
}

const props = defineProps<Props>()

defineEmits(['goBack', 'toggleAssistant'])

const clampedProgress = computed(() => Math.max(0, Math.min(100, props.progress || 0)))
const clampedProgressScale = computed(() => clampedProgress.value / 100)
const assistantButtonLabel = computed(() => {
  if (props.assistantDrawerMode) {
    return props.assistantOpen ? '收起辅助' : '辅助信息'
  }
  return props.assistantOpen ? '收起辅助信息' : '显示辅助信息'
})
</script>

<style scoped>
.writing-header {
  display: flex;
  align-items: center;
  min-height: 72px;
  background-color: color-mix(in srgb, var(--md-surface) 94%, var(--md-surface-container-low));
  border-bottom: 1px solid var(--md-outline-variant);
}

.writing-header__inner {
  width: min(100%, 1680px);
  margin: 0 auto;
  padding: var(--md-spacing-3) clamp(var(--md-spacing-4), 2.4vw, var(--md-spacing-8));
}

.writing-header__row {
  display: flex;
  min-height: 48px;
  align-items: center;
  justify-content: space-between;
  gap: var(--md-spacing-4);
}

.writing-header__project {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: var(--md-spacing-3);
}

.writing-header__back {
  flex-shrink: 0;
}

.writing-header__title-block {
  min-width: 0;
}

.writing-header__title-block h1 {
  max-width: min(58vw, 760px);
  margin: 0;
  font-family: var(--md-font-serif);
  letter-spacing: 0.05em;
  line-height: 1.25;
}

.writing-header__meta {
  display: flex;
  align-items: center;
  gap: var(--md-spacing-2);
  margin-top: 2px;
  white-space: nowrap;
}

.writing-header__actions {
  flex-shrink: 0;
}

.writing-header__assistant-toggle {
  min-height: 44px;
  height: 44px;
  border-radius: var(--md-radius-sm);
  padding-inline: 12px;
  font-size: var(--md-label-medium);
  white-space: nowrap;
}

.writing-header__progress {
  height: 4px;
  margin-top: var(--md-spacing-2);
  overflow: hidden;
  border-radius: var(--md-radius-xs);
  background-color: var(--md-surface-container);
}

.writing-header__progress span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background-color: var(--md-primary);
  transform-origin: left center;
  transform: scaleX(var(--wd-progress-scale, 0));
  transition: transform var(--md-duration-medium) var(--md-easing-standard);
  will-change: transform;
}

@media (max-width: 640px) {
  .writing-header {
    min-height: 80px;
  }

  .writing-header__inner {
    padding: var(--md-spacing-3) var(--md-spacing-4);
  }

  .writing-header__row {
    align-items: flex-start;
    gap: var(--md-spacing-3);
  }

  .writing-header__desktop-meta {
    display: none;
  }

  .writing-header__actions {
    margin-left: auto;
  }

  .writing-header__assistant-toggle {
    min-height: 44px;
    height: 44px;
    padding-inline: 10px;
  }

  .writing-header__title-block h1 {
    max-width: calc(100vw - 230px);
    font-size: var(--md-title-medium);
  }

  .writing-header__meta {
    gap: var(--md-spacing-1);
    font-size: var(--md-label-medium);
  }

}

@media (prefers-reduced-motion: reduce) {
  .writing-header__progress span {
    transition: none;
  }
}
</style>
