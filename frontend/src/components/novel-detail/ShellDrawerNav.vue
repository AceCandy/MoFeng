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
    <div
      v-if="isOpen && !isDesktop"
      class="detail-shell__drawer-backdrop"
      style="background-color: var(--md-scrim)"
      @click="$emit('close')"
    ></div>
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
  /* 侧边栏升级为老宣纸底色与纸帘帘纹 */
  background-color: var(--md-surface-dim);
  background-image: repeating-linear-gradient(90deg, rgba(28, 32, 34, 0.005) 0px, rgba(28, 32, 34, 0.005) 1px, transparent 1px, transparent 24px);
  border-right: 1.5px solid var(--md-outline-variant) !important; /* 单根墨晕细线分割 */
  box-shadow: 1px 0 4px rgba(28, 32, 34, 0.02);
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
  border-bottom: 1.5px solid rgba(28, 32, 34, 0.04) !important; /* 浅墨细线底分隔 */
  background-color: transparent !important;
  color: #8A7C6E !important; /* 浅灰棕文字 */
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

/* 笺条抽出金石颤抖 */
.detail-shell__nav-item:hover,
.detail-shell__nav-item:focus-visible {
  border-color: var(--md-outline) !important;
  background-color: color-mix(in srgb, var(--md-secondary) 4%, var(--md-surface)) !important;
  box-shadow: 2px 2px 0px var(--md-outline) !important;
  transform: translateX(4px);
  color: var(--md-primary-dark) !important;
}

.detail-shell__nav-item:focus-visible {
  outline: 1.5px solid var(--md-outline);
  outline-offset: 2px;
}

/* 激活选中的朱砂方印笺条 */
.detail-shell__nav-item.is-active {
  border: 1px dashed rgba(184, 60, 50, 0.15) !important;
  background-color: rgba(184, 60, 50, 0.03) !important; /* 轻微淡红背景 */
  color: var(--md-secondary) !important; /* 朱红色 */
  font-weight: 700 !important; /* 文字加粗 */
  box-shadow: none !important; /* 取消厚重投影 */
}

.detail-shell__nav-item.is-active::before {
  content: '';
  position: absolute;
  left: 8px;
  top: 50%;
  width: 6px;
  height: 6px;
  border: 1px solid var(--md-secondary);
  background-color: var(--md-secondary-container);
  transform: translateY(-50%) rotate(45deg);
  pointer-events: none;
}

/* 激活时在右下角轻微旋转渐显出朱砂阳刻方印 [ 卷 ] */
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
  color: var(--md-secondary) !important; /* 激活图标也是朱红色 */
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
