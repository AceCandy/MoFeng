<template>
  <div class="mofeng-table-shell">
    <n-data-table
      v-bind="$attrs"
      :bordered="false"
      class="mofeng-table"
    >
      <!-- 动态透传所有 slot 插槽 -->
      <template v-for="(_, name) in $slots" #[name]="slotProps">
        <slot :name="name" v-bind="slotProps || {}" />
      </template>
    </n-data-table>
  </div>
</template>

<script setup lang="ts">
import { NDataTable } from 'naive-ui/es/data-table'

defineOptions({
  inheritAttrs: false
})
</script>

<style scoped>
/* 墨风国风表格容器：双线古籍框，方圆风骨微直角 */
.mofeng-table-shell {
  background-color: var(--md-surface);
  border: 3px double var(--md-outline);
  padding: 4px;
  border-radius: var(--md-radius-xs); /* 2px 极窄直角 */
  box-shadow: var(--md-shadow-primary-1); /* 拓片硬投影 */
  position: relative;
  overflow: hidden;
  transition: border-color var(--md-duration-medium) var(--md-easing-standard),
              box-shadow var(--md-duration-medium) var(--md-easing-standard);
}

.mofeng-table {
  background-color: transparent !important;
}

/* 深度定制 Naive UI 的内部表格样式 */
:deep(.n-data-table-table) {
  background-color: transparent !important;
}

/* 单元格与表头基本布局及中式大气留白 */
:deep(.n-data-table-th) {
  background-color: var(--md-surface-container) !important;
  color: var(--md-primary) !important;
  font-family: var(--md-font-display) !important;
  font-size: var(--md-label-large) !important;
  font-weight: 600 !important;
  letter-spacing: 0.08em !important;
  padding: 14px 18px !important;
  border-bottom: 2px solid var(--md-outline) !important;
  text-align: left;
}

:deep(.n-data-table-td) {
  background-color: transparent !important;
  color: var(--md-on-surface) !important;
  padding: 16px 18px !important;
  border-bottom: 1px dashed var(--md-outline-variant) !important;
  transition: background-color var(--md-duration-medium) var(--md-easing-standard) !important;
}

/* 水墨渐变 Hover 态（朱砂印泥淡红） */
:deep(.n-data-table-tr:hover .n-data-table-td) {
  background-color: var(--md-secondary-container) !important; /* 淡朱砂红色 */
  color: var(--md-on-secondary-container) !important;
}

/* 斑马纹行交替宣纸竹纸色 */
:deep(.n-data-table-tr--striped .n-data-table-td) {
  background-color: var(--md-surface-container-low) !important;
}

/* 空状态样式适配 */
:deep(.n-empty) {
  padding: var(--md-spacing-8) 0;
}

/* 古风印章刻印分页样式 */
:deep(.n-data-table__pagination) {
  margin-top: var(--md-spacing-4) !important;
  justify-content: flex-end !important;
  padding: 0 12px 12px 12px !important;
}

/* 分页控制区 */
:deep(.n-pagination) {
  display: flex !important;
  align-items: center !important;
  gap: var(--md-spacing-1) !important;
}

/* 分页按钮中式方章化 */
:deep(.n-pagination-item) {
  height: 44px !important;
  min-width: 44px !important;
  line-height: 42px !important;
  border: 1px solid var(--md-outline) !important;
  border-radius: var(--md-radius-xs) !important;
  font-family: var(--md-font-display) !important;
  font-size: var(--md-label-large) !important;
  font-weight: 500 !important;
  background-color: var(--md-surface-container-lowest) !important;
  color: var(--md-on-surface) !important;
  transition:
    background-color var(--md-duration-short) var(--md-easing-standard),
    border-color var(--md-duration-short) var(--md-easing-standard),
    box-shadow var(--md-duration-short) var(--md-easing-standard),
    color var(--md-duration-short) var(--md-easing-standard) !important;
  display: inline-flex !important;
  justify-content: center !important;
  align-items: center !important;
  padding: 0 10px !important;
  cursor: pointer !important;
}

:deep(.n-pagination-item:hover) {
  border-color: var(--md-primary) !important;
  color: var(--md-primary) !important;
}

/* 当前激活页：显示为醒目的红色小方章印拓 */
:deep(.n-pagination-item--active) {
  background-color: var(--md-secondary) !important; /* 朱砂红 */
  color: var(--md-on-primary) !important;
  border-color: var(--md-secondary) !important;
  box-shadow: 1px 1px 0px rgba(184, 60, 50, 0.25) !important;
}

/* 页码切换箭头项 */
:deep(.n-pagination-item--button) {
  background-color: var(--md-surface-container-low) !important;
}

:deep(.n-pagination-item--disabled) {
  opacity: 0.4 !important;
  cursor: not-allowed !important;
}

/* 自适应及阴影过渡效果 */
.mofeng-table-shell:hover {
  border-color: var(--md-primary-light);
  box-shadow: var(--md-elevation-2);
}
</style>
