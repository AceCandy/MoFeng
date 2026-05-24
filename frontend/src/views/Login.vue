<!-- AIMETA P=登录页_用户登录|R=登录表单_认证|NR=不含注册功能|E=route:/login#component:Login|X=ui|A=登录表单|D=vue|S=dom,net,storage|RD=./README.ai -->
<template>
  <div class="login-page">
    <div class="login-brand">
      <TypewriterEffect text="墨风" />
    </div>

    <section class="md-card md-card-elevated login-card" aria-labelledby="login-title">
      <div class="login-card__header">
        <p>墨风</p>
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
            :aria-invalid="Boolean(error)"
            :aria-describedby="error ? 'login-error' : undefined"
            class="md-text-field-input"
            placeholder="请输入用户名"
            autocomplete="username"
            maxlength="64"
            spellcheck="false"
            autocapitalize="none"
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
            :aria-invalid="Boolean(error)"
            :aria-describedby="error ? 'login-error' : undefined"
            class="md-text-field-input"
            placeholder="请输入密码"
            autocomplete="current-password"
            maxlength="256"
          />
        </div>

        <Transition name="ink-fade">
          <div v-if="error" id="login-error" class="login-feedback" role="alert">
            <span class="login-feedback__stamp">[ 謬 ]</span>
            <span>{{ error }}</span>
          </div>
        </Transition>

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

      <div v-if="allowRegistration" class="login-link">
        <span>还没有账户？</span>
        <router-link to="/register" class="md-btn md-btn-text md-ripple login-link__cta">
          立即注册
        </router-link>
      </div>
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
  const normalizedUsername = username.value.trim()
  if (!normalizedUsername) {
    error.value = '请输入用户名'
    return
  }

  try {
    const result = await loginMutation.mutateAsync({
      username: normalizedUsername,
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
  /* 采用平铺温暖熟宣纸与干燥木骨色彩，驱逐SaaS放射性强渐变 */
  background-color: var(--md-background) !important;
  background-image: radial-gradient(var(--md-outline-variant) 1px, transparent 1px) !important;
  background-size: 24px 24px !important;
}

.login-brand {
  min-height: 64px;
}

.login-card {
  width: min(100%, 448px);
  padding: var(--md-spacing-8);
  /* 告别 SaaS 大圆角，改为木刻方直微圆角 */
  border-radius: var(--md-radius-sm) !important;
  /* 升级为古典双线细线框，配合右下拓片偏置硬投影 */
  border: 3px double var(--md-outline) !important;
  background: var(--md-surface) !important;
  box-shadow: 4px 4px 0px rgba(28, 32, 34, 0.15) !important;
}

.login-card__header {
  margin-bottom: var(--md-spacing-8);
  text-align: center;
}

.login-card__header p {
  margin: 0 0 var(--md-spacing-2);
  color: var(--md-secondary); /* 朱砂红小标 */
  font-family: var(--md-font-kai) !important;
  font-size: var(--md-label-large);
  font-weight: 600;
  letter-spacing: 0.05em;
}

.login-card__header h2 {
  margin: 0;
  color: var(--md-on-surface);
  /* 碑拓宋体，字间距舒展 */
  font-family: var(--md-font-serif) !important;
  font-size: 28px !important;
  font-weight: 600;
  letter-spacing: 0.06em !important;
}

.login-card__header span {
  display: block;
  margin-top: var(--md-spacing-2);
  color: var(--md-on-surface-variant);
  font-family: var(--md-font-kai) !important;
  font-size: 14px;
}

.login-form {
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

.login-feedback {
  display: flex;
  align-items: flex-start;
  gap: var(--md-spacing-2);
  padding: var(--md-spacing-3);
  border-radius: var(--md-radius-xs) !important;
  background-color: var(--md-error-container);
  border: 1px dashed var(--md-secondary);
  color: var(--md-on-error-container);
  font-size: var(--md-body-medium);
  font-weight: 500;
  box-shadow: 1px 1px 0px rgba(184, 60, 50, 0.08);
}

.login-feedback span {
  overflow-wrap: anywhere;
  font-family: var(--md-font-kai) !important;
}

.login-feedback svg,
.login-oauth-icon,
.login-spinner {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.login-feedback svg {
  color: var(--md-secondary);
}

/* 焦墨按钮与动态水墨晕染Hover特效 */
.login-submit {
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

.login-submit::before {
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

.login-submit:hover {
  background-color: var(--md-primary-light) !important;
  box-shadow: 3px 3px 0px rgba(28, 32, 34, 0.18) !important;
}

.login-submit:hover::before {
  transform: translate(-50%, -50%) scale(1.5);
  opacity: 0.35; /* 墨晕微显 */
}

.login-submit:active {
  transform: translate(1.5px, 1.5px) !important;
  box-shadow: 0.5px 0.5px 0px rgba(28, 32, 34, 0.25) !important;
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
  font-family: var(--md-font-kai) !important;
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
  background-color: var(--md-surface) !important;
}

.login-link {
  margin: var(--md-spacing-6) 0 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: var(--md-spacing-1);
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-medium);
  text-align: center;
  font-family: var(--md-font-kai) !important;
}

.login-link__cta {
  min-height: 44px;
  font-family: var(--md-font-serif) !important;
  color: var(--md-secondary) !important;
  font-weight: 600;
}

.login-link a:hover {
  text-decoration: underline;
}

@media (max-width: 833px) {
  .login-page {
    gap: var(--md-spacing-5);
  }

  .login-brand {
    min-height: 48px;
  }

  .login-card {
    width: min(100%, 480px);
    padding: var(--md-spacing-5);
  }

  .login-card__header {
    margin-bottom: var(--md-spacing-6);
  }

  .login-divider {
    margin: var(--md-spacing-6) 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .login-spinner {
    animation: none;
  }
}

/* 模拟熟宣水墨渐显：从模糊、淡色到清晰凝重 */
.ink-fade-enter-active,
.ink-fade-leave-active {
  transition: 
    opacity 0.35s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.35s cubic-bezier(0.22, 1, 0.36, 1);
}

.ink-fade-enter-from {
  opacity: 0;
  transform: translateY(4px);
}

.ink-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

.login-feedback__stamp {
  font-family: var(--md-font-serif) !important;
  font-weight: 600;
  color: var(--md-secondary) !important;
  margin-right: 4px;
  user-select: none;
}
</style>
