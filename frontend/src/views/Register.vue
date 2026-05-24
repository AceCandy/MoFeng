<!-- AIMETA P=注册页_用户注册|R=注册表单|NR=不含登录功能|E=route:/register#component:Register|X=ui|A=注册表单|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="register-page">
    <div class="register-brand">
      <TypewriterEffect text="墨风" />
    </div>

    <section v-if="allowRegistration" class="md-card md-card-elevated register-card">
      <div class="register-card__header">
        <h2>加入我们</h2>
        <p>开启您的创作新篇章</p>
      </div>

      <form @submit.prevent="handleRegister" class="register-form">
        <div class="md-text-field">
          <label for="username" class="md-text-field-label">用户名</label>
          <input
            v-model="username"
            id="username"
            name="username"
            type="text"
            required
            :aria-invalid="Boolean(error)"
            :aria-describedby="error ? 'register-error' : undefined"
            class="md-text-field-input"
            placeholder="请输入用户名"
            autocomplete="username"
            maxlength="64"
            spellcheck="false"
            autocapitalize="none"
          />
        </div>

        <div class="md-text-field">
          <label for="email" class="md-text-field-label">邮箱</label>
          <input
            v-model="email"
            id="email"
            name="email"
            type="email"
            required
            :aria-invalid="Boolean(error)"
            :aria-describedby="error ? 'register-error' : undefined"
            class="md-text-field-input"
            placeholder="请输入邮箱"
            autocomplete="email"
            maxlength="254"
            spellcheck="false"
            autocapitalize="none"
          />
        </div>

        <div class="register-code-row">
          <div class="md-text-field">
            <label for="verificationCode" class="md-text-field-label">验证码</label>
            <input
              v-model="verificationCode"
              id="verificationCode"
              name="verificationCode"
              type="text"
              required
              :aria-invalid="Boolean(error)"
              :aria-describedby="error ? 'register-error' : undefined"
              class="md-text-field-input"
              placeholder="请输入验证码"
              inputmode="numeric"
              autocomplete="one-time-code"
              maxlength="12"
              spellcheck="false"
              autocapitalize="none"
            />
          </div>
          <button
            type="button"
            @click="sendCode"
            :disabled="countdown > 0 || sending"
            class="md-ripple register-code-button"
          >
            <span v-if="sending">发送中...</span>
            <span v-else>{{ countdown > 0 ? countdown + '秒后重试' : '发送验证码' }}</span>
          </button>
        </div>

        <div class="md-text-field">
          <label for="password" class="md-text-field-label">密码</label>
          <input
            v-model="password"
            id="password"
            name="password"
            type="password"
            required
            :aria-invalid="Boolean(error)"
            :aria-describedby="error ? 'register-error' : undefined"
            class="md-text-field-input"
            placeholder="至少 8 个字符"
            autocomplete="new-password"
            minlength="8"
            maxlength="256"
          />
        </div>

        <Transition name="ink-fade">
          <div v-if="error" id="register-error" class="register-feedback is-error" role="alert">
            {{ error }}
          </div>
        </Transition>
        <Transition name="ink-fade">
          <div v-if="success" class="register-feedback is-success" role="status">
            {{ success }}
          </div>
        </Transition>

        <button
          type="submit"
          class="md-btn md-btn-filled md-ripple register-submit"
          :disabled="isRegistering"
        >
          {{ isRegistering ? '注册中...' : '注册' }}
        </button>
      </form>

      <div class="register-link">
        <span>已有账户？</span>
        <router-link to="/login" class="md-btn md-btn-text md-ripple register-link__cta">
          立即登录
        </router-link>
      </div>
    </section>

    <section v-else class="md-card md-card-elevated register-card register-card--closed">
      <h2>暂未开放注册</h2>
      <p>请联系管理员或稍后再试。</p>
      <router-link to="/login" class="md-btn md-btn-outlined md-ripple">返回登录</router-link>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import TypewriterEffect from '@/components/TypewriterEffect.vue'
import {
  useAuthOptionsQuery,
  useRegisterMutation,
  useSendVerificationCodeMutation,
} from '@/queries/auth'

const username = ref('')
const email = ref('')
const verificationCode = ref('')
const password = ref('')
const countdown = ref(0)
const error = ref('')
const success = ref('')
const router = useRouter()
const authOptionsQuery = useAuthOptionsQuery()
const sendCodeMutation = useSendVerificationCodeMutation()
const registerMutation = useRegisterMutation()
const sending = computed(() => sendCodeMutation.isPending.value)
const isRegistering = computed(() => registerMutation.isPending.value)
const allowRegistration = computed(() => authOptionsQuery.data.value?.allow_registration ?? true)
let countdownTimer: number | null = null

// 注册开关由 Query 缓存托管；关闭时只保留页面提示状态。
watch(
  allowRegistration,
  (allowed) => {
    if (allowed) return
    success.value = ''
    error.value = '当前已关闭注册，请稍后再试。'
  },
  { immediate: true },
)

const validateInput = () => {
  if (!username.value.trim()) {
    return '请输入用户名'
  }

  if (!email.value.trim()) {
    return '请输入邮箱'
  }

  if (!verificationCode.value.trim()) {
    return '请输入验证码'
  }

  // Password validation
  if (password.value.length < 8) {
    return '密码必须至少8个字符'
  }

  // Username validation
  const usernameVal = username.value
  const hasChinese = /[\u4e00-\u9fa5]/.test(usernameVal)
  const isNumeric = /^\d+$/.test(usernameVal)
  const isAlphanumeric = /^[a-zA-Z0-9]+$/.test(usernameVal)

  if (isNumeric) {
    return '用户名不能是纯数字'
  }

  if (hasChinese && usernameVal.length <= 1) {
    return '户名长度必须大于2个汉字'
  }

  if (isAlphanumeric && !hasChinese && usernameVal.length <= 6) {
    return '用户名长度必须大于6个字母或数字'
  }

  return null // No validation errors
}

const sendCode = async () => {
  error.value = ''
  success.value = ''
  const normalizedEmail = email.value.trim()

  if (!allowRegistration.value) {
    error.value = '当前已关闭注册，请联系管理员。'
    return
  }

  if (!normalizedEmail) {
    error.value = '请输入邮箱'
    return
  }
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!emailRegex.test(normalizedEmail)) {
    error.value = '邮箱格式不正确'
    return
  }

  sendCodeMutation.reset()
  try {
    await sendCodeMutation.mutateAsync(normalizedEmail)
    success.value = '验证码已发送，请查收邮箱'
    email.value = normalizedEmail
    // 等接口返回成功后再开始倒计时
    countdown.value = 60
    if (countdownTimer !== null) {
      window.clearInterval(countdownTimer)
    }
    countdownTimer = window.setInterval(() => {
      countdown.value--
      if (countdown.value <= 0 && countdownTimer !== null) {
        window.clearInterval(countdownTimer)
        countdownTimer = null
      }
    }, 1000)
  } catch (err) {
    if (err instanceof Error) {
      error.value = err.message
    } else {
      error.value = '发送验证码失败，请重试'
    }
  }
}

const handleRegister = async () => {
  error.value = ''
  success.value = ''

  const validationError = validateInput()
  if (validationError) {
    error.value = validationError
    return
  }

  if (!allowRegistration.value) {
    error.value = '当前已关闭注册，请联系管理员。'
    return
  }

  registerMutation.reset()
  try {
    const normalizedUsername = username.value.trim()
    const normalizedEmail = email.value.trim()
    const normalizedCode = verificationCode.value.trim()
    await registerMutation.mutateAsync({
      username: normalizedUsername,
      email: normalizedEmail,
      password: password.value,
      verification_code: normalizedCode,
    })
    username.value = normalizedUsername
    email.value = normalizedEmail
    verificationCode.value = normalizedCode
    success.value = '注册成功！正在跳转到登录页面...'
    setTimeout(() => {
      router.push('/login')
    }, 2000)
  } catch (err) {
    if (err instanceof Error) {
      error.value = err.message || '注册失败，请稍后再试。'
    } else {
      error.value = '注册失败，请稍后再试。'
    }
  }
}

onUnmounted(() => {
  if (countdownTimer !== null) {
    window.clearInterval(countdownTimer)
    countdownTimer = null
  }
})
</script>

<style scoped>
.register-page {
  min-height: var(--app-viewport-unit);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--md-spacing-8);
  padding:
    max(var(--md-spacing-4), env(safe-area-inset-top))
    max(var(--md-spacing-4), env(safe-area-inset-right))
    max(var(--md-spacing-4), env(safe-area-inset-bottom))
    max(var(--md-spacing-4), env(safe-area-inset-left));
  /* 采用平铺温暖熟宣纸与网格，驱逐SaaS强渐变 */
  background-color: var(--md-background) !important;
  background-image: radial-gradient(var(--md-outline-variant) 1px, transparent 1px) !important;
  background-size: 24px 24px !important;
}

.register-brand {
  min-height: 64px;
}

.register-card {
  width: min(100%, 448px);
  padding: var(--md-spacing-8);
  /* 告别 SaaS 大圆角，改为方直微圆角 */
  border-radius: var(--md-radius-sm) !important;
  /* 古籍粗细线双线框与拓片硬投影 */
  border: 3px double var(--md-outline) !important;
  background: var(--md-surface) !important;
  box-shadow: 4px 4px 0px rgba(28, 32, 34, 0.15) !important;
}

.register-card__header {
  margin-bottom: var(--md-spacing-8);
  text-align: center;
}

.register-card h2 {
  margin: 0;
  color: var(--md-on-surface);
  /* 碑拓宋体，字距拉伸 */
  font-family: var(--md-font-serif) !important;
  font-size: 28px !important;
  font-weight: 600;
  letter-spacing: 0.06em !important;
}

.register-card p {
  margin: var(--md-spacing-2) 0 0;
  color: var(--md-on-surface-variant);
  font-family: var(--md-font-kai) !important;
  font-size: 14px;
}

.register-form {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-5);
}

/* 输入框古典Focus反馈与朱砂压印硬影 */
.md-text-field-input {
  border-radius: var(--md-radius-xs) !important;
  border-color: var(--md-outline) !important;
  background-color: var(--md-surface-container-low) !important;
  font-family: inherit;
  transition:
    background-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.25s cubic-bezier(0.22, 1, 0.36, 1) !important;
}

.md-text-field-input:focus {
  outline: none !important;
  border-color: var(--md-secondary) !important;
  background-color: var(--md-surface-container-lowest) !important;
  box-shadow: 2px 2px 0px rgba(184, 60, 50, 0.25) !important; /* 朱批压章硬影 */
}

.md-text-field-label {
  font-family: var(--md-font-serif) !important;
  color: var(--md-primary-light) !important;
  font-weight: 600 !important;
  letter-spacing: 0.03em;
}

.register-code-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
  gap: var(--md-spacing-3);
}

/* 发送验证码辅助按钮 */
.register-code-button {
  min-width: 128px;
  align-self: stretch;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
  background: var(--md-surface-container-high) !important;
  border: 1px solid var(--md-outline) !important;
  border-radius: var(--md-radius-xs) !important;
  color: var(--md-on-surface) !important;
  font-family: var(--md-font-serif) !important;
  font-weight: 600;
  box-shadow: 1px 1px 0px rgba(28, 32, 34, 0.08) !important;
  transition:
    background-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.25s cubic-bezier(0.22, 1, 0.36, 1) !important;
  cursor: pointer;
}

.register-code-button:hover:not(:disabled) {
  background: var(--md-surface-container-highest) !important;
  box-shadow: 2px 2px 0px rgba(28, 32, 34, 0.15) !important;
}

.register-code-button:active:not(:disabled) {
  transform: translate(1px, 1px) !important;
  box-shadow: 0.5px 0.5px 0px rgba(28, 32, 34, 0.15) !important;
}

.register-feedback {
  padding: var(--md-spacing-3);
  border-radius: var(--md-radius-xs) !important;
  font-size: var(--md-body-medium);
  font-weight: 500;
  text-align: center;
  font-family: var(--md-font-kai) !important;
}

.register-feedback {
  overflow-wrap: anywhere;
}

.register-feedback.is-error {
  background-color: var(--md-error-container);
  border: 1px dashed var(--md-secondary);
  color: var(--md-on-error-container);
  box-shadow: 1px 1px 0px rgba(184, 60, 50, 0.08);
}

.register-feedback.is-success {
  background-color: var(--md-success-container);
  border: 1px dashed var(--md-success);
  color: var(--md-on-success-container);
  box-shadow: 1px 1px 0px rgba(59, 122, 87, 0.08);
}

/* 注册动作主按钮，动态水墨晕染Hover特效 */
.register-submit {
  width: 100%;
  min-height: 48px;
  position: relative;
  background: var(--md-primary) !important;
  color: var(--md-on-primary) !important;
  border: 1px solid var(--md-outline) !important;
  border-radius: var(--md-radius-xs) !important;
  overflow: hidden;
  font-family: var(--md-font-serif) !important;
  font-weight: 600 !important;
  letter-spacing: 0.05em;
  transition:
    background-color 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    color 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.3s cubic-bezier(0.22, 1, 0.36, 1) !important;
  box-shadow: 2px 2px 0px rgba(28, 32, 34, 0.12) !important;
  cursor: pointer;
}

.register-submit::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 200px;
  height: 200px;
  background: radial-gradient(circle, var(--md-primary-light) 0%, transparent 70%);
  border-radius: 50%;
  transform: translate(-50%, -50%) scale(0);
  transition: 
    transform 0.55s cubic-bezier(0.22, 1, 0.36, 1), 
    opacity 0.55s cubic-bezier(0.22, 1, 0.36, 1) !important;
  pointer-events: none;
  opacity: 0;
}

.register-submit:hover:not(:disabled) {
  background-color: var(--md-primary-light) !important;
  box-shadow: 3px 3px 0px rgba(28, 32, 34, 0.18) !important;
}

.register-submit:hover:not(:disabled)::before {
  transform: translate(-50%, -50%) scale(1.5);
  opacity: 0.35;
}

.register-submit:active:not(:disabled) {
  transform: translate(1.5px, 1.5px) !important;
  box-shadow: 0.5px 0.5px 0px rgba(28, 32, 34, 0.25) !important;
}

.register-link {
  margin-top: var(--md-spacing-6);
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: var(--md-spacing-1);
  text-align: center;
  font-family: var(--md-font-kai) !important;
}

.register-link__cta {
  min-height: 44px;
  font-family: var(--md-font-serif) !important;
  color: var(--md-secondary) !important;
  font-weight: 600;
}

.register-card--closed {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--md-spacing-4);
  text-align: center;
  border-radius: var(--md-radius-sm) !important;
  border: 3px double var(--md-outline) !important;
  background: var(--md-surface) !important;
  box-shadow: 4px 4px 0px rgba(28, 32, 34, 0.15) !important;
}

.register-card--closed h2 {
  font-family: var(--md-font-serif) !important;
  color: var(--md-secondary) !important;
}

@media (max-width: 833px) {
  .register-page {
    gap: var(--md-spacing-5);
  }

  .register-brand {
    min-height: 48px;
  }

  .register-card {
    width: min(100%, 480px);
    padding: var(--md-spacing-5);
  }

  .register-card__header {
    margin-bottom: var(--md-spacing-6);
  }

  .register-code-row {
    grid-template-columns: 1fr;
  }

  .register-code-button {
    width: 100%;
  }
}

/* 模拟熟宣水墨渐显：从模糊、淡色到清晰凝重 */
.ink-fade-enter-active,
.ink-fade-leave-active {
  transition: 
    opacity 0.45s cubic-bezier(0.22, 1, 0.36, 1),
    filter 0.45s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.45s cubic-bezier(0.22, 1, 0.36, 1);
}

.ink-fade-enter-from {
  opacity: 0;
  filter: blur(6px); /* 起笔淡墨模糊 */
  transform: translateY(4px);
}

.ink-fade-leave-to {
  opacity: 0;
  filter: blur(4px);
  transform: translateY(-4px);
}
</style>
