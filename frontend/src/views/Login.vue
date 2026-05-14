<!-- AIMETA P=登录页_用户登录|R=登录表单_认证|NR=不含注册功能|E=route:/login#component:Login|X=ui|A=登录表单|D=vue|S=dom,net,storage|RD=./README.ai -->
<template>
  <div class="login-page">
    <div class="login-brand">
      <TypewriterEffect text="拯救小说家" />
    </div>

    <section class="md-card md-card-elevated login-card" aria-labelledby="login-title">
      <div class="login-card__header">
        <p>Arboris Novel</p>
        <h2 id="login-title">欢迎回来</h2>
        <span>登录以继续您的创作之旅</span>
      </div>

      <form @submit.prevent="handleLogin" class="login-form" :aria-busy="isLoading">
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
          <label for="password" class="md-text-field-label">密码</label>
          <input
            v-model="password"
            id="password"
            name="password"
            type="password"
            required
            class="md-text-field-input"
            placeholder="请输入密码"
            autocomplete="current-password"
          />
        </div>

        <div v-if="error" class="login-feedback" role="alert">
          <svg
            aria-hidden="true"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <span>{{ error }}</span>
        </div>

        <button
          type="submit"
          :disabled="isLoading"
          class="md-btn md-btn-filled md-ripple login-submit"
        >
          <svg
            v-if="isLoading"
            class="login-spinner"
            viewBox="0 0 24 24"
            fill="none"
            aria-hidden="true"
          >
            <circle
              class="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              stroke-width="4"
            ></circle>
            <path
              class="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            ></path>
          </svg>
          <span v-if="isLoading">正在登录...</span>
          <span v-else>登录</span>
        </button>
      </form>

      <div class="login-divider">
        <span>或</span>
      </div>

      <div v-if="enableLinuxdoLogin">
        <a href="/api/auth/linuxdo/login" class="md-btn md-btn-outlined md-ripple login-submit">
          <svg class="login-oauth-icon" aria-hidden="true" viewBox="0 0 496 512">
            <path
              fill="currentColor"
              d="M248 8C111 8 0 119 0 256s111 248 248 248 248-111 248-248S385 8 248 8zm0 448c-110.5 0-200-89.5-200-200S137.5 56 248 56s200 89.5 200 200-89.5 200-200 200z"
            ></path>
          </svg>
          使用 Linux DO 登录
        </a>
      </div>

      <p v-if="allowRegistration" class="login-link">
        还没有账户？
        <router-link to="/register">立即注册</router-link>
      </p>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import TypewriterEffect from '@/components/TypewriterEffect.vue'
import { useAuthOptionsQuery, useLoginMutation } from '@/queries/auth'

const username = ref('')
const password = ref('')
const error = ref('')
const router = useRouter()
const authOptionsQuery = useAuthOptionsQuery()
const loginMutation = useLoginMutation()
const isLoading = computed(() => loginMutation.isPending.value)
const allowRegistration = computed(() => authOptionsQuery.data.value?.allow_registration ?? true)
const enableLinuxdoLogin = computed(
  () => authOptionsQuery.data.value?.enable_linuxdo_login ?? false,
)

const handleLogin = async () => {
  error.value = ''
  loginMutation.reset()
  try {
    const result = await loginMutation.mutateAsync({
      username: username.value,
      password: password.value,
    })
    if (result.user.is_admin && result.mustChangePassword) {
      await router.push({ name: 'admin', query: { tab: 'password' } })
    } else {
      await router.push('/workspace')
    }
  } catch (err) {
    if (err instanceof Error && err.message.includes('Request timed out')) {
      error.value = '登录请求超时，请确认后端服务已启动并可访问。'
    } else if (err instanceof Error && err.message === 'Failed to initialize user session') {
      error.value = '登录成功，但获取用户信息失败，请检查后端并重试。'
    } else {
      error.value = '登录失败，请检查您的用户名和密码。'
    }
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--md-spacing-8);
  padding: var(--md-spacing-4);
  background-color: var(--md-surface-dim);
}

.login-brand {
  min-height: 64px;
}

.login-card {
  width: min(100%, 448px);
  padding: var(--md-spacing-8);
  border-radius: var(--md-radius-xl);
}

.login-card__header {
  margin-bottom: var(--md-spacing-8);
  text-align: center;
}

.login-card__header p {
  margin: 0 0 var(--md-spacing-2);
  color: var(--md-primary-dark);
  font-size: var(--md-label-medium);
  font-weight: 600;
}

.login-card__header h2 {
  margin: 0;
  color: var(--md-on-surface);
  font-size: var(--md-headline-small);
  font-weight: 600;
}

.login-card__header span {
  display: block;
  margin-top: var(--md-spacing-2);
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-medium);
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-4);
}

.login-feedback {
  display: flex;
  align-items: flex-start;
  gap: var(--md-spacing-2);
  padding: var(--md-spacing-3);
  border-radius: var(--md-radius-md);
  background-color: var(--md-error-container);
  color: var(--md-on-error-container);
  font-size: var(--md-body-medium);
  font-weight: 500;
}

.login-feedback svg,
.login-oauth-icon,
.login-spinner {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.login-feedback svg {
  color: var(--md-error);
}

.login-submit {
  width: 100%;
  min-height: 48px;
}

.login-spinner {
  animation: md-spin 0.8s linear infinite;
}

.login-divider {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: var(--md-spacing-8) 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.login-divider::before {
  content: '';
  width: 100%;
  height: 1px;
  background-color: var(--md-outline-variant);
}

.login-divider span {
  position: absolute;
  padding: 0 var(--md-spacing-4);
  background-color: var(--md-surface);
}

.login-link {
  margin: var(--md-spacing-6) 0 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-medium);
  text-align: center;
}

.login-link a {
  color: var(--md-primary-dark);
  font-weight: 600;
  text-decoration: none;
}

.login-link a:hover {
  text-decoration: underline;
}

@media (max-width: 520px) {
  .login-card {
    padding: var(--md-spacing-5);
  }
}
</style>
