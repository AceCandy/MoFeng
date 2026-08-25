<!-- AIMETA P=章节正文工具栏_编辑AI优化与更多操作|R=已提交正文的非工作流操作|NR=不提交选版定稿或生命周期命令|E=component:ChapterToolbar|X=internal|A=章节操作工具栏|D=vue|S=dom|RD=./README.ai -->
<template>
  <aside
    v-if="isFinalizedSuccessful"
    class="writing-workspace__toolbar"
    role="toolbar"
    aria-label="章节操作"
  >
    <button
      type="button"
      class="md-btn md-btn-text md-ripple writing-workspace__tool-btn writing-workspace__tool-btn--edit"
      :disabled="!hasSelectedChapterContent"
      @click="emit('openEditModal')"
    >
      编辑
    </button>

    <div ref="aiMenuRef" class="writing-workspace__ai-menu">
      <button
        ref="aiMenuTriggerRef"
        type="button"
        class="md-btn md-btn-tonal md-ripple writing-workspace__tool-btn writing-workspace__tool-btn--hero"
        :disabled="isAiMenuDisabled"
        :aria-expanded="showAiMenu ? 'true' : 'false'"
        aria-haspopup="menu"
        :aria-controls="aiMenuId"
        @click="toggleAiMenu"
      >
        <span class="writing-workspace__label-full">AI优化</span>
        <span class="writing-workspace__label-short">AI</span>
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      <div
        v-if="showAiMenu"
        :id="aiMenuId"
        ref="aiMenuPanelRef"
        class="writing-workspace__menu-panel"
        role="menu"
        tabindex="-1"
        @keydown="handleAiMenuKeydown"
      >
        <button
          :ref="(el) => registerAiMenuItemRef(el, 0)"
          type="button"
          role="menuitem"
          class="writing-workspace__menu-item"
          :disabled="!hasSelectedChapterContent"
          @click="handleLayeredOptimize"
        >
          分层优化
        </button>
        <button
          :ref="(el) => registerAiMenuItemRef(el, 1)"
          type="button"
          role="menuitem"
          class="writing-workspace__menu-item"
          :disabled="!hasSelectedChapterContent"
          @click="handlePolishContent"
        >
          润色正文
        </button>
        <button
          :ref="(el) => registerAiMenuItemRef(el, 2)"
          type="button"
          role="menuitem"
          class="writing-workspace__menu-item"
          :disabled="!hasSelectedChapterContent"
          @click="handleAdjustRhythm"
        >
          调整节奏
        </button>
        <button
          :ref="(el) => registerAiMenuItemRef(el, 3)"
          type="button"
          role="menuitem"
          class="writing-workspace__menu-item"
          :disabled="!hasSelectedChapterContent"
          @click="handleRewriteStyle"
        >
          改写风格
        </button>
      </div>
    </div>

    <details ref="moreMenuRef" class="writing-workspace__more-menu">
      <summary class="md-ripple writing-workspace__tool-btn writing-workspace__more-trigger">
        更多
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
        </svg>
      </summary>
      <div class="writing-workspace__menu-panel writing-workspace__more-panel" aria-label="更多章节操作">
        <button
          type="button"
          class="writing-workspace__menu-item"
          :disabled="!hasSelectedChapterContent"
          @click="copyContent"
        >
          复制正文
        </button>
        <button
          type="button"
          class="writing-workspace__menu-item"
          :disabled="!isChapterContentView"
          @click="exportContent"
        >
          导出文本
        </button>
        <button
          type="button"
          class="writing-workspace__menu-item"
          :aria-label="assistantOpen ? '收起右侧辅助面板' : '展开右侧辅助面板'"
          :aria-expanded="assistantOpen ? 'true' : 'false'"
          aria-controls="writing-desk-assistant-panel"
          @click="toggleAssistant"
        >
          {{ assistantOpen ? '收起辅助信息' : '打开辅助信息' }}
        </button>
      </div>
    </details>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref, toRef, watch } from 'vue'
import { useAiMenu } from '@/composables/useAiMenu'

type BodyComponentExpose = {
  openOptimizerPanel?: () => void
  openOptimizerPanelWithPreset?: (preset?: { dimension?: string; notes?: string }) => void
  exportCurrentChapterAsTxt?: () => void
}

interface Props {
  chapterNumber: number | null
  isFinalizedSuccessful: boolean
  hasSelectedChapterContent: boolean
  isChapterContentView: boolean
  isAiMenuDisabled: boolean
  bodyComponentRef: BodyComponentExpose | null
  assistantOpen: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  copyContent: []
  openEditModal: []
  toggleAssistant: []
}>()
const moreMenuRef = ref<HTMLDetailsElement | null>(null)

const {
  aiMenuRef,
  aiMenuPanelRef,
  aiMenuTriggerRef,
  aiMenuId,
  showAiMenu,
  registerAiMenuItemRef,
  handleAiMenuKeydown,
  toggleAiMenu,
  closeAiMenu,
  handleLayeredOptimize,
  handlePolishContent,
  handleAdjustRhythm,
  handleRewriteStyle,
  exportContentAsTxt,
} = useAiMenu({
  isAiMenuDisabled: computed(() => props.isAiMenuDisabled),
  isChapterContentView: computed(() => props.isChapterContentView),
  bodyComponentRef: toRef(props, 'bodyComponentRef'),
})

const closeMoreMenu = () => {
  if (moreMenuRef.value) moreMenuRef.value.open = false
}

const copyContent = () => {
  emit('copyContent')
  closeMoreMenu()
}

const exportContent = () => {
  exportContentAsTxt()
  closeMoreMenu()
}

const toggleAssistant = () => {
  emit('toggleAssistant')
  closeMoreMenu()
}

watch(
  () => props.chapterNumber,
  () => {
    closeAiMenu()
    closeMoreMenu()
  },
)
</script>

<style scoped>
.writing-workspace__toolbar {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  margin-left: auto;
  white-space: nowrap;
}

.writing-workspace__ai-menu,
.writing-workspace__more-menu {
  position: relative;
}

.writing-workspace__tool-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-height: 44px;
  height: 44px;
  padding-inline: 12px;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-sm);
  background-color: transparent;
  color: var(--md-on-surface);
  font-family: var(--md-font-serif);
  font-size: var(--md-label-medium);
  font-weight: 700;
  letter-spacing: 0.04em;
  cursor: pointer;
  transition:
    background-color 0.2s var(--md-easing-standard),
    border-color 0.2s var(--md-easing-standard),
    color 0.2s var(--md-easing-standard);
}

.writing-workspace__tool-btn:hover:not(:disabled) {
  border-color: var(--md-outline);
  background-color: var(--md-state-layer-hover);
}

.writing-workspace__tool-btn:focus-visible,
.writing-workspace__menu-item:focus-visible {
  outline: 2px solid var(--md-on-surface);
  outline-offset: 2px;
}

.writing-workspace__tool-btn:disabled,
.writing-workspace__menu-item:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.writing-workspace__tool-btn--hero {
  border-color: var(--md-outline);
}

.writing-workspace__label-short {
  display: none;
}

.writing-workspace__more-trigger {
  list-style: none;
  user-select: none;
}

.writing-workspace__more-trigger::-webkit-details-marker {
  display: none;
}

.writing-workspace__more-menu[open] .writing-workspace__more-trigger {
  border-color: var(--md-outline);
  background-color: var(--md-state-layer-pressed);
}

.writing-workspace__menu-panel {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  z-index: 48;
  min-width: 180px;
  padding: 4px;
  border: 1px solid var(--md-outline);
  border-radius: var(--md-radius-sm);
  background: var(--md-surface);
  box-shadow: var(--md-elevation-paper-2);
  animation: ink-menu-slide 0.2s cubic-bezier(0.22, 1, 0.36, 1) both;
}

.writing-workspace__menu-item {
  display: block;
  width: 100%;
  min-height: 44px;
  padding: 8px 12px;
  border: 0;
  border-radius: var(--md-radius-xs);
  background: transparent;
  color: var(--md-on-surface);
  text-align: left;
  font-family: var(--md-font-serif);
  font-size: var(--md-label-medium);
  font-weight: 600;
  cursor: pointer;
}

.writing-workspace__menu-item:hover:not(:disabled) {
  background-color: var(--md-state-layer-hover);
}

@keyframes ink-menu-slide {
  from {
    opacity: 0;
    transform: translateY(-6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 640px) {
  .writing-workspace__tool-btn {
    padding-inline: 10px;
  }

  .writing-workspace__label-full {
    display: none;
  }

  .writing-workspace__label-short {
    display: inline;
  }
}
</style>
