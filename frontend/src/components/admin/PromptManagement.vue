<!-- AIMETA P=提示词管理_AI提示模板管理|R=提示词CRUD|NR=不含模型调用|E=component:PromptManagement|X=ui|A=管理组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <section class="admin-panel admin-panel--list">
    <div class="admin-panel__body">
      <n-alert v-if="error" type="error" closable @close="error = null">
        {{ error }}
      </n-alert>

      <n-spin :show="loading">
        <div class="admin-ops">
          <div class="admin-ops__summary">
            <div class="admin-ops__copy">
              <h2>提示词管理中心</h2>
              <p>按唯一标识维护系统 Prompt 模板，编辑前先确认标签、用途和正文完整度。</p>
            </div>
            <n-space :size="12" class="admin-panel__actions admin-ops__toolbar">
              <n-button quaternary size="small" @click="fetchPrompts" :loading="loading">
                刷新
              </n-button>
              <n-button type="primary" size="small" @click="openCreateModal">
                新建 Prompt
              </n-button>
            </n-space>
          </div>

          <div class="admin-ops__metrics">
            <article class="admin-ops__metric">
              <p>Prompt 总数</p>
              <strong>{{ prompts.length }}</strong>
              <span>可维护模板</span>
            </article>
            <article class="admin-ops__metric">
              <p>已打标签</p>
              <strong>{{ taggedPrompts.length }}</strong>
              <span>便于场景归档</span>
            </article>
            <article class="admin-ops__metric">
              <p>当前标签</p>
              <strong>{{ editForm.tags.length }}</strong>
              <span>{{ selectedPrompt ? '已选 Prompt' : '未选择' }}</span>
            </article>
            <article class="admin-ops__metric">
              <p>正文长度</p>
              <strong>{{ selectedPromptContentLength }}</strong>
              <span>当前模板字符数</span>
            </article>
          </div>

          <div class="admin-ops__grid">
            <article class="admin-panel-card admin-panel-card--wide">
              <header>
                <div>
                  <h3>模板编辑台</h3>
                  <p>左侧选择模板，右侧维护标题、标签和正文。</p>
                </div>
                <n-tag size="small" type="info" :bordered="false">{{ prompts.length }} 条</n-tag>
              </header>
              <div class="admin-table-shell prompt-layout" :class="{ mobile: isMobile }">
                <div class="prompt-sidebar">
                  <div class="sidebar-header">
                    <span class="sidebar-title">Prompt 列表</span>
                    <n-tag size="small" type="info" round>{{ prompts.length }}</n-tag>
                  </div>
                  <n-scrollbar class="prompt-scroll">
                    <n-empty v-if="!prompts.length && !loading" description="暂无提示词" />
                    <div v-else class="prompt-list">
                      <button
                        v-for="prompt in prompts"
                        :key="prompt.id"
                        type="button"
                        :class="['prompt-list-item', { active: selectedPrompt?.id === prompt.id }]"
                        @click="selectPrompt(prompt)"
                      >
                        <div class="prompt-item-main">
                          <span class="prompt-item-title">{{ prompt.title || prompt.name }}</span>
                          <span class="prompt-item-key">{{ prompt.name }}</span>
                        </div>
                        <n-tag
                          v-if="prompt.tags?.length"
                          size="tiny"
                          round
                          :type="selectedPrompt?.id === prompt.id ? 'success' : 'info'"
                        >
                          {{ prompt.tags.length }} 标签
                        </n-tag>
                        <span v-else class="prompt-item-meta">无标签</span>
                      </button>
                    </div>
                  </n-scrollbar>
                </div>

                <div class="prompt-editor">
                  <div v-if="!selectedPrompt" class="empty-editor">
                    <n-empty description="请选择一个提示词以编辑" />
                  </div>
                  <div v-else class="editor-content">
                    <n-form label-placement="top" :model="editForm">
                      <n-form-item label="唯一标识">
                        <n-input v-model:value="editForm.name" disabled />
                      </n-form-item>
                      <n-form-item label="标题">
                        <n-input
                          v-model:value="editForm.title"
                          placeholder="用于后台识别的标题，可为空"
                        />
                      </n-form-item>
                      <n-form-item label="标签">
                        <n-dynamic-tags
                          v-model:value="editForm.tags"
                          size="small"
                          placeholder="输入标签后回车"
                        />
                      </n-form-item>
                      <n-form-item label="提示词内容">
                        <n-input
                          v-model:value="editForm.content"
                          type="textarea"
                          :autosize="{ minRows: isMobile ? 8 : 16, maxRows: 40 }"
                          placeholder="请输入完整的提示词内容..."
                          class="prompt-textarea"
                        />
                      </n-form-item>
                    </n-form>
                    <n-space justify="end">
                      <n-popconfirm
                        v-if="selectedPrompt"
                        placement="bottom"
                        positive-text="删除"
                        negative-text="取消"
                        type="error"
                        @positive-click="deletePrompt"
                      >
                        <template #trigger>
                          <n-button type="error" quaternary :loading="deleting">
                            删除
                          </n-button>
                        </template>
                        确认删除该 Prompt？
                      </n-popconfirm>
                      <n-button type="primary" :loading="saving" @click="savePrompt">
                        保存修改
                      </n-button>
                    </n-space>
                  </div>
                </div>
              </div>
            </article>

            <article class="admin-panel-card">
              <header>
                <div>
                  <h3>标签巡检</h3>
                  <p>未打标签的模板更难排查调用边界。</p>
                </div>
              </header>
              <ul class="admin-insight-list prompt-status-list">
                <li>
                  <strong>{{ taggedPrompts.length }} 条已打标签</strong>
                  <span>保留清晰用途和阶段归属。</span>
                </li>
                <li>
                  <strong>{{ untaggedPrompts.length }} 条未打标签</strong>
                  <span>建议补充标签减少维护成本。</span>
                </li>
              </ul>
            </article>

            <article class="admin-panel-card">
              <header>
                <div>
                  <h3>当前模板</h3>
                  <p>保存前确认唯一标识不变，正文不能为空。</p>
                </div>
              </header>
              <ul class="admin-insight-list prompt-status-list">
                <li>
                  <strong>{{ selectedPrompt?.name || '未选择' }}</strong>
                  <span>{{ selectedPrompt?.title || '选择一个 Prompt 后查看标题' }}</span>
                </li>
                <li>
                  <strong>{{ selectedPromptContentLength }} 字符</strong>
                  <span>当前正文长度。</span>
                </li>
              </ul>
            </article>
          </div>
        </div>
      </n-spin>
    </div>
  </section>

  <n-modal v-model:show="createModalVisible" preset="card" title="新建 Prompt" class="prompt-modal">
    <n-form label-placement="top" :model="createForm">
      <n-form-item label="唯一标识（必填）">
        <n-input v-model:value="createForm.name" placeholder="例如 concept / outline" />
      </n-form-item>
      <n-form-item label="标题">
        <n-input v-model:value="createForm.title" placeholder="可选，用于后台展示" />
      </n-form-item>
      <n-form-item label="标签">
        <n-dynamic-tags
          v-model:value="createForm.tags"
          size="small"
          placeholder="输入标签后回车"
        />
      </n-form-item>
      <n-form-item label="内容">
        <n-input
          v-model:value="createForm.content"
          type="textarea"
          :autosize="{ minRows: 10, maxRows: 30 }"
          placeholder="输入提示词内容..."
        />
      </n-form-item>
    </n-form>
    <template #footer>
      <n-space justify="end">
        <n-button quaternary @click="closeCreateModal">取消</n-button>
        <n-button type="primary" :loading="creating" @click="createPrompt">创建</n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { NAlert } from 'naive-ui/es/alert'
import { NButton } from 'naive-ui/es/button'
import { NDynamicTags } from 'naive-ui/es/dynamic-tags'
import { NEmpty } from 'naive-ui/es/empty'
import { NForm, NFormItem } from 'naive-ui/es/form'
import { NInput } from 'naive-ui/es/input'
import { NModal } from 'naive-ui/es/modal'
import { NPopconfirm } from 'naive-ui/es/popconfirm'
import { NScrollbar } from 'naive-ui/es/scrollbar'
import { NSpace } from 'naive-ui/es/space'
import { NSpin } from 'naive-ui/es/spin'
import { NTag } from 'naive-ui/es/tag'

import type { PromptCreatePayload, PromptItem } from '@/api/admin'
import { useAlert } from '@/composables/useAlert'
import { useResponsiveViewport } from '@/composables/useResponsiveViewport'
import { mobileMax } from '@/constants/responsive'
import {
  useAdminPromptsQuery,
  useCreateAdminPromptMutation,
  useDeleteAdminPromptMutation,
  useUpdateAdminPromptMutation,
} from '@/queries/admin'

const { showAlert } = useAlert()

const promptsQuery = useAdminPromptsQuery()
const createPromptMutation = useCreateAdminPromptMutation()
const updatePromptMutation = useUpdateAdminPromptMutation()
const deletePromptMutation = useDeleteAdminPromptMutation()
const prompts = computed<PromptItem[]>(() => promptsQuery.data.value ?? [])
const selectedPrompt = ref<PromptItem | null>(null)
const taggedPrompts = computed(() => prompts.value.filter((prompt) => (prompt.tags?.length ?? 0) > 0))
const untaggedPrompts = computed(() => prompts.value.filter((prompt) => !(prompt.tags?.length)))
const loading = computed(() => promptsQuery.isLoading.value || promptsQuery.isFetching.value)
const saving = computed(() => updatePromptMutation.isPending.value)
const deleting = computed(() => deletePromptMutation.isPending.value)
const creating = computed(() => createPromptMutation.isPending.value)
const isErrorDismissed = ref(false)
const error = computed({
  get: () => {
    if (isErrorDismissed.value) return null
    const queryError = promptsQuery.error.value
    return queryError instanceof Error ? queryError.message : queryError ? String(queryError) : null
  },
  set: () => {
    isErrorDismissed.value = true
  },
})
const editForm = reactive({
  name: '',
  title: '',
  content: '',
  tags: [] as string[]
})
const selectedPromptContentLength = computed(() => editForm.content.trim().length)

const createModalVisible = ref(false)
const createForm = reactive<PromptCreatePayload>({
  name: '',
  title: '',
  content: '',
  tags: []
})

const viewport = useResponsiveViewport()
const isMobile = computed(() => viewport.width.value <= mobileMax)
const NAME_REGEXP = /^[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}$/
const MAX_TITLE_LENGTH = 255
const MAX_TAG_COUNT = 12
const MAX_TAG_LENGTH = 24
const MAX_SERIALIZED_TAG_LENGTH = 255

const normalizeTags = (tags: string[] | null | undefined): string[] => {
  const normalized = (tags || [])
    .map((tag) => tag.trim())
    .filter((tag) => Boolean(tag))
  return Array.from(new Set(normalized))
}

const validateName = (name: string): string | null => {
  if (!name) {
    return '名称不能为空'
  }
  if (!NAME_REGEXP.test(name)) {
    return '名称仅支持字母、数字、下划线和中划线，且必须以字母或数字开头'
  }
  return null
}

const validatePromptPayload = (payload: { title?: string; content: string; tags: string[] }): string | null => {
  if (!payload.content.trim()) {
    return '提示词内容不能为空'
  }

  if ((payload.title || '').trim().length > MAX_TITLE_LENGTH) {
    return `标题长度不能超过 ${MAX_TITLE_LENGTH} 个字符`
  }

  if (payload.tags.length > MAX_TAG_COUNT) {
    return `标签数量不能超过 ${MAX_TAG_COUNT} 个`
  }

  if (payload.tags.some((tag) => tag.length > MAX_TAG_LENGTH)) {
    return `单个标签长度不能超过 ${MAX_TAG_LENGTH} 个字符`
  }

  if (payload.tags.some((tag) => tag.includes(','))) {
    return '标签不能包含英文逗号'
  }

  if (payload.tags.join(',').length > MAX_SERIALIZED_TAG_LENGTH) {
    return '标签总长度过长，请减少标签数量或缩短标签文本'
  }

  return null
}

const fetchPrompts = () => {
  promptsQuery.refetch()
}

watch(
  () => promptsQuery.error.value,
  () => {
    isErrorDismissed.value = false
  },
)

watch(
  prompts,
  (list) => {
    if (selectedPrompt.value) {
      const refreshed = list.find((item) => item.id === selectedPrompt.value?.id)
      if (refreshed) {
        selectPrompt(refreshed)
        return
      }
      resetSelection()
      return
    }
    if (list.length) {
      selectPrompt(list[0])
    }
  },
  { immediate: true },
)

const resetSelection = () => {
  selectedPrompt.value = null
  editForm.name = ''
  editForm.title = ''
  editForm.content = ''
  editForm.tags = []
}

const selectPrompt = (prompt: PromptItem) => {
  selectedPrompt.value = prompt
  editForm.name = prompt.name
  editForm.title = prompt.title || ''
  editForm.content = prompt.content
  editForm.tags = normalizeTags(prompt.tags)
}

const savePrompt = async () => {
  if (!selectedPrompt.value) return
  const normalizedTags = normalizeTags(editForm.tags)
  const validationError = validatePromptPayload({
    title: editForm.title,
    content: editForm.content,
    tags: normalizedTags
  })
  if (validationError) {
    showAlert(validationError, 'error')
    return
  }
  editForm.tags = normalizedTags
  const normalizedTitle = editForm.title.trim()
  try {
    const updated = await updatePromptMutation.mutateAsync({
      id: selectedPrompt.value.id,
      data: {
        title: normalizedTitle || undefined,
        content: editForm.content,
        tags: normalizedTags
      },
    })
    selectPrompt(updated)
    showAlert('保存成功', 'success')
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '保存失败', 'error')
  }
}

const deletePrompt = async () => {
  if (!selectedPrompt.value) return
  try {
    await deletePromptMutation.mutateAsync(selectedPrompt.value.id)
    showAlert('删除成功', 'success')
    resetSelection()
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '删除失败', 'error')
  }
}

const openCreateModal = () => {
  createModalVisible.value = true
}

const closeCreateModal = () => {
  createModalVisible.value = false
  createForm.name = ''
  createForm.title = ''
  createForm.content = ''
  createForm.tags = []
}

const createPrompt = async () => {
  const normalizedName = createForm.name.trim()
  const nameError = validateName(normalizedName)
  if (nameError) {
    showAlert(nameError, 'error')
    return
  }
  if (prompts.value.some((item) => item.name.toLowerCase() === normalizedName.toLowerCase())) {
    showAlert('该名称已存在，请使用新的唯一标识', 'error')
    return
  }

  const normalizedTags = normalizeTags(createForm.tags)
  const validationError = validatePromptPayload({
    title: createForm.title,
    content: createForm.content,
    tags: normalizedTags
  })
  if (validationError) {
    showAlert(validationError, 'error')
    return
  }

  createForm.tags = normalizedTags
  try {
    const created = await createPromptMutation.mutateAsync({
      name: normalizedName,
      title: createForm.title?.trim() || undefined,
      content: createForm.content,
      tags: normalizedTags.length ? normalizedTags : undefined
    })
    prompts.value.unshift(created)
    selectPrompt(created)
    showAlert('创建成功', 'success')
    closeCreateModal()
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '创建失败', 'error')
  }
}

</script>

<style scoped>
.prompt-layout {
  display: flex;
  align-items: stretch;
  gap: 20px;
  min-height: 420px;
  margin-top: var(--md-spacing-4);
}

.prompt-layout.mobile {
  flex-direction: column;
}

.prompt-sidebar {
  width: 300px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background-color: var(--md-surface-container-low);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-lg);
  padding: 12px;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  padding: 0 2px;
}

.sidebar-title {
  font-size: 0.85rem;
  color: var(--md-on-surface-variant);
  font-weight: 600;
  letter-spacing: 0.02em;
}

.prompt-layout.mobile .prompt-sidebar {
  width: 100%;
  max-height: 260px;
}

.prompt-scroll {
  max-height: 520px;
  padding-right: 2px;
}

.prompt-layout.mobile .prompt-scroll {
  max-height: 210px;
}

.prompt-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.prompt-list-item {
  width: 100%;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-sm);
  background-color: var(--md-surface);
  padding: 10px 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  cursor: pointer;
  text-align: left;
  transition:
    border-color 0.15s ease,
    background-color 0.15s ease,
    color 0.15s ease;
}

.prompt-list-item:hover {
  border-color: var(--md-primary);
  background-color: var(--md-surface-container);
}

.prompt-list-item.active {
  border-color: var(--md-primary);
  background-color: var(--md-primary-container);
}

.prompt-item-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.prompt-item-title {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  font-size: 0.92rem;
  font-weight: 600;
  color: var(--md-on-surface);
}

.prompt-item-key {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  font-size: 0.78rem;
  color: var(--md-on-surface-variant);
}

.prompt-item-meta {
  font-size: 0.75rem;
  color: var(--md-on-surface-variant);
  flex-shrink: 0;
}

.prompt-list-item:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}

.prompt-list-item:active {
  transform: translateY(0);
}

.prompt-list-item :deep(.n-tag) {
  flex-shrink: 0;
}

.prompt-editor {
  flex: 1;
  min-width: 0;
}

.empty-editor {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 0;
}

.editor-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.prompt-textarea :deep(textarea) {
  font-family: var(--md-font-mono);
  font-size: 14px;
  line-height: 1.5;
}

.prompt-modal {
  max-width: min(720px, 90vw);
}

.prompt-status-list strong,
.prompt-status-list span {
  display: block;
}

.prompt-status-list strong {
  color: var(--md-on-surface);
  font-size: var(--md-label-large);
  overflow-wrap: anywhere;
}

.prompt-status-list span {
  margin-top: 4px;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
  line-height: 1.5;
}

@media (max-width: 1199px) {
  .prompt-sidebar {
    width: 260px;
  }
}

</style>
