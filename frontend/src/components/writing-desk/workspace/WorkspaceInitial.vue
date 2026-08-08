<!-- AIMETA P=初始工作区_初始状态展示|R=初始引导|NR=不含内容编辑|E=component:WorkspaceInitial|X=internal|A=初始状态|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="h-full flex items-center justify-center">
    <div class="md-card md-card-outlined p-8 text-center max-w-md m3-initial-card">
      <div class="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4 m3-initial-icon-wrapper">
        <svg class="w-8 h-8 m3-initial-icon" fill="currentColor" viewBox="0 0 20 20">
          <path d="M4 4a2 2 0 00-2 2v1h16V6a2 2 0 00-2-2H4zM18 9H2v5a2 2 0 002 2h12a2 2 0 002-2V9zM4 13a1 1 0 011-1h1a1 1 0 110 2H5a1 1 0 01-1-1zm5-1a1 1 0 100 2h1a1 1 0 100-2H9z"></path>
        </svg>
      </div>
      <h3 class="md-title-medium font-semibold mb-2 m3-initial-title">选择章节开始创作</h3>
      <p class="md-body-medium m3-initial-desc">从左侧章节列表中选择一个章节，开始您的创作之旅</p>
    </div>
  </div>
</template>

<script setup lang="ts">
// No script needed for this simple component
</script>

<style scoped>
.m3-initial-card {
  border-radius: var(--md-radius-sm) !important;
  border: 3px double var(--md-outline) !important;
  background-color: var(--md-surface-dim) !important;
  box-shadow: var(--md-elevation-paper-1) !important;
}

.m3-initial-icon-wrapper {
  background-color: var(--md-surface-container) !important;
}

.m3-initial-icon {
  color: var(--md-on-surface-variant) !important;
}

.m3-initial-title {
  font-family: var(--md-font-serif) !important;
  letter-spacing: 0.05em !important;
  color: var(--md-on-surface) !important;
}

.m3-initial-desc {
  color: var(--md-on-surface-variant) !important;
}
</style>

