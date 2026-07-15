<template>
  <div class="detail-shell__main">
    <div class="detail-shell__content-wrap">
      <div class="detail-shell__content-frame">
        <!-- Material 3 Card -->
        <section class="detail-shell__content-surface" :class="contentCardClass">
          <!-- Loading State -->
          <div
            v-if="isSectionLoading"
            class="flex flex-col items-center justify-center py-20 sm:py-28"
          >
            <div class="md-spinner"><span></span></div>
            <p class="mt-4 md-body-medium" style="color: var(--md-on-surface-variant)">
              加载中...
            </p>
          </div>

          <!-- Error State -->
          <div
            v-else-if="currentError"
            class="flex flex-col items-center justify-center py-20 sm:py-28 space-y-4"
          >
            <div
              class="w-16 h-16 rounded-xs border border-[var(--md-outline-variant)] flex items-center justify-center"
              style="background-color: var(--md-error-container)"
            >
              <svg
                class="w-8 h-8"
                style="color: var(--md-error-text)"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            </div>
            <p class="md-body-large text-center" style="color: var(--md-on-surface)">
              {{ currentError }}
            </p>
            <button
              class="md-btn md-btn-filled md-ripple"
              @click="$emit('retry')"
            >
              重试
            </button>
          </div>

          <!-- Content -->
          <component
            v-else
            :is="currentComponent"
            v-bind="componentProps"
            :class="componentContainerClass"
            @edit="$emit('edit')"
            @add="$emit('add')"
          />
        </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Component } from 'vue'

defineProps<{
  currentComponent: Component | undefined
  isSectionLoading: boolean
  currentError: string | null
  componentProps: Record<string, unknown>
  contentCardClass: string
  componentContainerClass: string
}>()

defineEmits<{
  edit: []
  add: []
  retry: []
}>()
</script>

<style scoped>
.detail-shell__main {
  display: flex;
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  height: 100%;
  max-height: 100%;
  width: 100%;
  margin-left: 0;
  box-sizing: border-box;
  overflow: hidden;
}

.detail-shell__content-wrap {
  display: flex;
  flex: 1 1 auto;
  align-items: stretch;
  min-width: 0;
  min-height: 0;
  height: 100%;
  max-height: 100%;
  width: 100%;
  padding: 1rem;
  box-sizing: border-box;
  overflow: hidden;
}

.detail-shell__content-frame {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-width: 0;
  height: 100%;
  max-height: 100%;
  width: 100%;
}

.detail-shell__content-surface {
  flex: 1 1 auto;
  width: 100%;
  min-height: 0;
  height: 100%;
  max-height: 100%;
  display: flex;
  flex-direction: column;
  padding: var(--md-spacing-6);
  box-sizing: border-box;
  transition:
    background-color 0.25s cubic-bezier(0.2, 0, 0, 1),
    border-color 0.25s cubic-bezier(0.2, 0, 0, 1),
    box-shadow 0.25s cubic-bezier(0.2, 0, 0, 1);

  /* 水墨微晕极细滚动条美化，保持纯净宣纸质感并引导高品质滚动 */
  scrollbar-width: thin;
  scrollbar-color: rgba(60, 80, 70, 0.25) transparent;
}

.detail-shell__content-surface::-webkit-scrollbar {
  display: block !important;
  width: 4px;
}

.detail-shell__content-surface::-webkit-scrollbar-track {
  background: transparent;
}

.detail-shell__content-surface::-webkit-scrollbar-thumb {
  background-color: rgba(60, 80, 70, 0.2);
  border-radius: var(--md-radius-xs);
}

.detail-shell__content-surface::-webkit-scrollbar-thumb:hover {
  background-color: rgba(60, 80, 70, 0.45);
}

/* 其它设定分区的双线古籍装订框大卡片 */
.detail-shell__content-surface--classical {
  border: 3px double var(--md-outline) !important; /* 双线装订框 */
  border-radius: 4px !important; /* 方折风骨 */
  box-shadow: 2px 2px 0px rgba(28, 32, 34, 0.15) !important; /* 拓片硬投影 */
  background-color: var(--md-surface) !important; /* 熟宣 */
  /* 宣纸帘纹理 */
  background-image: repeating-linear-gradient(90deg, rgba(28, 32, 34, 0.005) 0px, rgba(28, 32, 34, 0.005) 1px, transparent 1px, transparent 32px);
}

.detail-shell__content-surface--fill {
  min-height: 0;
  height: 100%;
  max-height: 100%;
}

@media (min-width: 1200px) {
  .detail-shell__content-wrap {
    padding: var(--md-spacing-3) 2rem 1rem;
  }
}

@media (min-width: 1200px) and (max-height: 700px) {
  .detail-shell__content-surface {
    padding: var(--md-spacing-5);
  }
}

@media (min-width: 834px) {
  .detail-shell__content-surface {
    padding: var(--md-spacing-6);
  }
}

/* ==========================================================================
   统摄并修正蓝图内部所有子卡片的现代扁平圆角，升级为古风竹纸笺条与碑拓小卡片
   ========================================================================== */
.detail-shell__content-surface--classical :deep(.bg-\[var\(--md-surface\)\]) {
  border: 1.5px solid var(--md-outline-variant) !important;
  border-radius: 4px !important; /* 统一碑拓方直 */
  background-color: var(--md-surface-container-low) !important; /* 竹纸淡黄底，产生层叠景深 */
  box-shadow: 1px 1px 0px rgba(28, 32, 34, 0.08) !important;
}

/* 统一统摄深度子卡片的现代圆角，回归方正骨力 */
.detail-shell__content-surface--classical :deep(.rounded-2xl) {
  border-radius: 4px !important;
}
.detail-shell__content-surface--classical :deep(.rounded-xl) {
  border-radius: 2px !important;
}
.detail-shell__content-surface--classical :deep(.rounded-lg) {
  border-radius: 2px !important;
}
.detail-shell__content-surface--classical :deep(.shadow-sm) {
  box-shadow: 1px 1px 0px rgba(28, 32, 34, 0.08) !important;
}
</style>
