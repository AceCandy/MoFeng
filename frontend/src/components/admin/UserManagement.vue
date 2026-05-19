<!-- AIMETA P=用户管理_用户列表管理|R=用户CRUD_权限|NR=不含认证功能|E=component:UserManagement|X=ui|A=用户组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <section class="admin-panel admin-panel--list">
    <div class="admin-panel__header admin-panel__header--toolbar">
      <n-space :size="12" class="admin-panel__actions">
        <n-input
          v-model:value="keyword"
          clearable
          round
          placeholder="搜索用户名或邮箱"
          @update:value="handleSearch"
          class="search-input"
        />
        <n-button type="primary" size="small" @click="handleAdd"> 新建用户 </n-button>
        <n-button quaternary size="small" @click="fetchUsers" :loading="loading"> 刷新 </n-button>
      </n-space>
    </div>

    <div class="admin-panel__body">
      <n-alert v-if="error" type="error" closable @close="error = null">
        {{ error }}
      </n-alert>

      <n-spin :show="loading">
        <div class="admin-table-shell">
          <n-empty
            v-if="!filteredUsers.length && !loading"
            description="暂无匹配用户"
            class="empty-state"
          />
          <div v-else-if="isMobile" class="user-mobile-list">
            <article v-for="user in filteredUsers" :key="user.id" class="user-mobile-card">
              <div class="user-mobile-card__header">
                <div class="user-mobile-card__identity">
                  <strong>{{ user.username }}</strong>
                  <span>ID {{ user.id }}</span>
                </div>
                <n-space :size="6">
                  <n-tag :type="user.is_admin ? 'success' : 'default'" :bordered="false" size="small">
                    {{ user.is_admin ? '管理员' : '普通用户' }}
                  </n-tag>
                  <n-tag :type="user.is_active ? 'success' : 'error'" :bordered="false" size="small">
                    {{ user.is_active ? '激活' : '禁用' }}
                  </n-tag>
                </n-space>
              </div>

              <div class="user-mobile-card__meta">
                <span>邮箱</span>
                <strong>{{ user.email || '未设置' }}</strong>
              </div>

              <div class="user-mobile-card__actions">
                <n-button size="small" type="primary" secondary @click="handleEdit(user)">
                  编辑
                </n-button>
                <n-popconfirm :disabled="user.is_admin" @positive-click="() => handleDelete(user.id)">
                  <template #trigger>
                    <n-button size="small" type="error" secondary :disabled="user.is_admin">
                      删除
                    </n-button>
                  </template>
                  确定要删除该用户吗？
                </n-popconfirm>
              </div>
            </article>
          </div>
          <n-data-table
            v-else
            :columns="columns"
            :data="filteredUsers"
            :bordered="false"
            :pagination="pagination"
            :row-key="rowKey"
            class="user-table"
          />
        </div>
      </n-spin>
    </div>

    <!-- Create/Edit User Modal -->
    <n-modal
      v-model:show="showModal"
      preset="card"
      :title="modalTitle"
      :style="{ width: 'min(500px, 92vw)' }"
    >
      <n-form
        ref="formRef"
        :model="formModel"
        :rules="rules"
        label-placement="left"
        label-width="80"
        require-mark-placement="right-hanging"
      >
        <n-form-item label="用户名" path="username">
          <n-input
            v-model:value="formModel.username"
            placeholder="请输入用户名"
            :input-props="{ autocomplete: 'off' }"
          />
        </n-form-item>
        <n-form-item label="邮箱" path="email">
          <n-input
            v-model:value="formModel.email"
            placeholder="请输入邮箱（可选）"
            :input-props="{ autocomplete: 'off' }"
          />
        </n-form-item>
        <n-form-item
          label="密码"
          path="password"
          :rule="
            isEditMode ? [{ min: 6, message: '密码至少 6 个字符', trigger: 'blur' }] : passwordRules
          "
        >
          <n-input
            v-model:value="formModel.password"
            type="password"
            show-password-on="click"
            :placeholder="isEditMode ? '不修改请留空' : '请输入密码'"
            :input-props="{ autocomplete: 'new-password' }"
          />
        </n-form-item>
        <n-form-item label="权限" path="is_admin">
          <n-switch v-model:value="formModel.is_admin" :disabled="!isEditMode">
            <template #checked>管理员</template>
            <template #unchecked>普通用户</template>
          </n-switch>
        </n-form-item>
        <n-form-item label="状态" path="is_active">
          <n-switch v-model:value="formModel.is_active">
            <template #checked>激活</template>
            <template #unchecked>禁用</template>
          </n-switch>
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showModal = false">取消</n-button>
          <n-button type="primary" :loading="submitting" @click="handleSubmit"> 确认 </n-button>
        </n-space>
      </template>
    </n-modal>
  </section>
</template>

<script setup lang="ts">
import { computed, h, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { NAlert } from 'naive-ui/es/alert'
import { NButton } from 'naive-ui/es/button'
import { NDataTable } from 'naive-ui/es/data-table'
import { NEmpty } from 'naive-ui/es/empty'
import { NForm, NFormItem } from 'naive-ui/es/form'
import { NInput } from 'naive-ui/es/input'
import { useMessage } from 'naive-ui/es/message'
import { NModal } from 'naive-ui/es/modal'
import { NPopconfirm } from 'naive-ui/es/popconfirm'
import { NSpace } from 'naive-ui/es/space'
import { NSpin } from 'naive-ui/es/spin'
import { NSwitch } from 'naive-ui/es/switch'
import { NTag } from 'naive-ui/es/tag'
import type { DataTableColumns, FormInst, FormRules, FormItemRule } from 'naive-ui'

import type { AdminUser, UserCreatePayload, UserUpdatePayload } from '@/api/admin'
import {
  useAdminUsersQuery,
  useCreateAdminUserMutation,
  useDeleteAdminUserMutation,
  useUpdateAdminUserMutation,
} from '@/queries/admin'

const message = useMessage()
const usersQuery = useAdminUsersQuery()
const createUserMutation = useCreateAdminUserMutation()
const updateUserMutation = useUpdateAdminUserMutation()
const deleteUserMutation = useDeleteAdminUserMutation()
const users = computed<AdminUser[]>(() => usersQuery.data.value ?? [])
const loading = computed(() => usersQuery.isLoading.value || usersQuery.isFetching.value)
const isErrorDismissed = ref(false)
const error = computed({
  get: () => {
    if (isErrorDismissed.value) return null
    const queryError = usersQuery.error.value
    return queryError instanceof Error ? queryError.message : queryError ? String(queryError) : null
  },
  set: () => {
    isErrorDismissed.value = true
  },
})
const keyword = ref('')
const isMobile = ref(false)

const showModal = ref(false)
const isEditMode = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInst | null>(null)
const submitting = computed(
  () => createUserMutation.isPending.value || updateUserMutation.isPending.value,
)

const formModel = reactive({
  username: '',
  email: '',
  password: '',
  is_admin: false,
  is_active: true,
})

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, message: '用户名至少 2 个字符', trigger: 'blur' },
  ],
  email: [{ type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }],
}

const passwordRules: FormItemRule[] = [
  { required: true, message: '请输入密码', trigger: 'blur' },
  { min: 6, message: '密码至少 6 个字符', trigger: 'blur' },
]

const pagination = reactive({
  page: 1,
  pageSize: 10,
  showSizePicker: true,
  pageSizes: [10, 20, 50],
})

const updateLayout = () => {
  isMobile.value = window.innerWidth < 768
}

const columns: DataTableColumns<AdminUser> = [
  {
    title: 'ID',
    key: 'id',
    sorter: (a, b) => a.id - b.id,
    width: 80,
  },
  {
    title: '用户名',
    key: 'username',
    ellipsis: { tooltip: true },
  },
  {
    title: '邮箱',
    key: 'email',
    ellipsis: { tooltip: true },
    render(row) {
      return row.email || '—'
    },
  },
  {
    title: '权限',
    key: 'is_admin',
    align: 'center',
    render(row) {
      return h(
        NTag,
        {
          type: row.is_admin ? 'success' : 'default',
          bordered: false,
          size: 'small',
        },
        { default: () => (row.is_admin ? '管理员' : '普通用户') },
      )
    },
  },
  {
    title: '状态',
    key: 'is_active',
    align: 'center',
    render(row) {
      return h(
        NTag,
        {
          type: row.is_active ? 'success' : 'error',
          bordered: false,
          size: 'small',
        },
        { default: () => (row.is_active ? '激活' : '禁用') },
      )
    },
  },
  {
    title: '操作',
    key: 'actions',
    align: 'center',
    render(row) {
      return h(
        NSpace,
        { justify: 'center', size: 'small' },
        {
          default: () => [
            h(
              NButton,
              {
                size: 'small',
                type: 'primary',
                secondary: true,
                onClick: () => handleEdit(row),
              },
              { default: () => '编辑' },
            ),
            h(
              NPopconfirm,
              {
                onPositiveClick: () => handleDelete(row.id),
              },
              {
                trigger: () =>
                  h(
                    NButton,
                    {
                      size: 'small',
                      type: 'error',
                      secondary: true,
                      disabled: row.is_admin,
                    },
                    { default: () => '删除' },
                  ),
                default: () => '确定要删除该用户吗？',
              },
            ),
          ],
        },
      )
    },
  },
]

const filteredUsers = computed(() => {
  if (!keyword.value.trim()) {
    return users.value
  }
  const q = keyword.value.trim().toLowerCase()
  return users.value.filter(
    (user) =>
      user.username.toLowerCase().includes(q) ||
      (user.email && user.email.toLowerCase().includes(q)),
  )
})

const modalTitle = computed(() => (isEditMode.value ? '编辑用户' : '新建用户'))

const rowKey = (row: AdminUser) => row.id

const fetchUsers = () => {
  usersQuery.refetch()
}

watch(
  () => usersQuery.error.value,
  () => {
    isErrorDismissed.value = false
  },
)

const handleSearch = () => {
  pagination.page = 1
}

const handleAdd = () => {
  isEditMode.value = false
  editingId.value = null
  // 清空表单数据
  formModel.username = ''
  formModel.email = ''
  formModel.password = ''
  formModel.is_admin = false
  formModel.is_active = true

  showModal.value = true
}

const handleEdit = (row: AdminUser) => {
  isEditMode.value = true
  editingId.value = row.id
  formModel.username = row.username
  formModel.email = row.email || ''
  formModel.password = '' // 密码留空表示不修改
  formModel.is_admin = row.is_admin
  formModel.is_active = row.is_active
  showModal.value = true
}

const handleDelete = async (id: number) => {
  try {
    await deleteUserMutation.mutateAsync(id)
    message.success('删除成功')
  } catch (err) {
    message.error(err instanceof Error ? err.message : '删除失败')
  }
}

const handleSubmit = () => {
  formRef.value?.validate(async (errors) => {
    if (errors) return

    try {
      if (isEditMode.value && editingId.value) {
        const payload: UserUpdatePayload = {
          username: formModel.username,
          is_admin: formModel.is_admin,
          is_active: formModel.is_active,
        }
        if (formModel.email) payload.email = formModel.email
        if (formModel.password) payload.password = formModel.password

        await updateUserMutation.mutateAsync({ id: editingId.value, data: payload })
        message.success('更新成功')
      } else {
        const payload: UserCreatePayload = {
          username: formModel.username,
          password: formModel.password,
          is_admin: formModel.is_admin,
          is_active: formModel.is_active,
        }
        if (formModel.email) payload.email = formModel.email

        await createUserMutation.mutateAsync(payload)
        message.success('创建成功')
      }
      showModal.value = false
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败')
    }
  })
}

onMounted(() => {
  updateLayout()
  window.addEventListener('resize', updateLayout)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateLayout)
})
</script>

<style scoped>
.search-input {
  width: min(230px, 60vw);
}

.empty-state {
  padding: var(--md-spacing-8) 0;
}

.user-mobile-list {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-3);
}

.user-mobile-card {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-3);
  padding: var(--md-spacing-4);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-lg);
  background-color: var(--md-surface-container-low);
}

.user-mobile-card__header,
.user-mobile-card__meta,
.user-mobile-card__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--md-spacing-3);
}

.user-mobile-card__identity {
  min-width: 0;
}

.user-mobile-card__identity strong,
.user-mobile-card__identity span,
.user-mobile-card__meta span,
.user-mobile-card__meta strong {
  display: block;
}

.user-mobile-card__identity strong {
  overflow: hidden;
  color: var(--md-on-surface);
  font-size: var(--md-title-small);
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-mobile-card__identity span,
.user-mobile-card__meta span {
  margin-top: 2px;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.user-mobile-card__meta {
  align-items: flex-start;
  padding-top: var(--md-spacing-3);
  border-top: 1px solid var(--md-outline-variant);
}

.user-mobile-card__meta strong {
  min-width: 0;
  max-width: 64%;
  color: var(--md-on-surface);
  font-size: var(--md-body-medium);
  font-weight: 500;
  overflow-wrap: anywhere;
  text-align: right;
}

.user-mobile-card__actions {
  justify-content: flex-end;
}

@media (max-width: 767px) {
  .search-input {
    width: 100%;
  }

  .user-mobile-card__header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
