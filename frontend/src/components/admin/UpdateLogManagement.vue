<!-- AIMETA P=更新日志管理_系统更新记录|R=日志CRUD|NR=不含系统更新|E=component:UpdateLogManagement|X=ui|A=日志组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <section class="admin-panel admin-panel--list">
    <div class="admin-panel__header admin-panel__header--toolbar">
      <n-button quaternary size="small" @click="fetchLogs" :loading="loading">
        刷新
      </n-button>
    </div>

    <div class="admin-panel__body">
      <n-alert v-if="error" type="error" closable @close="error = null">
        {{ error }}
      </n-alert>

      <div class="form-card">
        <n-form :model="form" label-placement="top">
          <n-form-item label="更新内容">
            <n-input
              v-model:value="form.content"
              type="textarea"
              :autosize="{ minRows: 3, maxRows: 10 }"
              placeholder="输入新的更新日志..."
            />
          </n-form-item>
          <n-form-item label="置顶">
            <n-switch v-model:value="form.isPinned" />
          </n-form-item>
          <n-space justify="end">
            <n-button type="primary" :loading="submitting" @click="addLog" :disabled="!form.content.trim()">
              发布日志
            </n-button>
          </n-space>
        </n-form>
      </div>

      <n-spin :show="loading">
        <n-empty v-if="!logs.length && !loading" description="目前还没有更新记录" />
        <div v-else class="admin-table-shell log-list">
          <article
            v-for="log in orderedLogs"
            :key="log.id"
            class="log-card"
          >
            <div class="log-header">
              <n-space align="center" size="small">
                <n-tag v-if="log.is_pinned" type="warning" :bordered="false">置顶</n-tag>
                <span class="log-date">{{ formatDate(log.created_at) }}</span>
                <span v-if="log.created_by" class="log-author">by {{ log.created_by }}</span>
              </n-space>
              <n-space size="small">
                <n-switch
                  :value="log.is_pinned"
                  size="small"
                  :loading="togglingId === log.id"
                  @update:value="(value) => togglePin(log, value)"
                >
                  <template #checked>置顶</template>
                  <template #unchecked>置顶</template>
                </n-switch>
                <n-popconfirm
                  placement="left"
                  positive-text="删除"
                  negative-text="取消"
                  type="error"
                  @positive-click="() => deleteLog(log.id)"
                >
                  <template #trigger>
                    <n-button quaternary type="error" size="small" :loading="deletingId === log.id">
                      删除
                    </n-button>
                  </template>
                  确认删除该更新日志？
                </n-popconfirm>
              </n-space>
            </div>
            <div class="log-content">
              {{ log.content }}
            </div>
          </article>
        </div>
      </n-spin>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { NAlert } from 'naive-ui/es/alert'
import { NButton } from 'naive-ui/es/button'
import { NEmpty } from 'naive-ui/es/empty'
import { NForm, NFormItem } from 'naive-ui/es/form'
import { NInput } from 'naive-ui/es/input'
import { NPopconfirm } from 'naive-ui/es/popconfirm'
import { NSpace } from 'naive-ui/es/space'
import { NSpin } from 'naive-ui/es/spin'
import { NSwitch } from 'naive-ui/es/switch'
import { NTag } from 'naive-ui/es/tag'

import type { UpdateLog } from '@/api/admin'
import { useAlert } from '@/composables/useAlert'
import {
  useAdminUpdateLogsQuery,
  useCreateAdminUpdateLogMutation,
  useDeleteAdminUpdateLogMutation,
  useUpdateAdminUpdateLogMutation,
} from '@/queries/admin'

const { showAlert } = useAlert()

const logsQuery = useAdminUpdateLogsQuery()
const createLogMutation = useCreateAdminUpdateLogMutation()
const updateLogMutation = useUpdateAdminUpdateLogMutation()
const deleteLogMutation = useDeleteAdminUpdateLogMutation()
const logs = computed<UpdateLog[]>(() => logsQuery.data.value ?? [])
const loading = computed(() => logsQuery.isLoading.value || logsQuery.isFetching.value)
const submitting = computed(() => createLogMutation.isPending.value)
const deletingId = ref<number | null>(null)
const togglingId = ref<number | null>(null)
const isErrorDismissed = ref(false)
const error = computed({
  get: () => {
    if (isErrorDismissed.value) return null
    const queryError = logsQuery.error.value
    return queryError instanceof Error ? queryError.message : queryError ? String(queryError) : null
  },
  set: () => {
    isErrorDismissed.value = true
  },
})

const form = ref({
  content: '',
  isPinned: false
})

const orderedLogs = computed(() => {
  return [...logs.value].sort((a, b) => {
    if (a.is_pinned && !b.is_pinned) return -1
    if (!a.is_pinned && b.is_pinned) return 1
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  })
})

const fetchLogs = () => {
  logsQuery.refetch()
}

watch(
  () => logsQuery.error.value,
  () => {
    isErrorDismissed.value = false
  },
)

const resetForm = () => {
  form.value.content = ''
  form.value.isPinned = false
}

const addLog = async () => {
  if (!form.value.content.trim()) return
  try {
    await createLogMutation.mutateAsync({
      content: form.value.content.trim(),
      is_pinned: form.value.isPinned
    })
    resetForm()
    showAlert('更新日志发布成功', 'success')
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '发布失败', 'error')
  }
}

const deleteLog = async (id: number) => {
  deletingId.value = id
  try {
    await deleteLogMutation.mutateAsync(id)
    showAlert('删除成功', 'success')
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '删除失败', 'error')
  } finally {
    deletingId.value = null
  }
}

const togglePin = async (log: UpdateLog, value: boolean) => {
  togglingId.value = log.id
  try {
    await updateLogMutation.mutateAsync({ id: log.id, data: { is_pinned: value } })
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '更新失败', 'error')
  } finally {
    togglingId.value = null
  }
}

const formatDate = (date: string) => {
  try {
    const d = new Date(date)
    if (isNaN(d.getTime())) return date
    
    const year = d.getFullYear()
    const month = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    const hours = String(d.getHours()).padStart(2, '0')
    const minutes = String(d.getMinutes()).padStart(2, '0')
    
    return `${year}年${month}月${day}日 ${hours}:${minutes}`
  } catch (error) {
    return date
  }
}
</script>

<style scoped>
.form-card {
  border-radius: 16px;
  border: 1px solid var(--md-outline-variant);
  background-color: var(--md-surface-container-low);
  padding: var(--md-spacing-4);
}

.log-list {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-3);
  padding: var(--md-spacing-3);
}

.log-card {
  border-radius: 16px;
  border: 1px solid var(--md-outline-variant);
  background-color: var(--md-surface-container-low);
  padding: var(--md-spacing-4);
}

.log-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 10px;
}

.log-date {
  font-size: 0.85rem;
  color: var(--md-on-surface-variant);
}

.log-author {
  font-size: 0.85rem;
  color: var(--md-on-surface-variant);
}

.log-content {
  font-size: 0.95rem;
  color: var(--md-on-surface);
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

</style>
