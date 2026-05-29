<!-- AIMETA P=用户管理_用户列表管理|R=用户CRUD_权限|NR=不含认证功能|E=component:UserManagement|X=ui|A=用户组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <section class="admin-panel admin-panel--list">
    <div class="admin-panel__body">
      <n-alert v-if="error" type="error" closable @close="error = null">
        {{ error }}
      </n-alert>

      <n-spin :show="loading">
        <div class="admin-ops">
          <!-- 顶部三块指标卡片 -->
          <div class="admin-metrics-grid">
            <!-- 用户总数 -->
            <!-- 用户总数 -->
            <article 
              class="metric-card clickable-card"
              :class="{ 'is-active-all': activeFilter === 'all' }"
              @click="clearCardFilter"
            >
              <p class="metric-card-title">用户总数</p>
              <strong class="metric-card-number">{{ users.length }}</strong>
              <span class="metric-card-desc">当前已注册的账号库规模。</span>
            </article>

            <!-- 权限分布 -->
            <article class="metric-card">
              <header class="metric-card-header-simple">
                <h3>权限分布</h3>
                <p>快速确认后台权限是否集中。</p>
              </header>
              <ul class="admin-insight-list user-status-list">
                <li 
                  class="filterable-item"
                  :class="{ 'is-active': activeFilter === 'admin' }"
                  @click="handleFilterToggle('admin')"
                >
                  <strong>{{ adminUsers.length }} 个管理员</strong>
                  <span>管理员账号不能在列表中直接删除。</span>
                </li>
                <li 
                  class="filterable-item"
                  :class="{ 'is-active': activeFilter === 'regular' }"
                  @click="handleFilterToggle('regular')"
                >
                  <strong>{{ users.length - adminUsers.length }} 个普通用户</strong>
                  <span>普通用户可按需编辑或停用。</span>
                </li>
              </ul>
            </article>

            <!-- 状态巡检 -->
            <article class="metric-card">
              <header class="metric-card-header-simple">
                <h3>状态巡检</h3>
                <p>删除前先确认停用账号是否仍需保留材料。</p>
              </header>
              <ul class="admin-insight-list user-status-list">
                <li 
                  class="filterable-item"
                  :class="{ 'is-active': activeFilter === 'active' }"
                  @click="handleFilterToggle('active')"
                >
                  <strong>{{ activeUsers.length }} 个启用账号</strong>
                  <span>可正常进入写作工作台。</span>
                </li>
                <li 
                  class="filterable-item"
                  :class="{ 'is-active': activeFilter === 'disabled' }"
                  @click="handleFilterToggle('disabled')"
                >
                  <strong>{{ disabledUsers.length }} 个禁用账号</strong>
                  <span>登录受限，历史项目仍保留。</span>
                </li>
              </ul>
            </article>
          </div>

          <!-- 账号清册及表格控制栏 -->
          <article class="table-card">
            <header class="table-card-header">
              <div class="table-card-title-group">
                <h3>账号清册</h3>
                <p>表格与移动卡片共用同一批账号数据。</p>
              </div>
              <div class="table-card-actions">
                <n-input
                  v-model:value="keyword"
                  clearable
                  placeholder="搜索用户名或邮箱"
                  @update:value="handleSearch"
                  class="search-input"
                />
                <n-button type="primary" class="md-btn-filled" size="small" @click="handleAdd"> 新建用户 </n-button>
                <n-button quaternary class="md-btn-outlined" size="small" @click="fetchUsers" :loading="loading"> 刷新 </n-button>
              </div>
            </header>
            
            <div class="table-card-body">
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
              <MofengTable
                v-else
                :columns="columns"
                :data="filteredUsers"
                :pagination="pagination"
                :row-key="rowKey"
                :row-props="rowProps"
                class="user-table"
              />
            </div>
          </article>
        </div>
      </n-spin>
    </div>

    <!-- Create/Edit User Modal -->
    <n-modal
      v-model:show="showModal"
      preset="card"
      :closable="false"
      :mask-closable="true"
      :style="{ width: 'min(500px, 92vw)' }"
      class="custom-mofeng-modal"
    >
      <template #header>
        <div class="custom-modal-header">
          <span class="custom-modal-title">
            <span class="title-first-char">{{ modalTitleFirstChar }}</span>{{ modalTitleRest }}
          </span>
          <n-button
            type="primary"
            class="custom-save-btn"
            :loading="submitting"
            @click="handleSubmit"
          >
            存
          </n-button>
        </div>
      </template>

      <n-form
        ref="formRef"
        :model="formModel"
        :rules="rules"
        label-placement="left"
        label-width="80"
        require-mark-placement="right-hanging"
      >
        <n-form-item label="用户名" path="username">
          <span class="static-value-text" v-if="isEditMode">{{ formModel.username }}</span>
          <n-input
            v-else
            v-model:value="formModel.username"
            placeholder="请输入用户名"
            :input-props="{ autocomplete: 'off' }"
          />
        </n-form-item>
        <n-form-item label="邮箱" path="email">
          <span class="static-value-text" v-if="isEditMode">{{ formModel.email || '未设置' }}</span>
          <n-input
            v-else
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
        
        <div class="form-row-inline">
          <n-form-item label="权限" path="is_admin" class="form-col-inline">
            <n-switch v-model:value="formModel.is_admin" :disabled="!isEditMode">
              <template #checked>管理员</template>
              <template #unchecked>普通用户</template>
            </n-switch>
          </n-form-item>
          <n-form-item label="状态" path="is_active" class="form-col-inline">
            <n-switch v-model:value="formModel.is_active">
              <template #checked>激活</template>
              <template #unchecked>禁用</template>
            </n-switch>
          </n-form-item>
        </div>
      </n-form>
    </n-modal>
  </section>
</template>

<script setup lang="ts">
import { computed, h, reactive, ref, watch } from 'vue'
import { NAlert } from 'naive-ui/es/alert'
import { NButton } from 'naive-ui/es/button'
import { NEmpty } from 'naive-ui/es/empty'
import MofengTable from '@/components/shared/MofengTable.vue'
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
import { useResponsiveViewport } from '@/composables/useResponsiveViewport'
import { mobileMax } from '@/constants/responsive'
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
const adminUsers = computed(() => users.value.filter((user) => user.is_admin))
const activeUsers = computed(() => users.value.filter((user) => user.is_active))
const disabledUsers = computed(() => users.value.filter((user) => !user.is_active))
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
const activeFilter = ref<'all' | 'admin' | 'regular' | 'active' | 'disabled'>('all')

const handleFilterToggle = (filterType: 'admin' | 'regular' | 'active' | 'disabled') => {
  if (activeFilter.value === filterType) {
    activeFilter.value = 'all'
  } else {
    activeFilter.value = filterType
  }
  pagination.page = 1
}

const clearCardFilter = () => {
  activeFilter.value = 'all'
  pagination.page = 1
}

const handleToggleStatus = async (row: AdminUser, newValue: boolean) => {
  try {
    const payload: UserUpdatePayload = {
      username: row.username,
      is_admin: row.is_admin,
      is_active: newValue,
    }
    if (row.email) payload.email = row.email
    
    await updateUserMutation.mutateAsync({ id: row.id, data: payload })
    message.success(`${newValue ? '激活' : '禁用'}成功`)
  } catch (err) {
    message.error(err instanceof Error ? err.message : '切换状态失败')
    fetchUsers()
  }
}

const rowProps = (row: AdminUser) => {
  return {
    style: 'cursor: pointer;',
    onDblclick: () => {
      handleEdit(row)
    }
  }
}
const viewport = useResponsiveViewport()
const isMobile = computed(() => viewport.width.value <= mobileMax)

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
    render(row) {
      return h('div', { class: 'username-cell-custom' }, [
        row.is_admin ? h('span', { class: 'admin-seal-custom' }, '管') : null,
        h('span', { class: 'username-text-custom' }, row.username)
      ])
    }
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
    title: '状态',
    key: 'is_active',
    align: 'center',
    render(row) {
      return h(
        NSwitch,
        {
          value: row.is_active,
          onUpdateValue: (val: boolean) => handleToggleStatus(row, val)
        }
      )
    },
  },
  {
    title: '操作',
    key: 'actions',
    align: 'center',
    render(row) {
      return h(
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
      )
    },
  },
]

const filteredUsers = computed(() => {
  let list = users.value

  if (activeFilter.value === 'admin') {
    list = list.filter((user) => user.is_admin)
  } else if (activeFilter.value === 'regular') {
    list = list.filter((user) => !user.is_admin)
  } else if (activeFilter.value === 'active') {
    list = list.filter((user) => user.is_active)
  } else if (activeFilter.value === 'disabled') {
    list = list.filter((user) => !user.is_active)
  }

  if (!keyword.value.trim()) {
    return list
  }
  const q = keyword.value.trim().toLowerCase()
  return list.filter(
    (user) =>
      user.username.toLowerCase().includes(q) ||
      (user.email && user.email.toLowerCase().includes(q)),
  )
})

const modalTitleFirstChar = computed(() => (isEditMode.value ? '编' : '新'))
const modalTitleRest = computed(() => (isEditMode.value ? `辑用户 · ${formModel.username}` : '建用户'))

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

</script>

<style scoped>
.search-input {
  width: min(230px, 60vw);
}

.empty-state {
  padding: var(--md-spacing-8) 0;
}

.admin-metrics-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--md-spacing-4);
  margin-top: var(--md-spacing-2);
  margin-bottom: var(--md-spacing-2);
}

.table-card {
  margin-top: 0;
  border: none !important;
  background: transparent !important;
  box-shadow: none !important;
  padding: 0 !important;
}

/* 国风单细线指标卡片样式 */
.metric-card {
  padding: var(--md-spacing-4);
  border-radius: var(--md-radius-xs) !important; /* 极窄 2px 直角 */
  border: 1px solid var(--md-outline) !important; /* 竹青细线 */
  background-color: var(--md-surface-container-low) !important; /* 熟宣暖灰 */
  box-shadow: 2px 2px 0px rgba(28, 32, 34, 0.05) !important;
  transition: all var(--md-duration-medium) var(--md-easing-standard) !important;
}

.metric-card:hover {
  transform: translate(-1px, -1px);
  border-color: var(--md-secondary) !important;
  box-shadow: 3px 3px 0px rgba(184, 60, 50, 0.15) !important; /* 朱砂压影 */
}

/* 激活状态 */
.clickable-card {
  cursor: pointer;
}

.clickable-card.is-active-all {
  border-color: var(--md-primary) !important;
  box-shadow: 3px 3px 0px rgba(28, 32, 34, 0.15) !important;
  background-color: var(--md-surface-container) !important;
}

.metric-card-title {
  margin: 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
  font-family: var(--md-font-serif) !important;
}

.metric-card-number {
  margin: var(--md-spacing-2) 0 5px;
  display: block;
  color: var(--md-primary);
  font-family: var(--md-font-mono) !important;
  font-size: var(--md-display-small) !important;
  font-weight: 600 !important;
}

.metric-card-desc {
  margin: 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
  font-family: var(--md-font-kai) !important;
}

.metric-card-header-simple h3 {
  margin: 0;
  color: var(--md-on-surface);
  font-family: var(--md-font-display) !important;
  font-size: var(--md-title-medium) !important;
  letter-spacing: 0.05em !important;
}

.metric-card-header-simple p {
  margin: 4px 0 0;
  color: var(--md-on-surface-variant);
  font-family: var(--md-font-kai) !important;
  font-size: var(--md-body-small);
}

.filterable-item {
  cursor: pointer;
  transition: all var(--md-duration-short) var(--md-easing-standard);
}

.filterable-item:hover {
  border-color: var(--md-primary-light);
  background-color: var(--md-surface-container);
}

.filterable-item.is-active {
  border-color: var(--md-secondary) !important;
  background-color: var(--md-secondary-container) !important;
  box-shadow: 2px 2px 0px rgba(184, 60, 50, 0.15);
}

/* 朱印管理员印章 */
:deep(.username-cell-custom) {
  display: inline-flex;
  align-items: center;
  gap: var(--md-spacing-2);
}

:deep(.admin-seal-custom) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  line-height: 18px;
  background-color: var(--md-secondary); /* 朱砂红 */
  color: var(--md-on-primary);
  font-size: 11px;
  font-family: var(--md-font-display);
  font-weight: bold;
  border-radius: 2px; /* 小方章微圆角 */
  box-shadow: 1px 1px 0px rgba(184, 60, 50, 0.3); /* 印章印泥压印感 */
  user-select: none;
  flex-shrink: 0;
}

:deep(.username-text-custom) {
  font-weight: 600;
  color: var(--md-on-surface);
}

/* 乾坤万象中枢定制：弹窗自定义 Header */
.custom-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  padding-bottom: var(--md-spacing-3);
  border-bottom: 1px dashed var(--md-outline-variant);
}

.custom-modal-title {
  font-family: var(--md-font-display);
  font-size: var(--md-title-large);
  color: var(--md-primary); /* 在暗色模式下会自动使用素骨黄，明色下使用松烟 */
  letter-spacing: 0.05em;
  font-weight: 600;
}

/* 乾坤万象风格首字朱红 */
.title-first-char {
  color: var(--md-secondary) !important; /* 朱砂红 */
  margin-right: 2px;
}

/* 黑色主题及白色主题下表单文字可见度增强 */
:deep(.n-form-item-label) {
  color: var(--md-on-surface) !important; /* 松烟 / 素骨黄 */
  font-weight: 600 !important;
  transition: color var(--md-duration-medium) var(--md-easing-standard) !important;
}

/* 禁用修改项去框线样式 */
.static-value-text {
  display: inline-block;
  padding: 4px 0;
  font-family: var(--md-font-family);
  font-size: var(--md-body-large);
  color: var(--md-on-surface-variant);
  user-select: text;
}

/* 权限与状态并排在一行 */
.form-row-inline {
  display: flex;
  gap: var(--md-spacing-6);
  width: 100%;
}

.form-col-inline {
  flex: 1;
  min-width: 0;
}

/* “存”字印章式红色小方章按钮 */
.custom-save-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  min-width: 32px;
  padding: 0;
  border-radius: var(--md-radius-xs) !important; /* 2px */
  background-color: var(--md-secondary) !important; /* 朱砂红 */
  color: var(--md-on-primary) !important;
  font-family: var(--md-font-display) !important;
  font-size: var(--md-label-large) !important;
  font-weight: bold !important;
  border: 1px solid var(--md-outline) !important;
  box-shadow: 1px 1px 0px rgba(184, 60, 50, 0.25) !important;
  cursor: pointer;
  transition: all var(--md-duration-short) var(--md-easing-standard) !important;
}

.custom-save-btn:hover:not(:disabled) {
  background-color: var(--md-secondary-light) !important;
  box-shadow: 2px 2px 0px rgba(184, 60, 50, 0.35) !important;
  transform: translate(-0.5px, -0.5px);
}

.custom-save-btn:active:not(:disabled) {
  transform: translate(0.5px, 0.5px);
  box-shadow: none !important;
}

/* 自定义 Modal 单线框化，去除冗余双线 */
:deep(.custom-mofeng-modal) {
  border: 1px solid var(--md-outline) !important;
  border-radius: var(--md-radius-sm) !important; /* 4px */
  background-color: var(--md-surface) !important;
  box-shadow: var(--md-elevation-3) !important;
}

.table-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--md-spacing-4);
  flex-wrap: wrap;
  padding-bottom: var(--md-spacing-4);
  border-bottom: 1px dashed var(--md-outline-variant);
  margin-bottom: var(--md-spacing-4);
}

.table-card-title-group h3 {
  margin: 0;
  color: var(--md-on-surface);
  font-family: var(--md-font-display);
  font-size: var(--md-title-medium);
  letter-spacing: 0.05em;
}

.table-card-title-group p {
  margin: 6px 0 0;
  color: var(--md-on-surface-variant);
  font-family: var(--md-font-kai);
  font-size: var(--md-body-small);
}

.table-card-actions {
  display: flex;
  align-items: center;
  gap: var(--md-spacing-3);
  flex-wrap: wrap;
}

.table-card-body {
  margin-top: var(--md-spacing-3);
}

.user-status-list strong,
.user-status-list span {
  display: block;
}

.user-status-list strong {
  color: var(--md-on-surface);
  font-size: var(--md-label-large);
}

.user-status-list span {
  margin-top: 4px;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
  line-height: 1.5;
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

@media (max-width: 833px) {
  .search-input {
    width: 100%;
  }

  .user-mobile-card__header {
    align-items: flex-start;
    flex-direction: column;
  }
  
  .admin-metrics-grid {
    grid-template-columns: 1fr;
  }
  
  .table-card-header {
    flex-direction: column;
    align-items: stretch;
  }
  
  .table-card-actions {
    width: 100%;
    justify-content: stretch;
  }
  
  .table-card-actions > * {
    flex: 1 1 100%;
  }
}
</style>
