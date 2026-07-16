<!-- AIMETA P=章节工具栏_复制导出编辑定稿与AI优化菜单|R=AI优化下拉_编辑草稿_确认定稿|NR=不含正文组件ref来源与模态框|E=component:ChapterToolbar|X=internal|A=章节操作工具栏|D=vue|S=dom|RD=./README.ai -->
<template>
  <aside
    class="writing-workspace__toolbar"
    role="toolbar"
    aria-label="章节操作"
  >
    <div v-if="isFinalizedSuccessful" class="writing-workspace__toolbar-row writing-workspace__toolbar-row--utility">
      <div class="writing-workspace__toolbar-group writing-workspace__toolbar-group--utility">
        <button
          type="button"
          @click="$emit('copyContent')"
          :disabled="!hasSelectedChapterContent"
          class="md-btn md-btn-text md-ripple writing-workspace__tool-btn writing-workspace__tool-btn--ghost disabled:opacity-50 disabled:cursor-not-allowed"
        >
          复制
        </button>
        <button
          type="button"
          @click="exportContentAsTxt"
          :disabled="!isChapterContentView"
          class="md-btn md-btn-text md-ripple writing-workspace__tool-btn writing-workspace__tool-btn--ghost disabled:opacity-50 disabled:cursor-not-allowed"
        >
          导出
        </button>
      </div>
    </div>

    <div v-if="isDraftWaitingConfirm" class="writing-workspace__toolbar-row writing-workspace__toolbar-row--primary">
      <div class="writing-workspace__toolbar-group writing-workspace__toolbar-group--emphasis">
        <button
          type="button"
          @click="$emit('openEditModal')"
          :disabled="!hasSelectedChapterContent"
          class="md-btn md-btn-outlined md-ripple writing-workspace__tool-btn writing-workspace__tool-btn--secondary writing-workspace__tool-btn--hero disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <span class="writing-workspace__label-full">编辑草稿</span>
          <span class="writing-workspace__label-short">编辑</span>
        </button>

        <button
          v-if="isDraftWaitingConfirm && hasSelectedChapterContent"
          type="button"
          @click="$emit('confirmVersionSelection', {})"
          class="md-btn md-btn-filled md-ripple writing-workspace__tool-btn writing-workspace__tool-btn--primary writing-workspace__tool-btn--hero"
        >
          <span class="writing-workspace__label-full">确认定稿</span>
          <span class="writing-workspace__label-short">定稿</span>
        </button>

        <div ref="aiMenuRef" class="writing-workspace__ai-menu">
          <button
            ref="aiMenuTriggerRef"
            type="button"
            @click="toggleAiMenu"
            :disabled="isAiMenuDisabled"
            class="md-btn md-btn-tonal md-ripple writing-workspace__tool-btn writing-workspace__tool-btn--primary writing-workspace__tool-btn--hero disabled:opacity-50 disabled:cursor-not-allowed"
            :aria-expanded="showAiMenu ? 'true' : 'false'"
            aria-haspopup="menu"
            :aria-controls="aiMenuId"
          >
            <span class="writing-workspace__label-full">AI优化</span>
            <span class="writing-workspace__label-short">AI</span>
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M19 9l-7 7-7-7"
              ></path>
            </svg>
          </button>

          <div
            v-if="showAiMenu"
            :id="aiMenuId"
            ref="aiMenuPanelRef"
            class="writing-workspace__ai-menu-panel"
            role="menu"
            tabindex="-1"
            @keydown="handleAiMenuKeydown"
          >
            <button
              :ref="(el) => registerAiMenuItemRef(el, 0)"
              type="button"
              role="menuitem"
              @click="handleLayeredOptimize"
              :disabled="!hasSelectedChapterContent"
              class="writing-workspace__ai-menu-item disabled:opacity-50 disabled:cursor-not-allowed"
            >
              分层优化
            </button>
            <button
              :ref="(el) => registerAiMenuItemRef(el, 1)"
              type="button"
              role="menuitem"
              @click="handlePolishContent"
              :disabled="!hasSelectedChapterContent"
              class="writing-workspace__ai-menu-item disabled:opacity-50 disabled:cursor-not-allowed"
            >
              润色正文
            </button>
            <button
              :ref="(el) => registerAiMenuItemRef(el, 2)"
              type="button"
              role="menuitem"
              @click="handleAdjustRhythm"
              :disabled="!hasSelectedChapterContent"
              class="writing-workspace__ai-menu-item disabled:opacity-50 disabled:cursor-not-allowed"
            >
              调整节奏
            </button>
            <button
              :ref="(el) => registerAiMenuItemRef(el, 3)"
              type="button"
              role="menuitem"
              @click="handleRewriteStyle"
              :disabled="!hasSelectedChapterContent"
              class="writing-workspace__ai-menu-item disabled:opacity-50 disabled:cursor-not-allowed"
            >
              改写风格
            </button>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed, toRef, watch } from 'vue'
import { useAiMenu } from '@/composables/useAiMenu'

/** 章节正文组件对外暴露的优化器/导出方法（与 useAiMenu 内 BodyComponentExpose 同构） */
type BodyComponentExpose = {
  openOptimizerPanel?: () => void
  openOptimizerPanelWithPreset?: (preset?: { dimension?: string; notes?: string }) => void
  exportCurrentChapterAsTxt?: () => void
}

interface Props {
  /** 当前章节号，切换章节时用于收起 AI 菜单 */
  chapterNumber: number | null
  isFinalizedSuccessful: boolean
  isDraftWaitingConfirm: boolean
  hasSelectedChapterContent: boolean
  isChapterContentView: boolean
  isAiMenuDisabled: boolean
  /** 章节正文动态组件实例引用（触发优化器面板/导出），由父组件传入共享 */
  bodyComponentRef: BodyComponentExpose | null
}

const props = defineProps<Props>()
defineEmits(['copyContent', 'openEditModal', 'confirmVersionSelection'])

const {
  aiMenuRef,
  aiMenuPanelRef,
  aiMenuTriggerRef,
  aiMenuItemRefs,
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

// 切换章节时收起 AI 菜单（从 WDWorkspace watch selectedChapterNumber 拆出，closeAiMenu 随 useAiMenu 迁入）
watch(
  () => props.chapterNumber,
  () => {
    closeAiMenu()
  },
)
</script>

<style scoped>
/* ==========================================================================
   章节工具栏（随 template 从 WDWorkspace 迁入）
   ========================================================================== */
.writing-workspace__toolbar {
  margin-left: auto;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: flex-start;
  gap: 8px;
  padding-top: 4px;
  white-space: nowrap;
}

.writing-workspace__toolbar-row {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  width: 100%;
}

.writing-workspace__toolbar-row--utility {
  opacity: 0.96;
}

.writing-workspace__toolbar-row--primary {
  justify-content: flex-end;
}

.writing-workspace__toolbar-group {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

.writing-workspace__toolbar-group--utility {
  gap: 6px;
}

.writing-workspace__toolbar-group--emphasis {
  gap: 8px;
}

.writing-workspace__toolbar-divider {
  width: 1px;
  height: 20px;
  background-color: var(--md-outline);
}

/* 极致国风脑洞：工具栏按钮的直角古朴金石风骨 */
.writing-workspace__tool-btn {
  min-height: 32px;
  height: 32px;
  padding-inline: 12px;
  border-radius: 0 !important; /* 去除圆角 */
  font-size: var(--md-label-medium);
  letter-spacing: 0.05em;
  font-family: var(--md-font-serif);
  font-weight: 600;
  border: 1px solid var(--md-outline);
  box-shadow: 1.5px 1.5px 0px var(--md-outline);
  transition:
    background-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.25s cubic-bezier(0.22, 1, 0.36, 1);
}

/* Hover 状态 */
.writing-workspace__tool-btn:hover:not(:disabled) {
  transform: translate(-0.5px, -0.5px);
  box-shadow: 2px 2px 0px var(--md-outline);
  background-color: var(--md-surface-container-low);
}

/* 脑洞：Active 点击时产生用力向下一压的钤印重力反馈 */
.writing-workspace__tool-btn:active:not(:disabled) {
  transform: translate(1.5px, 1.5px) !important;
  box-shadow: 0px 0px 0px var(--md-outline) !important;
}

.writing-workspace__tool-btn--hero {
  height: 38px;
  min-height: 38px;
  padding-inline: 16px;
  font-size: var(--md-title-small);
  font-weight: bold;
  border: 1.5px solid var(--md-outline) !important;
  box-shadow: 2px 2px 0px var(--md-outline);
}

.writing-workspace__tool-btn--hero:hover:not(:disabled) {
  transform: translate(-1px, -1px);
  box-shadow: 3px 3px 0px var(--md-outline);
}

.writing-workspace__tool-btn--hero:active:not(:disabled) {
  transform: translate(1.5px, 1.5px) !important;
  box-shadow: 0.5px 0.5px 0px var(--md-outline) !important;
}

.writing-workspace__label-full {
  display: inline;
}

.writing-workspace__label-short {
  display: none;
}

.writing-workspace__tool-btn--ghost {
  border-color: var(--md-outline);
  color: var(--md-on-surface-variant);
  background-color: transparent;
  box-shadow: 1px 1px 0px var(--md-outline);
}

.writing-workspace__tool-btn--ghost:hover:not(:disabled) {
  color: var(--md-secondary);
  border-color: var(--md-secondary);
  background-color: rgba(184, 60, 50, 0.02);
  box-shadow: 1.5px 1.5px 0px var(--md-secondary);
}

.writing-workspace__tool-btn--ghost:active:not(:disabled) {
  box-shadow: 0px 0px 0px var(--md-secondary) !important;
}

.writing-workspace__tool-btn--secondary {
  border-color: var(--md-outline) !important;
  background-color: var(--md-surface);
  color: var(--md-on-surface);
}

.writing-workspace__tool-btn--primary {
  border-color: var(--md-secondary) !important;
  background-color: rgba(184, 60, 50, 0.05);
  color: var(--md-secondary);
  box-shadow: 2px 2px 0px var(--md-secondary);
}

.writing-workspace__tool-btn--primary:hover:not(:disabled) {
  background-color: rgba(184, 60, 50, 0.09);
  box-shadow: 3px 3px 0px var(--md-secondary);
  border-color: var(--md-secondary) !important;
}

.writing-workspace__tool-btn--primary:active:not(:disabled) {
  box-shadow: 0px 0px 0px var(--md-secondary) !important;
}

/* 极致国风脑洞：下拉菜单重塑为方直“折页折扇”宣纸面板 */
.writing-workspace__ai-menu-panel {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  z-index: 48;
  min-width: 156px;
  padding: 4px;
  border-radius: 0 !important; /* 强制直角 */
  border: 2px solid var(--md-outline) !important;
  background: var(--md-surface);
  box-shadow: 3px 3px 0px var(--md-outline);
  animation: ink-menu-slide 0.3s cubic-bezier(0.22, 1, 0.36, 1) both;
}

.writing-workspace__ai-menu-panel {
  min-width: 180px;
}

/* 极致国风脑洞：菜单项 Hover 水墨吸水徐徐晕开淡染 */
.writing-workspace__ai-menu-item {
  display: block;
  width: 100%;
  min-height: 38px;
  padding: 8px 12px;
  border: 0;
  border-radius: 0 !important;
  background: transparent;
  text-align: left;
  font-size: var(--md-label-medium);
  font-family: var(--md-font-serif);
  font-weight: 600;
  color: var(--md-on-surface);
  cursor: pointer;
  transition: background-color 0.28s cubic-bezier(0.22, 1, 0.36, 1);
}

.writing-workspace__ai-menu-item:hover:not(:disabled) {
  background-color: rgba(184, 60, 50, 0.08) !important; /* 朱砂慢晕淡染 */
  color: var(--md-secondary);
}

.writing-workspace__ai-menu-item:focus-visible {
  outline: 1.5px solid var(--md-secondary);
  background-color: rgba(184, 60, 50, 0.04);
}

.writing-workspace__ai-menu-item--danger {
  color: #b83c32;
}

.writing-workspace__ai-menu-item--danger:hover:not(:disabled) {
  background-color: rgba(184, 60, 50, 0.12) !important;
}

/* 极致国风脑洞：折页折扇徐徐挂下、模糊渐变清晰的宣纸舒展 */
@keyframes ink-menu-slide {
  from {
    opacity: 0;
    transform: scaleY(0.8) translateY(-8px);
    transform-origin: top right;
  }
  to {
    opacity: 1;
    transform: scaleY(1) translateY(0);
    transform-origin: top right;
  }
}

@media (max-width: 1160px) {
  .writing-workspace__toolbar-divider {
    display: none;
  }
}

@media (max-width: 940px) {
  .writing-workspace__toolbar {
    width: 100%;
    align-items: stretch;
    margin-left: 0;
  }

  .writing-workspace__toolbar-row {
    justify-content: flex-end;
  }
}

@media (max-width: 640px) {
  .writing-workspace__tool-btn {
    min-width: 70px;
    padding-inline: 8px;
  }

  .writing-workspace__tool-btn--hero {
    height: 44px;
    min-height: 44px;
    padding-inline: 12px;
  }

  .writing-workspace__label-full {
    display: none;
  }

  .writing-workspace__label-short {
    display: inline;
  }

  .writing-workspace__ai-menu-panel {
    right: 0;
    left: auto;
  }
}
</style>
