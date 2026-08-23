<template>
  <aside
    id="novel-detail-blueprint-nav"
    class="detail-shell__drawer"
    :class="{ 'is-open': isOpen }"
    :aria-hidden="!isOpen ? 'true' : undefined"
    :inert="!isOpen"
  >
    <!-- Navigation Items -->
    <nav class="detail-shell__nav" aria-label="小说档案分区">
      <button
        v-for="section in sections"
        :key="section.key"
        type="button"
        @click="$emit('switch', section.key)"
        @mouseenter="$emit('prefetch', section.key)"
        @focus="$emit('prefetch', section.key)"
        @touchstart.passive="$emit('prefetch', section.key)"
        class="detail-shell__nav-item md-ripple"
        :class="{ 'is-active': activeSection === section.key }"
        :aria-current="activeSection === section.key ? 'page' : undefined"
      >
        <span class="detail-shell__nav-icon" aria-hidden="true">
          <component :is="getSectionIcon(section.key)" class="w-5 h-5" />
        </span>
        <span class="detail-shell__nav-label">{{ section.label }}</span>
      </button>
    </nav>
  </aside>

  <!-- Sidebar Overlay (Mobile) -->
  <transition
    enter-active-class="transition-opacity duration-300"
    leave-active-class="transition-opacity duration-300"
    enter-from-class="opacity-0"
    leave-to-class="opacity-0"
  >
    <button
      v-if="isOpen && !isDesktop"
      type="button"
      class="detail-shell__drawer-backdrop"
      aria-label="关闭小说档案分区导航"
      style="background-color: var(--md-scrim)"
      @click="$emit('close')"
    ></button>
  </transition>
</template>

<script setup lang="ts">
import { getSectionIcon, type SectionKey } from '@/components/novel-detail/sectionIcons'

// 小说档案分区导航抽屉（侧栏 + 移动端遮罩）。从 NovelDetailShell 抽出，纯展示组件。
defineProps<{
  sections: Array<{ key: SectionKey; label: string }>
  activeSection: SectionKey
  isOpen: boolean
  isDesktop: boolean
}>()

defineEmits<{
  (e: 'switch', key: SectionKey): void
  (e: 'prefetch', key: SectionKey): void
  (e: 'close'): void
}>()
</script>

<style scoped>
.detail-shell__drawer {
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  z-index: 30;
  width: 14.5rem; /* 侧边栏宽度优化至230px左右 */
  overflow: hidden;
  /* 侧边栏：熟宣淡底，1px 界格发线分割，静息无影 */
  background-color: var(--md-surface-dim);
  border-right: 1px solid var(--md-jiege) !important;
  transform: translateX(-100%);
  transition:
    transform 300ms cubic-bezier(0.2, 0, 0, 1),
    opacity 200ms cubic-bezier(0.2, 0, 0, 1),
    border-color 200ms cubic-bezier(0.2, 0, 0, 1),
    box-shadow 300ms cubic-bezier(0.2, 0, 0, 1);
  will-change: transform;
}

.detail-shell__drawer.is-open {
  transform: translateX(0);
}

.detail-shell__drawer-backdrop {
  position: fixed;
  inset: 0;
  z-index: 20;
  width: 100%;
  padding: 0;
  border: 0;
}

.detail-shell__nav {
  height: 100%;
  padding: var(--md-spacing-4) var(--md-spacing-2);
  overflow-y: auto;
}

.detail-shell__nav-item {
  position: relative;
  width: 100%;
  min-height: 3rem;
  display: flex;
  align-items: center;
  gap: var(--md-spacing-3);
  padding: var(--md-spacing-2) var(--md-spacing-4);
  /* 古籍目录式扁平书签感 */
  border-radius: 0 !important;
  border: none !important;
  border-bottom: 1.5px solid color-mix(in srgb, var(--md-on-surface) 4%, transparent) !important; /* 浅墨细线底分隔 */
  background-color: transparent !important;
  color: var(--md-on-surface-variant) !important; /* 松烟灰辅助文字 */
  font-family: var(--md-font-serif);
  font-size: 15px;
  font-weight: 500;
  letter-spacing: 0.05em;
  text-align: left;
  cursor: pointer;
  outline: none;
  transition:
    background-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.25s cubic-bezier(0.22, 1, 0.36, 1);
}

.detail-shell__nav-item + .detail-shell__nav-item {
  margin-top: var(--md-spacing-2);
}

/* 笺条抽出：hover 浮起 paper-1，不再染朱 */
.detail-shell__nav-item:hover,
.detail-shell__nav-item:focus-visible {
  border-color: var(--md-outline) !important;
  background-color: var(--md-surface) !important;
  box-shadow: var(--md-elevation-paper-1) !important;
  transform: translateX(4px);
  color: var(--md-primary-dark) !important;
}

.detail-shell__nav-item:focus-visible {
  outline: 1.5px solid var(--md-outline);
  outline-offset: 2px;
}

/* 激活选中：焦墨题签笺片（已定 UI 不见红，激活=作家选定位置） */
.detail-shell__nav-item.is-active {
  border: 1px solid var(--md-jiege) !important;
  background-color: var(--md-surface) !important;
  color: var(--md-primary-dark) !important; /* 焦墨 */
  font-weight: 700 !important; /* 文字加粗 */
  box-shadow: var(--md-elevation-paper-1) !important; /* 轻微浮起标识当前卷 */
}

.detail-shell__nav-item.is-active::before {
  content: '';
  position: absolute;
  left: 8px;
  top: 50%;
  width: 6px;
  height: 6px;
  border: 1px solid var(--md-primary);
  background-color: var(--md-surface-container);
  transform: translateY(-50%) rotate(45deg);
  pointer-events: none;
}

/* 导航图标：无底色，随激活态染焦墨 */
.detail-shell__nav-icon {
  width: 2rem;
  height: 2rem;
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  border-radius: 2px;
  background-color: transparent; /* 去除拼凑感十足的灰色圆背景 */
  color: var(--md-on-surface-variant);
  transition:
    background-color 0.2s cubic-bezier(0.2, 0, 0, 1),
    color 0.2s cubic-bezier(0.2, 0, 0, 1);
}

.detail-shell__nav-item.is-active .detail-shell__nav-icon {
  background-color: transparent;
  color: var(--md-primary-dark) !important; /* 激活图标同为焦墨 */
}

.detail-shell__nav-label {
  flex: 1 1 auto;
  min-width: 0;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (min-width: 1200px) {
  .detail-shell__drawer {
    position: sticky;
    top: 0;
    bottom: auto;
    flex: 0 0 14.5rem; /* 自适应侧边栏宽度优化至230px左右 */
    height: var(--app-viewport-unit);
    max-height: var(--app-viewport-unit);
    transform: translateX(0);
  }
}
</style>
