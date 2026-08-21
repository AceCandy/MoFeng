<!-- AIMETA P=登录页_用户登录|R=登录表单_认证|NR=不含注册功能|E=route:/login#component:Login|X=ui|A=登录表单|D=vue|S=dom,net,storage|RD=./README.ai -->
<template>
  <main class="login-page">
    <!-- 墨碑排印层：出血大字衬于夜色底与品牌簇/纸卡之间（纯装饰，样式在 auth-night.css） -->
    <div class="auth-monument" aria-hidden="true">
      <span class="auth-monument__char auth-monument__char--mo">墨</span>
      <span class="auth-monument__char auth-monument__char--feng">风</span>
    </div>

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

          <button type="submit" :disabled="isLoading" class="md-btn md-btn-primary md-ripple login-submit">
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
import { HttpRequestError } from '@/utils/errors'
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
    if (err instanceof HttpRequestError && err.code === 'timeout') {
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
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  padding: max(12px, env(safe-area-inset-top)) max(12px, env(safe-area-inset-right))
    max(12px, env(safe-area-inset-bottom)) max(12px, env(safe-area-inset-left));
  /* 夜色墨韵：固定深夜书房底（不随明暗主题切换），边缘径向压暗至夜深处，一次绘成 */
  background-color: var(--md-night-bg);
  background-image: radial-gradient(118% 92% at 50% 38%, transparent 52%, var(--md-night-bg-deep) 100%);
  color: var(--md-night-on);
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
  color: var(--md-night-on);
}

.login-panel {
  position: relative;
  z-index: 1;
  align-self: center;
  width: 100%;
  box-sizing: border-box;
  padding: clamp(20px, 2.2vw, 32px);
  /* 夜案纸卡：熟宣定值浮于夜色，无边框（影边不叠），深影承担浮起；
     卡内变量钉版见 auth-night.css（color-scheme: light，暗主题不混暗色控件） */
  border: 0;
  border-radius: var(--md-radius-xs);
  background:
    repeating-linear-gradient(90deg, transparent 0 39px, var(--md-miaohong-line) 39px 40px),
    linear-gradient(var(--md-night-paper), var(--md-night-paper));
  box-shadow: var(--md-night-elevation-2); /* 纸卡浮于夜案之上 */
  color: var(--md-on-surface);
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
  color: var(--md-on-surface);
  font-family: var(--md-font-serif);
  font-size: clamp(28px, 2.25vw, 38px);
  font-weight: 600;
  line-height: 1.2;
  letter-spacing: 0.08em;
}

/* 题字旁落印：朱砂实底钤章，印章无影 */
.login-card__header h2 span {
  width: clamp(18px, 1.4vw, 22px);
  height: clamp(18px, 1.4vw, 22px);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--md-secondary-dark);
  border-radius: var(--md-radius-xs);
  background-color: var(--md-secondary);
  color: var(--md-on-secondary);
  font-size: 12px;
  letter-spacing: 0;
  transform: rotate(-4deg);
}

.login-card__header p {
  margin: clamp(8px, 0.8vw, 12px) 0 0;
  color: var(--md-on-surface-variant);
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
  color: var(--md-on-surface);
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
  border: 1px solid var(--md-outline);
  border-radius: var(--md-radius-xs);
  background-color: var(--md-surface-container-low);
  color: var(--md-on-surface);
  font-family: var(--md-font-serif);
  font-size: clamp(13px, 0.96vw, 15px);
  letter-spacing: 0.03em;
  transition:
    background-color 180ms cubic-bezier(0.22, 1, 0.36, 1),
    border-color 180ms cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 180ms cubic-bezier(0.22, 1, 0.36, 1);
}

.md-text-field-input:focus {
  outline: none;
  border-color: var(--md-primary);
  background-color: var(--md-surface);
  box-shadow: var(--md-elevation-paper-1); /* 落笔浮起 */
}

/* 键盘焦点可见环（≥3:1），鼠标 focus 不重复显示 */
.md-text-field-input:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}

.md-text-field-input::placeholder {
  color: color-mix(in srgb, var(--md-on-surface-variant) 52%, transparent);
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
  color: color-mix(in srgb, var(--md-on-surface-variant) 65%, transparent);
  transform: translateY(-50%);
}

.md-text-field-icon--button {
  width: 44px;
  height: 44px;
  padding: 11px;
  border: 0;
  background: transparent;
  cursor: pointer;
  transition: color 150ms cubic-bezier(0.22, 1, 0.36, 1);
}

.md-text-field-icon--button:hover {
  color: var(--md-on-surface);
}

.login-options {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  color: var(--md-on-surface-variant);
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
  border: 1px solid var(--md-outline);
  background: var(--md-surface);
}

.login-remember input:checked + span {
  background: var(--md-secondary);
  border-color: var(--md-secondary-dark);
}

.login-remember input:focus-visible + span {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}

.login-feedback {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border: 1px dashed color-mix(in srgb, var(--md-secondary) 52%, transparent);
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

/* 落印钮：提交即钤章——配色/重力链/禁用态统一收编全局 .md-btn-primary（--md-btn-seal-*），
   此处仅保留整卷幅面与字号的版面覆写 */
.login-submit {
  width: 100%;
  min-height: clamp(48px, 3.55vw, 56px);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  font-family: var(--md-font-serif);
  font-size: clamp(14px, 1vw, 16px);
  font-weight: 600;
  letter-spacing: 0.14em;
  transition:
    background-color 180ms cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 180ms cubic-bezier(0.22, 1, 0.36, 1),
    transform 180ms cubic-bezier(0.22, 1, 0.36, 1);
}

.login-submit__mark {
  width: 18px;
  height: 18px;
  color: color-mix(in srgb, var(--md-btn-seal-text) 72%, transparent);
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
  color: var(--md-outline);
}

.login-divider::before,
.login-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--md-outline-variant), transparent);
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
  color: var(--md-on-surface-variant);
  font-size: 12px;
}

.login-oauth {
  min-height: 46px;
  margin-top: 10px;
  border-color: var(--md-outline);
  border-radius: var(--md-radius-xs);
  color: var(--md-on-surface);
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
  color: var(--md-on-surface-variant);
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
    box-shadow: var(--md-night-elevation-2); /* 纸卡浮于夜案之上 */
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
