<template>
  <header class="detail-shell__topbar">
    <div class="detail-shell__topbar-inner">
      <button
        type="button"
        class="detail-shell__drawer-toggle"
        :aria-expanded="isSidebarOpen"
        :aria-label="isSidebarOpen ? '收起蓝图导航' : '展开蓝图导航'"
        :title="isSidebarOpen ? '收起蓝图导航' : '展开蓝图导航'"
        aria-controls="novel-detail-blueprint-nav"
        @click="$emit('toggleSidebar')"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
        </svg>
        <span class="sr-only">切换小说档案分区导航</span>
      </button>
      <button class="md-btn md-btn-outlined md-ripple detail-shell__back-button" @click="$emit('back')">
        返回
      </button>
      <h1 class="detail-shell__title md-title-large truncate" style="color: var(--md-on-surface)">
        {{ title }}
      </h1>
      <span v-if="isAdmin" class="detail-shell__mode-chip">管理只读</span>
      <button
        v-if="!isAdmin"
        class="md-btn md-btn-filled md-ripple detail-shell__write-button"
        @click="$emit('goToWritingDesk')"
      >
        <span class="detail-shell__write-label-full">继续写作</span>
        <span class="detail-shell__write-label-compact">续写</span>
      </button>
    </div>
  </header>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  isAdmin: boolean
  isSidebarOpen: boolean
}>()

defineEmits<{
  toggleSidebar: []
  back: []
  goToWritingDesk: []
}>()
</script>

<style scoped>
.detail-shell__topbar {
  position: sticky;
  top: 0;
  z-index: 40;
}

.detail-shell__topbar-inner {
  max-width: 1800px;
  width: 100%;
  min-height: var(--detail-shell-topbar-height);
  margin: 0 auto;
  padding: 0 1rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  box-sizing: border-box;
}

.detail-shell__title {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-shell__back-button,
.detail-shell__write-button {
  flex: 0 0 auto;
  white-space: nowrap;
}

.detail-shell__write-label-compact {
  display: none;
}

.detail-shell__drawer-toggle {
  min-width: 44px;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--md-spacing-2);
  margin-right: var(--md-spacing-2);
  padding: 0 var(--md-spacing-3);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-xs);
  background-color: var(--md-surface);
  color: var(--md-on-surface-variant);
  font-family: var(--md-font-family);
  cursor: pointer;
  transition:
    background-color var(--md-duration-short) var(--md-easing-standard),
    border-color var(--md-duration-short) var(--md-easing-standard),
    color var(--md-duration-short) var(--md-easing-standard);
}

.detail-shell__drawer-toggle:hover {
  border-color: color-mix(in srgb, var(--md-primary) 36%, var(--md-outline-variant));
  background-color: color-mix(in srgb, var(--md-primary-dark) 8%, var(--md-surface));
  color: var(--md-primary-dark);
}

.detail-shell__drawer-toggle:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}

.detail-shell--drawer-collapsed .detail-shell__drawer-toggle {
  border-color: transparent;
  background-color: var(--md-primary-container);
  color: var(--md-on-primary-container);
}

.detail-shell__drawer-toggle svg {
  width: 20px;
  height: 20px;
  flex: 0 0 auto;
}

.detail-shell__mode-chip {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
  height: 1.75rem;
  padding: 0 0.625rem;
  border-radius: var(--md-radius-xs);
  background-color: color-mix(in srgb, var(--md-secondary-container) 78%, transparent);
  color: var(--md-on-secondary-container);
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  white-space: nowrap;
}

@media (max-width: 833px) {
  .detail-shell__topbar-inner {
    padding-inline: var(--md-spacing-3);
    gap: var(--md-spacing-2);
  }

  .detail-shell__drawer-toggle {
    margin-right: 0;
    padding-inline: var(--md-spacing-2);
  }

  .detail-shell__back-button,
  .detail-shell__write-button {
    min-width: 58px;
    padding-inline: var(--md-spacing-3);
  }

  .detail-shell__write-label-full {
    display: none;
  }

  .detail-shell__write-label-compact {
    display: inline;
  }
}
</style>
