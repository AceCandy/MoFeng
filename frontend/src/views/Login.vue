<!-- AIMETA P=登录页_用户登录|R=登录表单_认证|NR=不含注册功能|E=route:/login#component:Login|X=ui|A=登录表单|D=vue|S=dom,net,storage|RD=./README.ai -->
<template>
  <main class="login-page">
    <section class="login-scroll" aria-labelledby="login-title">
      <aside class="login-intro" aria-label="墨风">
        <span class="login-intro__spine" aria-hidden="true">墨风</span>

        <div class="login-intro__brand">
          <h1>墨风</h1>
          <span class="login-intro__seal" aria-hidden="true">墨</span>
          <p class="login-intro__kind">AI<br />长篇创作</p>
          <p class="login-intro__slogan">让每一次落笔，<br />都续写昨日的世界。</p>
        </div>

        <div class="login-intro__footmark" aria-hidden="true">
          <span class="login-intro__stamp">墨</span>
          <span>一案 · 一砚 · 一方长卷</span>
        </div>
      </aside>

      <section class="login-panel" aria-label="登录表单">
        <span class="login-panel__corner" aria-hidden="true"></span>

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
            <a class="login-forgot" href="#" @click.prevent="() => {}">忘记口令？</a>
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

      <ul class="login-feature-rail" aria-label="墨风创作流程">
        <li v-for="item in featureRail" :key="item.title">
          <span class="login-feature-rail__icon" aria-hidden="true" v-html="item.icon"></span>
          <span class="login-feature-rail__copy">
            <strong>{{ item.title }}</strong>
            <small>{{ item.desc }}</small>
          </span>
        </li>
      </ul>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthOptionsQuery, useLoginMutation } from '@/queries/auth'

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

const featureRail = [
  {
    title: '谋篇',
    desc: '构建世界与大纲',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M18 3 4 17l-1 4 4-1L21 6l-3-3Z" stroke-linecap="round" stroke-linejoin="round"/><path d="m14 7 3 3M4 20c.8-.5 1.4-1.1 2-2" stroke-linecap="round"/></svg>',
  },
  {
    title: '塑魂',
    desc: '刻画人物与成长',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="12" cy="7" r="3"/><path d="M5 20c0-4 3-6 7-6s7 2 7 6" stroke-linecap="round"/></svg>',
  },
  {
    title: '织线',
    desc: '伏笔线索与结构',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M12 9c-3 0-5 3.5-5 7.5S9.5 21 12 21s5-1 5-4.5S15 9 12 9Z" stroke-linejoin="round"/><path d="M12 9V3M10 5h4M11.5 9v11M12.5 9v11" stroke-linecap="round"/></svg>',
  },
  {
    title: '润色',
    desc: '文风润色与优化',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="4" y="6" width="16" height="12" rx="2" stroke-linejoin="round"/><ellipse cx="12" cy="12" rx="5" ry="3"/><path d="M12 10c.6-.6 1-1.4 1-2s-.4-1-1-1-1 .4-1 1 1 1.4 1 2Z" fill="currentColor"/></svg>',
  },
  {
    title: '校牍',
    desc: '一致性与纠错',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M5 4h14v16H5V4Z" stroke-linejoin="round"/><path d="M7 4v16M7 6h2M7 10h2M7 14h2M12 6h3v6h-3V6Z" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  },
]

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
  --auth-ink: #1c2022;
  --auth-ink-soft: #556265;
  --auth-line: #c4b99f;
  --auth-line-soft: #ded3bd;
  --auth-vermilion: #8c241c;
  --auth-paper-field: rgba(253, 250, 240, 0.52);
  --md-secondary-readable: #8c241c;

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
    url('../assets/mofeng_login_bg_v2.png') center / cover,
    #d8cbb7;
  color: var(--auth-ink);
}

.login-scroll {
  width: min(96vw, 1600px);
  max-height: calc(100vh - 24px);
  aspect-ratio: 16 / 9;
  position: relative;
  flex: 0 1 auto;
  overflow: hidden;
  background-image: url('../assets/mofeng_login_composite_v4.png');
  background-position: center;
  background-size: cover;
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

.login-intro,
.login-panel,
.login-feature-rail {
  z-index: 1;
  position: absolute;
}

.login-intro {
  top: 8.2%;
  left: 11.55%;
  width: 35.35%;
  height: 77.8%;
  pointer-events: none;
}

.login-intro__spine {
  position: absolute;
  top: 9.6%;
  left: 8.8%;
  color: rgba(58, 70, 72, 0.56);
  font-family: var(--md-font-serif);
  font-size: clamp(11px, 0.96vw, 15px);
  letter-spacing: 0.18em;
  writing-mode: vertical-rl;
}

.login-intro__brand {
  position: absolute;
  top: 11.4%;
  left: 34%;
  width: 45%;
  height: 64%;
}

.login-intro__brand h1 {
  position: absolute;
  top: 0;
  left: 0;
  margin: 0;
  color: rgba(28, 32, 34, 0.96);
  font-family: var(--md-font-serif);
  font-size: clamp(56px, 5.1vw, 88px);
  font-weight: 600;
  line-height: 1.02;
  letter-spacing: 0.06em;
  writing-mode: vertical-rl;
  text-shadow: 0 0 10px rgba(247, 239, 220, 0.92);
}

.login-intro__seal {
  position: absolute;
  top: 45%;
  left: 49%;
  width: clamp(22px, 1.9vw, 30px);
  height: clamp(22px, 1.9vw, 30px);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 2px solid var(--auth-vermilion);
  background: rgba(239, 226, 201, 0.42);
  color: var(--auth-vermilion);
  font-family: var(--md-font-serif);
  font-size: clamp(13px, 1.1vw, 18px);
  font-weight: 600;
  line-height: 1;
}

.login-intro__kind,
.login-intro__slogan {
  margin: 0;
  color: rgba(28, 32, 34, 0.9);
  font-family: var(--md-font-serif);
  writing-mode: vertical-rl;
  text-shadow: 0 0 10px rgba(247, 239, 220, 0.86);
}

.login-intro__kind {
  position: absolute;
  top: 23.5%;
  left: 65.5%;
  color: rgba(58, 70, 72, 0.86);
  font-size: clamp(12px, 1vw, 17px);
  font-weight: 600;
  line-height: 1.7;
  letter-spacing: 0.18em;
}

.login-intro__slogan {
  position: absolute;
  top: 54%;
  left: 51%;
  font-size: clamp(14px, 1.32vw, 22px);
  font-weight: 600;
  line-height: 1.82;
  letter-spacing: 0.17em;
}

.login-intro__footmark {
  position: absolute;
  left: 8.2%;
  bottom: 3.6%;
  display: inline-flex;
  align-items: center;
  gap: clamp(8px, 0.9vw, 14px);
  color: rgba(28, 32, 34, 0.78);
  font-family: var(--md-font-serif);
  font-size: clamp(11px, 0.9vw, 14px);
  letter-spacing: 0.08em;
}

.login-intro__stamp {
  width: clamp(29px, 2.4vw, 38px);
  height: clamp(29px, 2.4vw, 38px);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 2px solid var(--auth-vermilion);
  color: var(--auth-vermilion);
  font-size: clamp(15px, 1.35vw, 21px);
  font-weight: 600;
  line-height: 1;
}

.login-panel {
  top: 18.3%;
  left: 53.15%;
  width: 28.7%;
  box-sizing: border-box;
  color: var(--auth-ink);
}

.login-panel__corner {
  display: none;
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
  border-radius: 2px;
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
  border-color: var(--auth-vermilion);
  background-color: rgba(253, 251, 245, 0.9);
  box-shadow:
    inset 0 0 0 1px rgba(255, 251, 241, 0.75),
    2px 2px 0 rgba(140, 36, 28, 0.12);
}

.md-text-field-input::placeholder {
  color: rgba(85, 98, 101, 0.52);
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
  color: rgba(85, 98, 101, 0.65);
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
  background: var(--auth-vermilion);
  border-color: var(--auth-vermilion);
}

.login-remember input:focus-visible + span {
  outline: 2px solid var(--auth-line);
  outline-offset: 2px;
}

.login-forgot {
  color: var(--auth-ink-soft);
  text-decoration: none;
  transition: color 150ms cubic-bezier(0.22, 1, 0.36, 1);
}

.login-forgot:hover {
  color: var(--md-secondary-readable);
}

.login-feedback {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border: 1px dashed rgba(140, 36, 28, 0.52);
  border-radius: 3px;
  background: rgba(251, 235, 234, 0.84);
  color: #6f1d16;
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
  border: 1px solid rgba(28, 32, 34, 0.75);
  border-radius: 2px;
  background:
    linear-gradient(90deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0)),
    #1c2022;
  color: #f4ecda;
  font-family: var(--md-font-serif);
  font-size: clamp(14px, 1vw, 16px);
  font-weight: 600;
  letter-spacing: 0.14em;
  box-shadow: 2px 2px 0 rgba(28, 32, 34, 0.2);
  transition:
    background-color 180ms cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 180ms cubic-bezier(0.22, 1, 0.36, 1),
    transform 180ms cubic-bezier(0.22, 1, 0.36, 1);
}

.login-submit:hover:not(:disabled) {
  background-color: #262d2f;
  box-shadow: 3px 3px 0 rgba(28, 32, 34, 0.24);
}

.login-submit:active:not(:disabled) {
  transform: translate(1px, 1px);
  box-shadow: 1px 1px 0 rgba(28, 32, 34, 0.22);
}

.login-submit:disabled {
  opacity: 0.68;
  cursor: not-allowed;
}

.login-submit__mark {
  width: 18px;
  height: 18px;
  color: #c9ad7a;
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
  border-radius: 2px;
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

.login-feature-rail {
  left: 15.2%;
  right: 12.8%;
  bottom: 4.6%;
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: clamp(10px, 1.9vw, 34px);
  padding: 0;
  margin: 0;
  list-style: none;
  color: rgba(28, 32, 34, 0.76);
}

.login-feature-rail li {
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: clamp(7px, 0.75vw, 12px);
}

.login-feature-rail__icon {
  width: clamp(24px, 2.1vw, 34px);
  height: clamp(24px, 2.1vw, 34px);
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  color: rgba(28, 32, 34, 0.76);
  filter: drop-shadow(0 2px 3px rgba(28, 32, 34, 0.16));
}

.login-feature-rail__icon :deep(svg) {
  width: clamp(20px, 1.7vw, 27px);
  height: clamp(20px, 1.7vw, 27px);
}

.login-feature-rail__copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.login-feature-rail strong {
  font-family: var(--md-font-serif);
  font-size: clamp(12px, 0.94vw, 15px);
  font-weight: 600;
  letter-spacing: 0.06em;
}

.login-feature-rail small {
  color: rgba(85, 98, 101, 0.78);
  font-size: clamp(10px, 0.75vw, 12px);
  white-space: nowrap;
}

@media (max-width: 1024px) {
  .login-scroll {
    width: min(98vw, 1600px);
  }

  .login-panel {
    top: 17%;
    left: 52.9%;
    width: 30.2%;
  }

  .login-feature-rail {
    left: 14.5%;
    right: 13.8%;
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
    max-height: none;
    min-height: max(980px, calc(100vh + 120px));
    aspect-ratio: auto;
    background-image: url('../assets/mofeng_login_scene_v3.png');
    background-position: center -96px;
    background-repeat: no-repeat;
    background-size: 100% auto;
    border-radius: 8px;
  }

  .login-intro {
    top: clamp(84px, calc((100vw - 12px) * 0.24), 130px);
    left: 4.2%;
    width: 88.4%;
    height: clamp(250px, calc((100vw - 12px) * 0.68), 340px);
  }

  .login-intro__spine {
    top: 6%;
    left: 3%;
    font-size: 13px;
  }

  .login-intro__brand {
    top: 8%;
    left: 9%;
    width: 46%;
    height: 72%;
  }

  .login-intro__brand h1 {
    font-size: 52px;
  }

  .login-intro__seal {
    width: 28px;
    height: 28px;
    top: 58%;
    left: 47%;
    font-size: 16px;
  }

  .login-intro__kind {
    top: 1%;
    left: 62%;
    font-size: 12px;
    line-height: 1.5;
    letter-spacing: 0.14em;
  }

  .login-intro__slogan {
    top: 63%;
    left: 0;
    width: 126px;
    writing-mode: horizontal-tb;
    font-size: 15px;
    line-height: 1.55;
    letter-spacing: 0.08em;
  }

  .login-intro__footmark {
    top: 48%;
    right: 6%;
    left: auto;
    bottom: auto;
    width: clamp(158px, 38vw, 188px);
    box-sizing: border-box;
    gap: 8px;
    padding: 6px 0;
    background: transparent;
    font-size: 11.5px;
    letter-spacing: 0.04em;
    text-shadow: 0 0 8px rgba(250, 244, 229, 0.95);
  }

  .login-intro__stamp {
    width: 30px;
    height: 30px;
    font-size: 16px;
  }

  .login-panel {
    top: clamp(372px, calc((100vw - 12px) * 1.04), 440px);
    left: 6.8%;
    right: 6.8%;
    width: auto;
    padding: 22px 18px 24px;
    border: 1px solid rgba(176, 159, 128, 0.62);
    border-radius: 4px;
    background:
      linear-gradient(180deg, rgba(253, 250, 241, 0.9), rgba(247, 239, 222, 0.94)),
      rgba(250, 246, 237, 0.9);
    box-shadow:
      0 12px 22px rgba(42, 35, 25, 0.18),
      inset 0 0 0 1px rgba(255, 251, 242, 0.7);
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

  .login-feature-rail {
    display: none;
  }
}

@media (max-width: 390px) {
  .login-intro__brand {
    left: 40px;
  }

  .login-intro__kind {
    left: 116px;
  }

  .login-intro__slogan {
    left: 0;
  }

  .login-intro__footmark {
    top: 148px;
    right: 16px;
    width: 156px;
  }

  .login-panel {
    left: 5.2%;
    right: 5.2%;
    padding-left: 16px;
    padding-right: 16px;
  }
}

@keyframes md-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
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
