<!-- AIMETA P=统计面板_系统使用统计|R=统计图表|NR=不含数据修改|E=component:Statistics|X=ui|A=统计组件|D=vue,chart.js|S=dom,net|RD=./README.ai -->
<template>
  <section class="admin-panel">
    <div class="admin-panel__header admin-panel__header--toolbar">
      <n-button quaternary size="small" @click="fetchStats" :loading="loading">
        刷新
      </n-button>
    </div>

    <div class="admin-panel__body">
      <n-alert v-if="error" type="error" closable @close="error = null">
        {{ error }}
      </n-alert>

      <n-spin :show="loading">
        <n-grid :cols="gridCols" :x-gap="16" :y-gap="16">
          <n-gi>
            <n-card class="stat-card" :bordered="false">
              <div class="stat-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M4 19.5A2.5 2.5 0 016.5 17H20" />
                  <path stroke-linecap="round" stroke-linejoin="round" d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z" />
                </svg>
              </div>
              <n-statistic label="小说总数" :value="stats?.novel_count ?? 0" show-separator>
                <template #suffix>部</template>
              </n-statistic>
            </n-card>
          </n-gi>
          <n-gi>
            <n-card class="stat-card" :bordered="false">
              <div class="stat-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="8" r="4" />
                  <path stroke-linecap="round" stroke-linejoin="round" d="M4 20a8 8 0 0116 0" />
                </svg>
              </div>
              <n-statistic label="用户总数" :value="stats?.user_count ?? 0" show-separator>
                <template #suffix>人</template>
              </n-statistic>
            </n-card>
          </n-gi>
          <n-gi>
            <n-card class="stat-card" :bordered="false">
              <div class="stat-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <n-statistic label="API 请求总数" :value="stats?.api_request_count ?? 0" show-separator>
                <template #suffix>次</template>
              </n-statistic>
            </n-card>
          </n-gi>
        </n-grid>
      </n-spin>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NGi,
  NGrid,
  NSpin,
  NStatistic,
  NSpace
} from 'naive-ui'

import { AdminAPI, type Statistics } from '@/api/admin'

const stats = ref<Statistics | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const isMobile = ref(false)

const updateLayout = () => {
  isMobile.value = window.innerWidth < 768
}

const gridCols = computed(() => (isMobile.value ? 1 : 3))

const fetchStats = async () => {
  loading.value = true
  error.value = null
  try {
    stats.value = await AdminAPI.getStatistics()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '获取统计数据失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  updateLayout()
  window.addEventListener('resize', updateLayout)
  fetchStats()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateLayout)
})
</script>

<style scoped>
.stat-card {
  min-height: 100%;
  border-radius: 18px;
  background-color: var(--md-surface-container-low);
  border: 1px solid var(--md-outline-variant);
}

.stat-card :deep(.n-card__content) {
  display: flex;
  align-items: center;
  gap: var(--md-spacing-4);
  padding: var(--md-spacing-5);
}

.stat-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  flex: 0 0 auto;
  border-radius: var(--md-radius-full);
  background-color: var(--md-primary-container);
  color: var(--md-on-primary-container);
}

.stat-icon svg {
  width: 24px;
  height: 24px;
}

@media (max-width: 767px) {
  .stat-card :deep(.n-card__content) {
    padding: var(--md-spacing-4);
  }

  .stat-icon {
    width: 40px;
    height: 40px;
  }
}
</style>
