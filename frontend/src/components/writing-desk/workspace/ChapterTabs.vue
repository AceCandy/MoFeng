<!-- AIMETA P=章节工作台三合一分区切换栏_正文版本评审|R=tab切换_版本计数|NR=不含tab状态归属与切换后内容分发|E=component:ChapterTabs|X=internal|A=章节工作台分区切换|D=vue|S=dom|RD=./README.ai -->
<template>
  <nav class="writing-workspace__tabs" aria-label="章节工作台分区">
    <button
      type="button"
      class="writing-workspace__tab-btn md-ripple"
      :class="{ 'is-active': activeTab === 'content' }"
      @click="$emit('update:activeTab', 'content')"
    >
      <span class="tab-badge">🎴</span>
      <span>章节正文</span>
    </button>
    <button
      type="button"
      class="writing-workspace__tab-btn md-ripple"
      :class="{ 'is-active': activeTab === 'versions' }"
      @click="$emit('update:activeTab', 'versions')"
    >
      <span class="tab-badge">📜</span>
      <span>查看版本 ({{ versionsCount }})</span>
    </button>
    <button
      type="button"
      class="writing-workspace__tab-btn md-ripple"
      :class="{ 'is-active': activeTab === 'evaluation' }"
      @click="$emit('update:activeTab', 'evaluation')"
    >
      <span class="tab-badge">⚖️</span>
      <span>AI 评审反馈</span>
    </button>
  </nav>
</template>

<script setup lang="ts">
// 章节正文/历史版本/AI 评审 三合一 Tab 切换栏（从 WDWorkspace 抽出，行为逐行等价）
type ChapterTab = 'content' | 'versions' | 'evaluation'

defineProps<{
  activeTab: ChapterTab
  versionsCount: number
}>()

defineEmits<{
  'update:activeTab': [ChapterTab]
}>()
</script>

<style scoped>
.writing-workspace__tabs {
  display: flex;
  gap: 4px;
}

.writing-workspace__tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 38px;
  padding: 0 16px;
  border: 1px solid var(--md-outline-variant) !important;
  border-bottom: none !important;
  border-radius: 4px 4px 0 0 !important; /* 笺片式上圆角 */
  background-color: rgba(28, 32, 34, 0.015) !important;
  color: var(--md-on-surface-variant) !important;
  font-family: var(--md-font-serif);
  font-size: 13.5px;
  font-weight: 600;
  cursor: pointer;
  transition:
    background-color 0.2s ease,
    color 0.2s ease,
    box-shadow 0.2s ease;
}

.writing-workspace__tab-btn:hover {
  background-color: var(--md-surface-container-low) !important;
  color: var(--md-primary-dark) !important;
}

/* 激活的朱砂方章笺条 */
.writing-workspace__tab-btn.is-active {
  border: 1.5px solid var(--md-secondary) !important;
  border-bottom: 1.5px solid var(--md-surface) !important; /* 无缝贴合底线 */
  background-color: var(--md-surface) !important; /* 熟宣暖白 */
  color: var(--md-secondary) !important; /* 朱红色 */
  box-shadow: 0 1.5px 0px var(--md-surface);
  margin-bottom: -1.5px; /* 压住底线，呈现一体化连卷 */
  z-index: 10;
}

.tab-badge {
  font-size: 14px;
}
</style>
