<template>
  <!-- 加载状态 -->
  <div v-if="loading" class="h-full flex justify-center items-center">
    <div class="text-center">
      <div class="md-spinner mx-auto mb-4"><span></span></div>
      <p class="md-body-medium md-on-surface-variant">正在加载项目数据...</p>
    </div>
  </div>
  <!-- 错误状态 -->
  <div v-else class="text-center py-20">
    <div
      class="md-card md-card-outlined p-8 max-w-md mx-auto"
      style="border-radius: var(--md-radius-xl)"
    >
      <div
        class="w-12 h-12 rounded-full mx-auto mb-4 flex items-center justify-center"
        style="background-color: var(--md-error-container)"
      >
        <svg class="w-6 h-6" style="color: var(--md-error)" fill="currentColor" viewBox="0 0 20 20">
          <path
            fill-rule="evenodd"
            d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
            clip-rule="evenodd"
          ></path>
        </svg>
      </div>
      <h3 class="md-title-large mb-2" style="color: var(--md-on-surface)">加载失败</h3>
      <p class="md-body-medium mb-4" style="color: var(--md-error)">{{ error }}</p>
      <button type="button" @click="$emit('retry')" class="md-btn md-btn-tonal md-ripple">
        重新加载
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
interface Props {
  loading: boolean
  error: string | null
}
defineProps<Props>()
defineEmits(['retry'])
</script>
