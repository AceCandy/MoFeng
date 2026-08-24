<!-- AIMETA P=账户安全_登录密码修改|R=密码修改表单|NR=不含用户管理|E=component:PasswordManagement|X=ui|A=密码组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <section class="admin-panel password-container">
    <div class="admin-panel__body">
      <n-alert v-if="mustReset" type="warning" class="mb-4">
        为保障账户安全，请先更新默认密码。
      </n-alert>

      <n-alert v-if="error" type="error" closable @close="error = null" class="mb-4">
        {{ error }}
      </n-alert>

      <n-spin :show="submitting">
        <div class="password-layout">
          <n-form class="password-form" label-placement="top" @submit.prevent="handleSubmit">
            <n-form-item label="当前密码">
              <n-input
                v-model:value="form.oldPassword"
                type="password"
                show-password-on="click"
                placeholder="请输入当前密码"
                autocomplete="current-password"
              />
            </n-form-item>

            <n-form-item label="新密码">
              <n-input
                v-model:value="form.newPassword"
                type="password"
                show-password-on="click"
                placeholder="请输入至少 8 位新密码"
                autocomplete="new-password"
              />
            </n-form-item>

            <n-form-item label="确认新密码">
              <n-input
                v-model:value="form.confirmPassword"
                type="password"
                show-password-on="click"
                placeholder="请再次输入新密码"
                autocomplete="new-password"
              />
            </n-form-item>

            <n-space justify="end">
              <n-button type="primary" :loading="submitting" @click="handleSubmit">
                保存新密码
              </n-button>
            </n-space>
          </n-form>
        </div>
      </n-spin>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'

import { useQueryClient } from '@tanstack/vue-query'
import { NAlert } from 'naive-ui/es/alert'
import { NButton } from 'naive-ui/es/button'
import { NForm, NFormItem } from 'naive-ui/es/form'
import { NInput } from 'naive-ui/es/input'
import { NSpace } from 'naive-ui/es/space'
import { NSpin } from 'naive-ui/es/spin'

import { useAlert } from '@/composables/useAlert'
import { useAuthStore } from '@/stores/auth'
import { useChangePasswordMutation } from '@/queries/admin'
import { currentUserQueryOptions } from '@/queries/auth'

const authStore = useAuthStore()
const queryClient = useQueryClient()
const { showAlert } = useAlert()
const changePasswordMutation = useChangePasswordMutation()

const form = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})

const submitting = computed(() => changePasswordMutation.isPending.value)
const formError = ref<string | null>(null)
const error = computed({
  get: () => {
    if (formError.value) return formError.value
    const mutationError = changePasswordMutation.error.value
    return mutationError instanceof Error ? mutationError.message : mutationError ? String(mutationError) : null
  },
  set: (value) => {
    formError.value = value
  },
})

const mustReset = computed(() => authStore.mustChangePassword && authStore.user?.is_admin)

const resetForm = () => {
  form.oldPassword = ''
  form.newPassword = ''
  form.confirmPassword = ''
}

const handleSubmit = async () => {
  formError.value = null
  changePasswordMutation.reset()

  if (!form.oldPassword.trim() || !form.newPassword.trim()) {
    formError.value = '请填写完整的密码信息'
    return
  }

  if (form.newPassword.length < 8) {
    formError.value = '新密码长度需至少 8 位'
    return
  }

  if (form.newPassword === form.oldPassword) {
    formError.value = '新密码不能与当前密码相同'
    return
  }

  if (form.newPassword !== form.confirmPassword) {
    formError.value = '两次输入的新密码不一致'
    return
  }

  try {
    await changePasswordMutation.mutateAsync({
      oldPassword: form.oldPassword,
      newPassword: form.newPassword,
    })
    const user = await queryClient.fetchQuery(currentUserQueryOptions(authStore.token))
    authStore.setUser(user)
    resetForm()
    await showAlert('密码已更新，请使用新密码继续操作', 'success')
  } catch (err) {
    formError.value = err instanceof Error ? err.message : '密码更新失败'
  }
}

</script>

<style scoped>
.password-container {
  max-width: 520px;
  margin: 0 auto;
  color: var(--md-on-surface);
}

.password-layout {
  display: block;
}

.password-form {
  max-width: 420px;
  margin: 0 auto;
}

.mb-4 {
  margin-bottom: var(--md-spacing-4);
}

/* 调整表单字段标题 (Label) 呈现空灵错落的中式信笺布局 */
:deep(.n-form-item-label) {
  font-family: var(--md-font-serif) !important;
  color: var(--md-on-surface-variant) !important;
  font-weight: 600 !important;
  font-size: var(--md-body-medium) !important;
  padding-bottom: 8px !important;
  letter-spacing: 0.06em !important;
}

/* 输入框：竹青细框、微直角，聚焦时焦墨框线加浮起纸页影 */
:deep(.n-input) {
  background-color: transparent !important;
  box-shadow: none !important;
  --n-box-shadow-focus: none !important;
  border: 1px solid var(--md-outline) !important;
  border-radius: var(--md-radius-xs) !important;
  transition:
    border-color var(--md-duration-short, 140ms) var(--md-easing-standard, ease-in-out),
    box-shadow var(--md-duration-short, 140ms) var(--md-easing-standard, ease-in-out) !important;
}

:deep(.n-input.n-input--focus) {
  border-color: var(--md-primary) !important;
  box-shadow: var(--md-elevation-paper-1) !important;
}

:deep(.n-input .n-input__border),
:deep(.n-input .n-input__state-border) {
  border: none !important;
}

/* 微调右侧密码显示/隐藏切换图标的排版与颜色 */
:deep(.n-input__suffix) {
  color: var(--md-on-surface-variant) !important;
  transition: color var(--md-duration-short, 140ms) var(--md-easing-standard, ease-in-out) !important;
}

:deep(.n-input__suffix:hover) {
  color: var(--md-primary) !important;
}

/* 校验失败（error）状态的框线 */
:deep(.n-input.n-input--error-status) {
  border-color: var(--md-error) !important;
}

/* 禁用（disabled）状态的样式 */
:deep(.n-input.n-input--disabled) {
  border-color: var(--md-outline-variant) !important;
  opacity: 0.5 !important;
  cursor: not-allowed !important;
}

</style>
