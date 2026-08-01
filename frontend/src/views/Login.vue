<!-- AIMETA P=登录页_用户登录|R=登录表单_认证|NR=不含注册功能|E=route:/login#component:Login|X=ui|A=登录表单|D=vue|S=dom,net,storage|RD=./README.ai -->
<template>
  <main class="login-page">
    <section class="login-scroll" aria-labelledby="login-title">
      <AuthIntro variant="login" />

      <section class="login-panel" aria-label="登录表单">
        <div class="login-card__header">
          <h2 id="login-title">
            归来续笔
            <span aria-hidden="true">印</span>
          </h2>
          <p>登录以继续你的创作之旅</p>
        </div>

        <form class="login-form" :aria-busy="isLoading" @submit.prevent="handleLogin">
          <div class="md-text-field">
            <label for="username" class="md-text-field-label">笔名</label>
            <div class="md-text-field-wrapper">
              <input
                id="username"
                v-model="username"
                name="username"
                type="text"
                required
                :aria-invalid="Boolean(error)"
                :aria-describedby="error ? 'login-error' : undefined"
                class="md-text-field-input"
                placeholder="请输入笔名"
                autocomplete="username"
                maxlength="64"
                spellcheck="false"
                autocapitalize="none"
              />
              <span class="md-text-field-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
                  <path
                    d="M18 3 4 17l-1 4 4-1L21 6l-3-3Z"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                  <path d="m14 7 3 3M4 20c.8-.5 1.4-1.1 2-2" stroke-linecap="round" />
                </svg>
              </span>
            </div>
          </div>

          <div class="md-text-field">
            <label for="password" class="md-text-field-label">口令</label>
            <div class="md-text-field-wrapper">
              <input
                id="password"
                v-model="password"
                name="password"
                :type="showPassword ? 'text' : 'password'"
                required
                :aria-invalid="Boolean(error)"
                :aria-describedby="error ? 'login-error' : undefined"
                class="md-text-field-input"
                placeholder="请输入口令"
                autocomplete="current-password"
                maxlength="256"
              />
              <button
                type="button"
                class="md-text-field-icon md-text-field-icon--button"
                :aria-label="showPassword ? '隐藏口令' : '显示口令'"
                @click="showPassword = !showPassword"
              >
                <svg v-if="!showPassword" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
                  <path d="M3 10c3 4 8 4 11 0" stroke-linecap="round" />
                  <path d="m5.5 11-1.5 2.5M8.5 12l-.5 3M11.5 12l.5 3M14.5 11l1.5 2.5" stroke-linecap="round" />
                </svg>
                <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8Z" stroke-linejoin="round" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
              </button>
            </div>
          </div>

          <div class="login-options">
            <label class="login-remember">
              <input v-model="rememberMe" type="checkbox" />
              <span aria-hidden="true"></span>
              记住我
            </label>
          </div>

          <Transition name="ink-fade">
            <div v-if="error" id="login-error" class="login-feedback" role="alert">
              <span class="login-feedback__stamp" aria-hidden="true">误</span>
              <span>{{ error }}</span>
            </div>
          </Transition>

          <button type="submit" :disabled="isLoading" class="md-btn md-btn-filled md-ripple login-submit">
            <svg v-if="isLoading" class="login-spinner" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="3" opacity="0.25" />
              <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" stroke-width="3" stroke-linecap="round" />
            </svg>
            <span>{{ isLoading ? '正在入卷...' : '入卷续写' }}</span>
            <svg v-if="!isLoading" class="login-submit__mark" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true">
              <path d="M3 12c4 0 6-3 8-3s4 3 8 3" stroke-linecap="round" />
              <path d="M7 10c2-1 3-2 5-2s3 1 5 2" stroke-linecap="round" />
            </svg>
          </button>
        </form>

        <div class="login-divider" aria-hidden="true">
          <span></span>
        </div>

        <template v-if="enableLinuxdoLogin">
          <div class="login-oauth-divider"><span>或</span></div>
          <a href="/api/auth/linuxdo/login" class="md-btn md-btn-outlined md-ripple login-oauth">
            <svg class="login-oauth-icon" aria-hidden="true" viewBox="0 0 496 512">
              <path
                fill="currentColor"
                d="M248 8C111 8 0 119 0 256s111 248 248 248 248-111 248-248S385 8 248 8Zm0 448c-110.5 0-200-89.5-200-200S137.5 56 248 56s200 89.5 200 200-89.5 200-200 200Z"
              />
            </svg>
            使用 Linux DO 登录
          </a>
        </template>

        <div v-if="allowRegistration" class="login-link">
          <span>还没有账户？</span>
          <router-link to="/register" class="md-btn md-btn-text md-ripple login-link__cta">
            开新卷
          </router-link>
        </div>
      </section>

      <AuthFeatureRail />
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthOptionsQuery, useLoginMutation } from '@/queries/auth'
import AuthIntro from '@/components/auth/AuthIntro.vue'
import AuthFeatureRail from '@/components/auth/AuthFeatureRail.vue'

const username = ref('')
const password = ref('')
const showPassword = ref(false)
const rememberMe = ref(false)
const error = ref('')
const router = useRouter()
const authOptionsQuery = useAuthOptionsQuery()
const loginMutation = useLoginMutation()
const isLoading = computed(() => loginMutation.isPending.value)
const allowRegistration = computed(() => authOptionsQuery.data.value?.allow_registration ?? true)
const enableLinuxdoLogin = computed(
  () => authOptionsQuery.data.value?.enable_linuxdo_login ?? false,
)

// 登录流程只做输入规整和失败反馈，页面改版不改变认证接口语义。
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
  --auth-ink: var(--md-on-surface);
  --auth-ink-soft: var(--md-on-surface-variant);
  --auth-line: var(--md-outline);
  --auth-line-soft: var(--md-outline-variant);
  --auth-vermilion: var(--md-secondary-dark);
  --auth-paper: #faf6ed;
  --auth-paper-light: #fbf7ec;
  --auth-paper-field: rgba(253, 250, 240, 0.52);
  --md-secondary-readable: var(--md-secondary-dark);

  min-height: var(--app-viewport-unit);
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  padding: max(12px, env(safe-area-inset-top)) max(12px, env(safe-area-inset-right))
    max(12px, env(safe-area-inset-bottom)) max(12px, env(safe-area-inset-left));
  background:
    linear-gradient(180deg, rgba(45, 39, 29, 0.08), rgba(45, 39, 29, 0.16)),
    url('../assets/mofeng_login_bg_v2.webp') center / cover,
    #d8cbb7;
  color: var(--auth-ink);
}

.login-scroll {
  width: min(96vw, 1440px);
  min-height: min(760px, calc(100vh - 24px));
  position: relative;
  z-index: 1;
  flex: 0 1 auto;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(340px, 430px);
  grid-template-rows: 1fr auto;
  gap: clamp(20px, 3vw, 48px);
  padding: clamp(14px, 2vw, 32px);
  overflow: hidden;
  border-radius: var(--md-radius-sm);
  background:
    linear-gradient(180deg, rgba(45, 39, 29, 0.04), rgba(45, 39, 29, 0.08)),
    repeating-linear-gradient(90deg, rgba(28, 32, 34, 0.014) 0 1px, transparent 1px 24px),
    var(--auth-paper-light);
  color: var(--auth-ink);
}

.login-page::before {
  content: '';
  position: fixed;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(circle at 50% 40%, rgba(252, 246, 231, 0.28), transparent 38%),
    linear-gradient(180deg, rgba(45, 39, 29, 0.02), rgba(45, 39, 29, 0.1));
  z-index: 0;
}

.login-panel {
  position: relative;
  z-index: 1;
  align-self: center;
  width: 100%;
  box-sizing: border-box;
  padding: clamp(20px, 2.2vw, 32px);
  border: 3px double var(--md-outline);
  border-radius: var(--md-radius-xs);
  background:
    repeating-linear-gradient(90deg, transparent, transparent 38px, color-mix(in srgb, var(--md-on-surface) 3%, transparent) 38px, color-mix(in srgb, var(--md-on-surface) 4%, transparent) 40px),
    linear-gradient(var(--auth-paper-light), var(--auth-paper));
  box-shadow: 4px 4px 0 color-mix(in srgb, var(--md-on-surface) 14%, transparent);
  color: var(--auth-ink);
}

.login-card__header,
.login-form,
.login-divider,
.login-oauth-divider,
.login-oauth,
.login-link {
  width: 100%;
  position: relative;
}

.login-panel *,
.login-panel *::before,
.login-panel *::after {
  box-sizing: border-box;
}

.login-card__header {
  margin-bottom: clamp(14px, 1.7vw, 24px);
}

.login-card__header h2 {
  display: flex;
  align-items: center;
  gap: clamp(8px, 0.85vw, 14px);
  margin: 0;
  color: var(--auth-ink);
  font-family: var(--md-font-serif);
  font-size: clamp(28px, 2.25vw, 38px);
  font-weight: 600;
  line-height: 1.2;
  letter-spacing: 0.08em;
}

.login-card__header h2 span {
  width: clamp(18px, 1.4vw, 22px);
  height: clamp(18px, 1.4vw, 22px);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1.5px solid var(--auth-vermilion);
  color: var(--auth-vermilion);
  font-size: 12px;
  letter-spacing: 0;
}

.login-card__header p {
  margin: clamp(8px, 0.8vw, 12px) 0 0;
  color: var(--auth-ink-soft);
  font-size: clamp(12px, 0.9vw, 14px);
  letter-spacing: 0.04em;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: clamp(12px, 1vw, 16px);
}

.md-text-field {
  display: flex;
  flex-direction: column;
  gap: clamp(6px, 0.55vw, 8px);
}

.md-text-field-label {
  color: var(--auth-ink);
  font-family: var(--md-font-serif);
  font-size: clamp(12px, 0.88vw, 14px);
  font-weight: 600;
  letter-spacing: 0.06em;
}

.md-text-field-wrapper {
  position: relative;
}

.md-text-field-input {
  width: 100%;
  height: clamp(46px, 3.35vw, 54px);
  padding: 0 clamp(44px, 3.2vw, 52px) 0 clamp(14px, 1.15vw, 18px);
  border: 1px solid var(--auth-line);
  border-radius: var(--md-radius-xs);
  background-color: var(--auth-paper-field);
  color: var(--auth-ink);
  font-family: var(--md-font-serif);
  font-size: clamp(13px, 0.96vw, 15px);
  letter-spacing: 0.03em;
  box-shadow: inset 0 0 0 1px rgba(255, 251, 241, 0.55);
  transition:
    background-color 180ms cubic-bezier(0.22, 1, 0.36, 1),
    border-color 180ms cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 180ms cubic-bezier(0.22, 1, 0.36, 1);
}

.md-text-field-input:focus {
  outline: none;
  border-color: var(--auth-ink);
  background-color: rgba(253, 251, 245, 0.9);
  box-shadow:
    inset 0 0 0 1px rgba(255, 251, 241, 0.75),
    2px 2px 0 color-mix(in srgb, var(--auth-ink) 18%, transparent);
}

/* 键盘焦点可见环（≥3:1），鼠标 focus 不重复显示 */
.md-text-field-input:focus-visible {
  outline: 2px solid var(--auth-ink);
  outline-offset: 2px;
}

.md-text-field-input::placeholder {
  color: color-mix(in srgb, var(--auth-ink-soft) 52%, transparent);
}

.md-text-field-icon {
  position: absolute;
  top: 50%;
  right: clamp(12px, 1vw, 16px);
  width: clamp(18px, 1.35vw, 22px);
  height: clamp(18px, 1.35vw, 22px);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: color-mix(in srgb, var(--auth-ink-soft) 65%, transparent);
  transform: translateY(-50%);
}

.md-text-field-icon--button {
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
  transition: color 150ms cubic-bezier(0.22, 1, 0.36, 1);
}

.md-text-field-icon--button:hover {
  color: var(--auth-ink);
}

.login-options {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  color: var(--auth-ink-soft);
  font-family: var(--md-font-serif);
  font-size: clamp(11px, 0.82vw, 13px);
}

.login-remember {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 28px;
  cursor: pointer;
  user-select: none;
}

.login-remember input {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  opacity: 0;
}

.login-remember span {
  width: 14px;
  height: 14px;
  border: 1px solid var(--auth-line);
  background: rgba(253, 251, 245, 0.62);
  box-shadow: inset 0 0 0 2px rgba(253, 251, 245, 0.8);
}

.login-remember input:checked + span {
  background: var(--md-secondary);
  border-color: var(--md-secondary);
}

.login-remember input:focus-visible + span {
  outline: 2px solid var(--auth-line);
  outline-offset: 2px;
}

.login-feedback {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border: 1px dashed color-mix(in srgb, var(--auth-vermilion) 52%, transparent);
  border-radius: var(--md-radius-xs);
  background: var(--md-error-container);
  color: var(--md-error-text);
  font-size: 13px;
  line-height: 1.55;
}

.login-feedback__stamp {
  width: 22px;
  height: 22px;
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border: 1px solid currentColor;
  font-family: var(--md-font-serif);
  font-size: 12px;
}

.login-submit {
  width: 100%;
  min-height: clamp(48px, 3.55vw, 56px);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  border: 1px solid color-mix(in srgb, var(--auth-ink) 75%, transparent);
  border-radius: var(--md-radius-xs);
  background:
    linear-gradient(90deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0)),
    var(--auth-ink);
  color: var(--auth-paper-light);
  font-family: var(--md-font-serif);
  font-size: clamp(14px, 1vw, 16px);
  font-weight: 600;
  letter-spacing: 0.14em;
  box-shadow: 2px 2px 0 color-mix(in srgb, var(--auth-ink) 20%, transparent);
  transition:
    background-color 180ms cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 180ms cubic-bezier(0.22, 1, 0.36, 1),
    transform 180ms cubic-bezier(0.22, 1, 0.36, 1);
}

.login-submit:hover:not(:disabled) {
  background-color: var(--md-primary-light);
  box-shadow: 3px 3px 0 color-mix(in srgb, var(--auth-ink) 24%, transparent);
}

.login-submit:active:not(:disabled) {
  transform: translate(1px, 1px);
  box-shadow: 1px 1px 0 color-mix(in srgb, var(--auth-ink) 22%, transparent);
}

.login-submit:disabled {
  opacity: 0.68;
  cursor: not-allowed;
}

.login-submit__mark {
  width: 18px;
  height: 18px;
  color: var(--md-outline);
}

.login-spinner {
  width: 19px;
  height: 19px;
  animation: md-spin 900ms linear infinite;
}

.login-divider {
  height: clamp(16px, 1.4vw, 22px);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: clamp(8px, 0.8vw, 12px);
  color: var(--auth-line);
}

.login-divider::before,
.login-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--auth-line-soft), transparent);
}

.login-divider span {
  width: clamp(13px, 1.12vw, 18px);
  height: clamp(13px, 1.12vw, 18px);
  margin: 0 clamp(8px, 0.75vw, 12px);
  border: 1px solid currentColor;
  transform: rotate(45deg);
}

.login-oauth-divider {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 8px;
  color: var(--auth-ink-soft);
  font-size: 12px;
}

.login-oauth {
  min-height: 46px;
  margin-top: 10px;
  border-color: var(--auth-line);
  border-radius: var(--md-radius-xs);
  color: var(--auth-ink);
  font-family: var(--md-font-serif);
}

.login-oauth-icon {
  width: 18px;
  height: 18px;
}

.login-link {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin-top: clamp(8px, 0.85vw, 14px);
  color: var(--auth-ink-soft);
  font-family: var(--md-font-serif);
  font-size: clamp(12px, 0.9vw, 14px);
}

.login-link__cta {
  min-height: 44px;
  padding: 0 10px;
  color: var(--md-secondary-readable);
  font-weight: 600;
}

@media (min-width: 834px) {
  .auth-intro {
    min-height: 420px;
  }
}

.auth-feature-rail {
  grid-column: 1 / -1;
  justify-self: center;
}

@media (max-width: 1024px) {
  .login-scroll {
    width: min(98vw, 1440px);
    grid-template-columns: minmax(0, 1fr) minmax(320px, 400px);
  }
}

@media (max-width: 833px) {
  .login-page {
    justify-content: flex-start;
    overflow-y: auto;
    padding: max(6px, env(safe-area-inset-top)) 6px max(12px, env(safe-area-inset-bottom));
    background:
      linear-gradient(180deg, rgba(45, 39, 29, 0.06), rgba(45, 39, 29, 0.14)),
      #d8cbb7;
  }

  .login-scroll {
    width: min(calc(100vw - 12px), 520px);
    min-height: 0;
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: auto;
    gap: 12px;
    padding: 10px;
  }

  .login-panel {
    align-self: stretch;
    padding: 22px 18px 24px;
    box-shadow: 3px 3px 0 color-mix(in srgb, var(--md-on-surface) 12%, transparent);
  }

  .login-card__header {
    margin-bottom: 18px;
  }

  .login-card__header h2 {
    font-size: 28px;
  }

  .login-form {
    gap: 14px;
  }

  .md-text-field-input {
    height: 50px;
  }

  .login-options {
    font-size: 12.5px;
    gap: 10px;
  }

  .login-link {
    flex-wrap: wrap;
  }
}

@media (max-width: 390px) {
  .login-panel {
    padding-left: 16px;
    padding-right: 16px;
  }
}

.ink-fade-enter-active,
.ink-fade-leave-active {
  transition:
    opacity 220ms cubic-bezier(0.22, 1, 0.36, 1),
    transform 220ms cubic-bezier(0.22, 1, 0.36, 1);
}

.ink-fade-enter-from,
.ink-fade-leave-to {
  opacity: 0;
  transform: translateY(4px);
}
</style>
