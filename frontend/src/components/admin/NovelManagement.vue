<!-- AIMETA P=小说管理_管理员小说列表管理|R=小说列表_删除_统计|NR=不含普通用户功能|E=component:NovelManagement|X=ui|A=管理组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <section class="admin-panel admin-panel--list">
    <div class="admin-panel__header admin-panel__header--toolbar">
      <n-space :size="8" align="center">
        <n-tag size="small" type="primary" round>共 {{ novels.length }} 项</n-tag>
        <n-button quaternary size="small" @click="fetchNovels" :loading="loading">刷新</n-button>
      </n-space>
    </div>

    <div class="admin-panel__body">
      <n-alert v-if="error" type="error" closable @close="error = null">
        {{ error }}
      </n-alert>

      <n-spin :show="loading">
        <template #default>
          <n-empty
            v-if="!novels.length && !loading"
            description="暂无小说项目"
            class="empty-state"
          />
          <div v-else class="admin-table-shell">
            <n-space v-if="isMobile" vertical size="large">
              <article
                v-for="novel in novels"
                :key="novel.id"
                class="novel-card"
              >
                <div class="mobile-card-header">
                  <span class="mobile-card-title">{{ novel.title }}</span>
                  <n-tag size="small" type="info" round>{{ novel.genre || '未分类' }}</n-tag>
                </div>
                <div class="mobile-meta">
                  <span class="mobile-label">编号</span>
                  <span class="mobile-value">{{ novel.id }}</span>
                </div>
                <div class="mobile-meta">
                  <span class="mobile-label">创作者</span>
                  <span class="mobile-value">{{ novel.owner_username }}</span>
                </div>
                <div class="mobile-meta">
                  <span class="mobile-label">进度</span>
                  <span class="mobile-value">{{ formatProgress(novel) }}</span>
                </div>
                <div class="mobile-meta">
                  <span class="mobile-label">最近更新</span>
                  <span class="mobile-value">{{ formatDate(novel.last_edited) }}</span>
                </div>
                <div class="mobile-card-actions">
                  <n-button type="primary" size="small" block @click="viewDetails(novel.id)">
                    查看详情
                  </n-button>
                </div>
              </article>
            </n-space>
            <n-data-table
              v-else
              :columns="columns"
              :data="novels"
              :pagination="pagination"
              :bordered="false"
              size="small"
              class="novel-table"
            />
          </div>
        </template>
      </n-spin>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, h, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { NAlert } from 'naive-ui/es/alert'
import { NButton } from 'naive-ui/es/button'
import { NDataTable } from 'naive-ui/es/data-table'
import { NEmpty } from 'naive-ui/es/empty'
import { NSpace } from 'naive-ui/es/space'
import { NSpin } from 'naive-ui/es/spin'
import { NTag } from 'naive-ui/es/tag'
import type { DataTableColumns } from 'naive-ui'

import type { AdminNovelSummary } from '@/api/admin'
import { useResponsiveViewport } from '@/composables/useResponsiveViewport'
import { mobileMax } from '@/constants/responsive'
import { useAdminNovelsQuery } from '@/queries/admin'

const novelsQuery = useAdminNovelsQuery()
const novels = computed<AdminNovelSummary[]>(() => novelsQuery.data.value ?? [])
const loading = computed(() => novelsQuery.isLoading.value || novelsQuery.isFetching.value)
const isErrorDismissed = ref(false)
const error = computed({
  get: () => {
    if (isErrorDismissed.value) return null
    const queryError = novelsQuery.error.value
    return queryError instanceof Error ? queryError.message : queryError ? String(queryError) : null
  },
  set: () => {
    isErrorDismissed.value = true
  },
})
const viewport = useResponsiveViewport()
const isMobile = computed(() => viewport.width.value <= mobileMax)
const router = useRouter()

const pagination = {
  pageSize: 8,
  showSizePicker: false
}

const MAX_VISIBLE_GENRE_SEGMENTS = 3
const GENRE_SEPARATOR_REGEXP = /\s*[\/,，、|]\s*/

const formatDate = (value: string | null | undefined) => {
  if (!value) return '未记录'
  try {
    const date = new Date(value)
    if (isNaN(date.getTime())) return '未记录'
    
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')
    
    return `${year}年${month}月${day}日 ${hours}:${minutes}`
  } catch (error) {
    return '未记录'
  }
}

const formatProgress = (novel: Pick<AdminNovelSummary, 'completed_chapters' | 'total_chapters'>) => {
  const total = novel.total_chapters || 0
  const completed = novel.completed_chapters || 0
  return `${completed} / ${total}`
}

const genreSegments = (genre: string | null | undefined): string[] => {
  const segments = (genre || '')
    .split(GENRE_SEPARATOR_REGEXP)
    .map((item) => item.trim())
    .filter(Boolean)
  return segments.length ? segments : ['未分类']
}

const visibleGenreSegments = (genre: string | null | undefined): string[] => {
  return genreSegments(genre).slice(0, MAX_VISIBLE_GENRE_SEGMENTS)
}

const overflowGenreCount = (genre: string | null | undefined): number => {
  return Math.max(0, genreSegments(genre).length - MAX_VISIBLE_GENRE_SEGMENTS)
}

const viewDetails = (novelId: string) => {
  router.push(`/admin/novels/${novelId}`)
}

const columns: DataTableColumns<AdminNovelSummary> = [
  {
    title: '项目',
    key: 'title',
    ellipsis: { tooltip: true },
    render(row) {
      return h('div', { class: 'table-title-cell' }, [
        h('div', { class: 'table-title' }, row.title),
        h('div', { class: 'table-subtitle' }, row.id)
      ])
    }
  },
  {
    title: '类型',
    key: 'genre',
    width: 300,
    render(row) {
      const overflowCount = overflowGenreCount(row.genre)
      return h(
        'div',
        {
          class: 'table-genre-list',
          title: row.genre || '未分类'
        },
        [
          ...visibleGenreSegments(row.genre).map((segment) =>
            h('span', { class: 'table-genre-chip' }, segment)
          ),
          overflowCount > 0
            ? h('span', { class: 'table-genre-more' }, `+${overflowCount}`)
            : null
        ]
      )
    }
  },
  {
    title: '创作者',
    key: 'owner_username',
    render(row) {
      return h('span', { class: 'table-owner' }, row.owner_username)
    }
  },
  {
    title: '进度',
    key: 'progress',
    render(row) {
      return h('span', { class: 'table-progress' }, formatProgress(row))
    }
  },
  {
    title: '最近更新',
    key: 'last_edited',
    render(row) {
      return h('span', { class: 'table-date' }, formatDate(row.last_edited))
    }
  },
  {
    title: '操作',
    key: 'actions',
    align: 'center',
    render(row) {
      return h(
        NButton,
        {
          size: 'small',
          type: 'primary',
          tertiary: true,
          onClick: () => viewDetails(row.id)
        },
        { default: () => '详情' }
      )
    }
  }
]

const fetchNovels = () => {
  novelsQuery.refetch()
}

watch(
  () => novelsQuery.error.value,
  () => {
    isErrorDismissed.value = false
  },
)

</script>

<style scoped>
.novel-table {
  width: 100%;
}

:deep(.table-title-cell) {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

:deep(.table-title) {
  font-weight: 600;
  color: var(--md-on-surface);
}

:deep(.table-subtitle) {
  font-size: 0.75rem;
  color: var(--md-on-surface-variant);
  word-break: break-all;
}

:deep(.table-owner),
:deep(.table-progress),
:deep(.table-date) {
  color: var(--md-on-surface-variant);
}

:deep(.table-genre-list) {
  display: flex;
  align-items: center;
  gap: var(--md-spacing-1);
  max-width: 100%;
  overflow: hidden;
  flex-wrap: wrap;
}

:deep(.table-genre-chip),
:deep(.table-genre-more) {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  border-radius: var(--md-radius-full);
  background-color: var(--md-primary-container);
  color: var(--md-primary);
  font-size: var(--md-label-medium);
  font-weight: 600;
  line-height: 1.2;
}

:deep(.table-genre-chip) {
  max-width: 112px;
  padding: 0 var(--md-spacing-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.table-genre-more) {
  padding: 0 var(--md-spacing-2);
  flex: 0 0 auto;
}

.novel-card {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-3);
  padding: var(--md-spacing-4);
  border-radius: 16px;
  background-color: var(--md-surface-container-low);
  border: 1px solid var(--md-outline-variant);
}

.mobile-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
}

.mobile-card-title {
  min-width: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--md-on-surface);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mobile-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 10px;
  font-size: 0.875rem;
  color: var(--md-on-surface-variant);
  word-break: break-word;
}

.mobile-label {
  color: var(--md-on-surface-variant);
}

.mobile-value {
  color: var(--md-on-surface);
  font-weight: 500;
  text-align: right;
  margin-left: 12px;
}

.mobile-card-actions {
  padding-top: var(--md-spacing-2);
}

.empty-state {
  padding: var(--md-spacing-8) 0;
}

@media (max-width: 833px) {
  .mobile-card-header {
    gap: var(--md-spacing-2);
  }
}
</style>
