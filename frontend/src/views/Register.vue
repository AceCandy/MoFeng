<!-- AIMETA P=注册页_用户注册|R=注册表单|NR=不含登录功能|E=route:/register#component:Register|X=ui|A=注册表单|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="register-page">
    <div class="register-brand">
      <TypewriterEffect text="拯救小说家" />
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
            class="md-text-field-input"
            placeholder="请输入用户名"
            autocomplete="username"
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
            class="md-text-field-input"
            placeholder="请输入邮箱"
            autocomplete="email"
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
              class="md-text-field-input"
              placeholder="请输入验证码"
              inputmode="numeric"
              autocomplete="one-time-code"
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
            class="md-text-field-input"
            placeholder="至少 8 个字符"
            autocomplete="new-password"
          />
        </div>

        <div v-if="error" class="register-feedback is-error" role="alert">
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

      <p class="register-link">
        已有账户？
        <router-link to="/login">立即登录</router-link>
      </p>
    </section>

    <section v-else class="md-card md-card-elevated register-card register-card--closed">
      <h2>暂未开放注册</h2>
      <p>请联系管理员或稍后再试。</p>
      <router-link to="/login" class="md-btn md-btn-outlined md-ripple">返回登录</router-link>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import TypewriterEffect from '@/components/TypewriterEffect.vue'

const username = ref('')
const email = ref('')
const verificationCode = ref('')
const password = ref('')
const countdown = ref(0)
const sending = ref(false)
const isRegistering = ref(false)
const error = ref('')
const success = ref('')
const router = useRouter()
const authStore = useAuthStore()
const allowRegistration = computed(() => authStore.allowRegistration)

// 进入页面即拉取认证开关，避免展示无效注册表单
onMounted(async () => {
  await authStore.fetchAuthOptions()
  if (!allowRegistration.value) {
    success.value = ''
    error.value = '当前已关闭注册，请稍后再试。'
  }
})

const validateInput = () => {
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

  if (!allowRegistration.value) {
    error.value = '当前已关闭注册，请联系管理员。'
    return
  }

  if (!email.value) {
    error.value = '请输入邮箱'
    return
  }
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!emailRegex.test(email.value)) {
    error.value = '邮箱格式不正确'
    return
  }

  sending.value = true
  try {
    const res = await fetch(`/api/auth/send-code?email=${encodeURIComponent(email.value)}`, {
      method: 'POST',
    })
    if (!res.ok) {
      const errMsg = await res.json()
      throw new Error(errMsg.detail || '发送验证码失败')
    }
    success.value = '验证码已发送，请查收邮箱'
    // 等接口返回成功后再开始倒计时
    countdown.value = 60
    const timer = setInterval(() => {
      countdown.value--
      if (countdown.value <= 0) clearInterval(timer)
    }, 1000)
  } catch (err: any) {
    error.value = err.message
  } finally {
    sending.value = false
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

  isRegistering.value = true
  try {
    const res = await fetch('/api/auth/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: username.value,
        email: email.value,
        password: password.value,
        verification_code: verificationCode.value,
      }),
    })
    if (!res.ok) {
      const errMsg = await res.json()
      throw new Error(errMsg.detail || '注册失败')
    }
    success.value = '注册成功！正在跳转到登录页面...'
    setTimeout(() => {
      router.push('/login')
    }, 2000)
  } catch (err: any) {
    error.value = err.message || '注册失败，请稍后再试。'
  } finally {
    isRegistering.value = false
  }
}
</script>

<style scoped>
.register-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--md-spacing-8);
  padding: var(--md-spacing-4);
}

.register-brand {
  min-height: 64px;
}

.register-card {
  width: min(100%, 448px);
  padding: var(--md-spacing-8);
  border-radius: var(--md-radius-xl);
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
  text-align: center;
}

.register-link a {
  color: var(--md-primary-dark);
  font-weight: 600;
  text-decoration: none;
}

.register-card--closed {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--md-spacing-4);
  text-align: center;
}

@media (max-width: 520px) {
  .register-card {
    padding: var(--md-spacing-5);
  }

  .register-code-row {
    grid-template-columns: 1fr;
  }

  .register-code-button {
    width: 100%;
  }
}
</style>
