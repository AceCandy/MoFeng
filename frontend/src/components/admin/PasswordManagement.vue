<!-- AIMETA P=密码管理_管理员密码修改|R=密码修改表单|NR=不含用户管理|E=component:PasswordManagement|X=ui|A=密码组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <section class="admin-panel password-container">
    <div class="admin-panel__body">
      <n-alert v-if="mustReset" type="warning" class="mb-4">
        为保障安全，请先更新默认密码后再继续使用管理后台。
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
                placeholder="请输入当前管理员密码"
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

            <n-space v-if="!isModal" justify="end">
              <n-button type="primary" :loading="submitting" @click="handleSubmit">
                保存新密码
              </n-button>
            </n-space>
          </n-form>

          <div class="password-sidebar-note">
            <div class="note-seal">密</div>
            <span class="note-main">更替密契 · 慎防外泄</span>
            <span class="note-sub">司天监起居注</span>
          </div>
        </div>
      </n-spin>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'

interface Props {
  isModal?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  isModal: false
})

const emit = defineEmits<{
  (e: 'saved'): void
}>()
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
    emit('saved')
    await showAlert('密码已更新，请使用新密码继续操作', 'success')
  } catch (err) {
    formError.value = err instanceof Error ? err.message : '密码更新失败'
  }
}

defineExpose({
  submit: handleSubmit,
  submitting,
})
</script>

<style scoped>
.password-container {
  max-width: 520px;
  margin: 0 auto;
  color: var(--md-on-surface);
}

.password-layout {
  display: flex;
  gap: 24px;
  align-items: stretch;
}

.password-form {
  flex: 1;
  max-width: 350px;
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

/* 移除输入框原有的现代直角/圆角封闭外框，阴影和背景色填充 */
:deep(.n-input) {
  background-color: transparent !important;
  box-shadow: none !important;
  --n-box-shadow-focus: none !important;
  /* 强制清除其他三边边框，仅保留底部乌丝栏下划线 */
  border: none !important;
  border-bottom: 1.5px solid var(--md-outline) !important;
  border-radius: 0 !important;
  transition: border-bottom-color var(--md-duration-short, 140ms) var(--md-easing-standard, ease-in-out) !important;
}

:deep(.n-input.n-input--focus) {
  border-bottom-color: var(--md-secondary) !important;
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

/* 校验失败（error）状态的底线 */
:deep(.n-input.n-input--error-status) {
  border-bottom-color: var(--md-error) !important;
}

/* 禁用（disabled）状态的样式 */
:deep(.n-input.n-input--disabled) {
  border-bottom-color: var(--md-outline-variant) !important;
  opacity: 0.5 !important;
  cursor: not-allowed !important;
}

/* 右侧古典起居栏侧栏竖排美化 */
.password-sidebar-note {
  writing-mode: vertical-rl;
  text-orientation: mixed;
  padding: 16px 12px;
  user-select: none;
  min-width: 90px;
  text-align: left;
  border-left: 1px dashed var(--md-outline) !important;
}

/* 朱印阳刻金石微方章 */
.password-sidebar-note .note-seal {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  background-color: var(--md-secondary, #b83c32) !important;
  color: var(--md-on-secondary, #faf6ed) !important;
  font-family: var(--md-font-serif) !important;
  font-size: 11px !important;
  font-weight: 900 !important;
  border: 1px solid var(--md-outline) !important;
  box-shadow: 1.5px 1.5px 0px rgba(184, 60, 50, 0.25) !important;
  transform: rotate(-4deg);
  margin-bottom: 12px;
  margin-left: 4px;
}

.password-sidebar-note .note-main {
  display: inline;
  font-family: var(--md-font-serif) !important;
  font-size: 14px;
  font-weight: 600;
  color: var(--md-on-surface-variant);
  letter-spacing: 0.18em;
}

.password-sidebar-note .note-sub {
  display: block; /* 另起一列，实现完美的双列竖排 */
  font-family: var(--md-font-serif) !important;
  font-size: 11px;
  color: var(--md-outline);
  letter-spacing: 0.12em;
  margin-top: 14px; /* 竖向排版换列之后的顶部缩进，产生落款错落感 */
  margin-right: 8px; /* 列与列的间隔 */
  opacity: 0.85;
}

/* 移动端/窄视口下自适应响应式，优雅隐去侧栏并拉满表单 */
@media (max-width: 480px) {
  .password-sidebar-note {
    display: none !important;
  }
  .password-form {
    max-width: 100% !important;
  }
}
</style>
