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
            class="md-btn md-btn-tonal md-ripple register-code-button"
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

        <div v-if="error" id="register-error" class="register-feedback is-error" role="alert">
          {{ error }}
        </div>
        <div v-if="success" class="register-feedback is-success" role="status">
          {{ success }}
        </div>

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
  } catch (err: any) {
    error.value = err.message
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
  } catch (err: any) {
    error.value = err.message || '注册失败，请稍后再试。'
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
  background:
    radial-gradient(
      circle at 0% 0%,
      color-mix(in oklch, var(--md-primary-container) 50%, transparent),
      transparent 36%
    ),
    radial-gradient(
      circle at 100% 10%,
      color-mix(in oklch, var(--md-success-container) 54%, transparent),
      transparent 40%
    ),
    linear-gradient(
      180deg,
      color-mix(in oklch, var(--md-surface-dim) 84%, var(--md-tint-cool)),
      color-mix(in oklch, var(--md-surface-container-low) 90%, var(--md-tint-success))
    );
}

.register-brand {
  min-height: 64px;
}

.register-card {
  width: min(100%, 448px);
  padding: var(--md-spacing-8);
  border-radius: var(--md-radius-xl);
  border: 1px solid color-mix(in oklch, var(--md-primary) 20%, var(--md-outline-variant));
  background:
    linear-gradient(
      150deg,
      color-mix(in oklch, var(--md-surface) 90%, var(--md-tint-cool)),
      color-mix(in oklch, var(--md-surface) 92%, var(--md-tint-success))
    );
}

.register-card__header {
  margin-bottom: var(--md-spacing-8);
  text-align: center;
}

.register-card h2 {
  margin: 0;
  color: var(--md-on-surface);
  font-size: var(--md-headline-small);
  font-weight: 600;
}

.register-card p {
  margin: var(--md-spacing-2) 0 0;
  color: var(--md-on-surface-variant);
}

.register-form {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-4);
}

.register-code-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
  gap: var(--md-spacing-3);
}

.register-code-button {
  min-width: 128px;
  height: 56px;
  white-space: nowrap;
}

.register-feedback {
  padding: var(--md-spacing-3);
  border-radius: var(--md-radius-md);
  font-size: var(--md-body-medium);
  font-weight: 500;
  text-align: center;
}

.register-feedback {
  overflow-wrap: anywhere;
}

.register-feedback.is-error {
  background-color: var(--md-error-container);
  color: var(--md-on-error-container);
}

.register-feedback.is-success {
  background-color: var(--md-success-container);
  color: var(--md-on-success-container);
}

.register-submit {
  width: 100%;
}

.register-link {
  margin-top: var(--md-spacing-6);
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: var(--md-spacing-1);
  text-align: center;
}

.register-link__cta {
  min-height: 44px;
}

.register-card--closed {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--md-spacing-4);
  text-align: center;
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
</style>
