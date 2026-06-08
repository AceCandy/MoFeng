<!-- AIMETA P=注册页_用户注册|R=注册表单|NR=不含登录功能|E=route:/register#component:Register|X=ui|A=注册表单|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <main class="register-page">
    <section class="register-scroll" aria-labelledby="register-title">
      <aside class="register-intro" aria-label="墨风">
        <span class="register-intro__spine" aria-hidden="true">墨风</span>

        <div class="register-intro__brand">
          <h1>墨风</h1>
          <span class="register-intro__seal" aria-hidden="true">墨</span>
          <p class="register-intro__kind">AI<br />长篇创作</p>
          <p class="register-intro__slogan">让每一次落笔，<br />都续写昨日的世界。</p>
        </div>

        <div class="register-intro__footmark" aria-hidden="true">
          <span class="register-intro__stamp">墨</span>
          <span>一案 · 一砚 · 一方长卷</span>
        </div>
      </aside>

      <section class="register-panel" aria-label="注册表单">
        <span class="register-panel__corner" aria-hidden="true"></span>

        <div v-if="allowRegistration" class="register-panel__content">
          <div class="register-card__header">
            <h2 id="register-title">
              开新卷
              <span aria-hidden="true">启</span>
            </h2>
            <p>开启你的创作新篇章</p>
          </div>

          <form class="register-form" @submit.prevent="handleRegister">
            <div class="md-text-field">
              <label for="username" class="md-text-field-label">用户名</label>
              <div class="md-text-field-wrapper">
                <input
                  id="username"
                  v-model="username"
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
                <span class="md-text-field-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
                    <path
                      d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    />
                  </svg>
                </span>
              </div>
            </div>

            <div class="md-text-field">
              <label for="email" class="md-text-field-label">邮箱</label>
              <div class="md-text-field-wrapper">
                <input
                  id="email"
                  v-model="email"
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
                <span class="md-text-field-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
                    <path
                      d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2Z"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    />
                    <path d="m22 6-10 7L2 6" stroke-linecap="round" stroke-linejoin="round" />
                  </svg>
                </span>
              </div>
            </div>

            <div class="register-code-row">
              <div class="md-text-field">
                <label for="verificationCode" class="md-text-field-label">验证码</label>
                <div class="md-text-field-wrapper">
                  <input
                    id="verificationCode"
                    v-model="verificationCode"
                    name="verificationCode"
                    type="text"
                    required
                    :aria-invalid="Boolean(error)"
                    :aria-describedby="error ? 'register-error' : undefined"
                    class="md-text-field-input"
                    placeholder="验证码"
                    inputmode="numeric"
                    autocomplete="one-time-code"
                    maxlength="12"
                    spellcheck="false"
                    autocapitalize="none"
                  />
                </div>
              </div>
              <button
                type="button"
                class="md-ripple register-code-button"
                :disabled="countdown > 0 || sending"
                @click="sendCode"
              >
                <span v-if="sending">发送中...</span>
                <span v-else>{{ countdown > 0 ? countdown + '秒后重试' : '发送验证码' }}</span>
              </button>
            </div>

            <div class="md-text-field">
              <label for="password" class="md-text-field-label">密码</label>
              <div class="md-text-field-wrapper">
                <input
                  id="password"
                  v-model="password"
                  name="password"
                  :type="showPassword ? 'text' : 'password'"
                  required
                  :aria-invalid="Boolean(error)"
                  :aria-describedby="error ? 'register-error' : undefined"
                  class="md-text-field-input"
                  placeholder="至少 8 个字符"
                  autocomplete="new-password"
                  minlength="8"
                  maxlength="256"
                />
                <button
                  type="button"
                  class="md-text-field-icon md-text-field-icon--button"
                  :aria-label="showPassword ? '隐藏密码' : '显示密码'"
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
              {{ isRegistering ? '正在开卷...' : '开卷写意' }}
            </button>
          </form>

          <div class="register-divider" aria-hidden="true">
            <span></span>
          </div>

          <div class="register-link">
            <span>已有账户？</span>
            <router-link to="/login" class="md-btn md-btn-text md-ripple register-link__cta">
              立即登录
            </router-link>
          </div>
        </div>

        <div v-else class="register-closed-panel">
          <h2 id="register-title">暂未开放注册</h2>
          <p>请联系管理员或稍后再试。</p>
          <router-link to="/login" class="register-closed-btn md-btn md-btn-outlined md-ripple">
            返回登录
          </router-link>
        </div>
      </section>

      <div class="register-scroll__roller" aria-hidden="true">
        <span></span>
      </div>
    </section>

    <ul class="register-feature-rail" aria-label="墨风创作流程">
      <li v-for="item in featureRail" :key="item.title">
        <span class="register-feature-rail__icon" aria-hidden="true" v-html="item.icon"></span>
        <span class="register-feature-rail__copy">
          <strong>{{ item.title }}</strong>
          <small>{{ item.desc }}</small>
        </span>
      </li>
    </ul>
  </main>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  useAuthOptionsQuery,
  useRegisterMutation,
  useSendVerificationCodeMutation,
} from '@/queries/auth'

const username = ref('')
const email = ref('')
const verificationCode = ref('')
const password = ref('')
const showPassword = ref(false)
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

  if (password.value.length < 8) {
    return '密码必须至少8个字符'
  }

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

  return null
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
  --auth-ink: #1c2022;
  --auth-ink-soft: #556265;
  --auth-paper: #f8f2e4;
  --auth-paper-deep: #eadfc8;
  --auth-paper-light: #fbf7ec;
  --auth-line: #c4b99f;
  --auth-line-soft: #ded3bd;
  --auth-shadow: rgba(28, 32, 34, 0.18);
  --auth-vermilion: #8c241c;

  min-height: var(--app-viewport-unit);
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: clamp(22px, 3vw, 36px);
  overflow-x: hidden;
  padding:
    max(38px, env(safe-area-inset-top))
    max(44px, env(safe-area-inset-right))
    max(30px, env(safe-area-inset-bottom))
    max(44px, env(safe-area-inset-left));
  background-color: #d9cebc;
  background-image: url('../assets/mofeng_login_bg_v2.png');
  background-position: center;
  background-size: cover;
  color: var(--auth-ink);
}

.register-page::before {
  content: '';
  position: fixed;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(circle at 50% 48%, rgba(252, 246, 231, 0.32), transparent 38%),
    linear-gradient(180deg, rgba(45, 39, 29, 0.08), rgba(45, 39, 29, 0.14));
  z-index: 0;
}

.register-scroll {
  width: min(88vw, 1180px);
  min-height: clamp(580px, 72vh, 720px);
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(360px, 0.9fr) minmax(420px, 1.1fr);
  background: var(--auth-paper);
  border: 1px solid rgba(148, 132, 105, 0.48);
  border-radius: 5px;
  box-shadow:
    0 24px 44px var(--auth-shadow),
    0 4px 0 rgba(104, 86, 58, 0.08),
    inset 0 0 0 1px rgba(255, 251, 240, 0.72);
}

.register-scroll::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    linear-gradient(90deg, transparent 0 48.3%, rgba(42, 36, 28, 0.14) 49.5%, rgba(255, 255, 255, 0.18) 50.2%, transparent 52%),
    repeating-linear-gradient(90deg, rgba(28, 32, 34, 0.018) 0 1px, transparent 1px 14px);
  z-index: 2;
}

.register-intro,
.register-panel {
  min-width: 0;
  position: relative;
}

.register-intro {
  overflow: hidden;
  border-radius: 5px 0 0 5px;
  background-color: #eadfca;
  background-image:
    linear-gradient(rgba(236, 225, 205, 0.12), rgba(236, 225, 205, 0.12)),
    url('../assets/mofeng_scroll_left_v2.png');
  background-position: center;
  background-size: cover;
}

.register-intro::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(circle at 62% 18%, rgba(251, 246, 232, 0.5), transparent 25%),
    linear-gradient(180deg, rgba(246, 238, 219, 0.42), rgba(236, 225, 202, 0.16));
}

.register-intro__spine {
  position: absolute;
  top: 72px;
  left: 56px;
  z-index: 1;
  color: rgba(58, 70, 72, 0.56);
  font-family: var(--md-font-serif);
  font-size: 15px;
  letter-spacing: 0.18em;
  writing-mode: vertical-rl;
}

.register-intro__brand {
  position: absolute;
  top: 104px;
  left: 186px;
  z-index: 1;
  width: 290px;
  height: 420px;
}

.register-intro__brand h1 {
  position: absolute;
  top: 0;
  left: 0;
  margin: 0;
  color: rgba(28, 32, 34, 0.96);
  font-family: var(--md-font-serif);
  font-size: clamp(64px, 5.3vw, 86px);
  font-weight: 600;
  line-height: 1.02;
  letter-spacing: 0.06em;
  writing-mode: vertical-rl;
  text-shadow: 0 0 10px rgba(247, 239, 220, 0.86);
}

.register-intro__seal {
  position: absolute;
  top: 182px;
  left: 116px;
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 2px solid var(--auth-vermilion);
  background: rgba(239, 226, 201, 0.42);
  color: var(--auth-vermilion);
  font-family: var(--md-font-serif);
  font-size: 18px;
  font-weight: 600;
  line-height: 1;
}

.register-intro__kind,
.register-intro__slogan {
  margin: 0;
  color: rgba(28, 32, 34, 0.9);
  font-family: var(--md-font-serif);
  writing-mode: vertical-rl;
  text-shadow: 0 0 10px rgba(247, 239, 220, 0.86);
}

.register-intro__kind {
  position: absolute;
  top: 96px;
  left: 154px;
  color: rgba(58, 70, 72, 0.86);
  font-size: 17px;
  font-weight: 600;
  line-height: 1.7;
  letter-spacing: 0.18em;
}

.register-intro__slogan {
  position: absolute;
  top: 250px;
  left: 134px;
  font-size: clamp(18px, 1.45vw, 22px);
  font-weight: 600;
  line-height: 1.82;
  letter-spacing: 0.17em;
}

.register-intro__footmark {
  position: absolute;
  left: 56px;
  bottom: 48px;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  gap: 14px;
  color: rgba(28, 32, 34, 0.78);
  font-family: var(--md-font-serif);
  font-size: 14px;
  letter-spacing: 0.08em;
}

.register-intro__stamp {
  width: 38px;
  height: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 2px solid var(--auth-vermilion);
  color: var(--auth-vermilion);
  font-size: 21px;
  font-weight: 600;
  line-height: 1;
}

.register-panel {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 50px clamp(64px, 6vw, 96px);
  border-radius: 0 5px 5px 0;
  background:
    radial-gradient(circle at 91% 94%, rgba(86, 92, 83, 0.12), transparent 25%),
    linear-gradient(180deg, rgba(255, 252, 244, 0.7), rgba(249, 242, 228, 0.94)),
    var(--auth-paper-light);
}

.register-panel::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: repeating-linear-gradient(90deg, rgba(28, 32, 34, 0.016) 0 1px, transparent 1px 15px);
  mix-blend-mode: multiply;
}

.register-panel__corner {
  position: absolute;
  top: 24px;
  right: 24px;
  width: 48px;
  height: 48px;
  color: rgba(141, 128, 105, 0.35);
  background:
    linear-gradient(currentColor, currentColor) left top / 100% 1px no-repeat,
    linear-gradient(currentColor, currentColor) right top / 1px 100% no-repeat,
    linear-gradient(currentColor, currentColor) 11px 11px / calc(100% - 11px) 1px no-repeat,
    linear-gradient(currentColor, currentColor) right 11px top 11px / 1px calc(100% - 11px) no-repeat;
}

.register-panel__content,
.register-closed-panel,
.register-card__header,
.register-form,
.register-divider,
.register-link {
  width: min(100%, 430px);
  margin-left: auto;
  margin-right: auto;
  position: relative;
  z-index: 1;
}

.register-card__header {
  margin-bottom: 24px;
}

.register-card__header h2,
.register-closed-panel h2 {
  display: flex;
  align-items: center;
  gap: 14px;
  margin: 0;
  color: var(--auth-ink);
  font-family: var(--md-font-serif);
  font-size: 35px;
  font-weight: 600;
  line-height: 1.2;
  letter-spacing: 0.08em;
}

.register-card__header h2 span {
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1.5px solid var(--auth-vermilion);
  color: var(--auth-vermilion);
  font-size: 12px;
  letter-spacing: 0;
}

.register-card__header p,
.register-closed-panel p {
  margin: 10px 0 0;
  color: var(--auth-ink-soft);
  font-size: 14px;
  letter-spacing: 0.04em;
}

.register-form {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.md-text-field {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.md-text-field-label {
  color: var(--auth-ink);
  font-family: var(--md-font-serif);
  font-size: 13.5px;
  font-weight: 600;
  letter-spacing: 0.06em;
}

.md-text-field-wrapper {
  position: relative;
}

.md-text-field-input {
  width: 100%;
  height: 50px;
  padding: 0 50px 0 16px;
  border: 1px solid var(--auth-line);
  border-radius: 2px;
  background-color: rgba(253, 251, 245, 0.62);
  color: var(--auth-ink);
  font-family: var(--md-font-serif);
  font-size: 14.5px;
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
  right: 16px;
  width: 22px;
  height: 22px;
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

.register-code-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
  gap: 12px;
}

.register-code-row .md-text-field-input {
  padding-right: 16px;
}

.register-code-button {
  min-width: 118px;
  height: 50px;
  padding: 0 14px;
  border: 1px solid var(--auth-line);
  border-radius: 2px;
  background: rgba(253, 251, 245, 0.62);
  color: var(--auth-ink);
  font-family: var(--md-font-serif);
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  cursor: pointer;
  box-shadow: 1px 1px 0 rgba(28, 32, 34, 0.1);
  transition:
    background-color 180ms cubic-bezier(0.22, 1, 0.36, 1),
    border-color 180ms cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 180ms cubic-bezier(0.22, 1, 0.36, 1);
}

.register-code-button:hover:not(:disabled) {
  border-color: var(--auth-vermilion);
  background-color: rgba(253, 251, 245, 0.9);
  box-shadow: 2px 2px 0 rgba(140, 36, 28, 0.12);
}

.register-code-button:disabled {
  opacity: 0.62;
  cursor: not-allowed;
}

.register-feedback {
  padding: 10px 12px;
  border-radius: 3px;
  font-size: 13px;
  line-height: 1.5;
  text-align: center;
}

.register-feedback.is-error {
  border: 1px dashed rgba(140, 36, 28, 0.52);
  background: rgba(251, 235, 234, 0.84);
  color: #6f1d16;
}

.register-feedback.is-success {
  border: 1px dashed rgba(43, 108, 63, 0.48);
  background: rgba(234, 246, 238, 0.84);
  color: #1f5231;
}

.register-submit {
  width: 100%;
  min-height: 52px;
  border: 1px solid rgba(28, 32, 34, 0.75);
  border-radius: 2px;
  background:
    linear-gradient(90deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0)),
    #1c2022;
  color: #f4ecda;
  font-family: var(--md-font-serif);
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.14em;
  box-shadow: 2px 2px 0 rgba(28, 32, 34, 0.2);
  transition:
    background-color 180ms cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 180ms cubic-bezier(0.22, 1, 0.36, 1),
    transform 180ms cubic-bezier(0.22, 1, 0.36, 1);
}

.register-submit:hover:not(:disabled) {
  background-color: #262d2f;
  box-shadow: 3px 3px 0 rgba(28, 32, 34, 0.24);
}

.register-submit:active:not(:disabled) {
  transform: translate(1px, 1px);
  box-shadow: 1px 1px 0 rgba(28, 32, 34, 0.22);
}

.register-submit:disabled {
  opacity: 0.68;
  cursor: not-allowed;
}

.register-divider {
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 14px;
  color: var(--auth-line);
}

.register-divider::before,
.register-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--auth-line-soft), transparent);
}

.register-divider span {
  width: 18px;
  height: 18px;
  margin: 0 12px;
  border: 1px solid currentColor;
  transform: rotate(45deg);
}

.register-link {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin-top: 10px;
  color: var(--auth-ink-soft);
  font-family: var(--md-font-serif);
  font-size: 14px;
}

.register-link__cta {
  min-height: 44px;
  padding: 0 10px;
  color: var(--auth-vermilion);
  font-weight: 600;
}

.register-closed-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.register-closed-panel h2 {
  justify-content: center;
}

.register-closed-btn {
  min-height: 44px;
  margin-top: 24px;
  border-radius: 2px;
}

.register-scroll__roller {
  position: absolute;
  top: -18px;
  right: -32px;
  bottom: -18px;
  z-index: 3;
  width: 32px;
  display: flex;
  justify-content: center;
  filter: drop-shadow(8px 6px 10px rgba(28, 32, 34, 0.24));
}

.register-scroll__roller::before,
.register-scroll__roller::after {
  content: '';
  position: absolute;
  left: 0;
  width: 32px;
  height: 19px;
  border-radius: 5px;
  background: linear-gradient(90deg, #3c2c1d, #9a7856 34%, #d7bd8f 52%, #7e6043 74%, #2f2318);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.22),
    inset 0 -2px 1px rgba(0, 0, 0, 0.28);
}

.register-scroll__roller::before {
  top: 0;
}

.register-scroll__roller::after {
  bottom: 0;
}

.register-scroll__roller span {
  width: 20px;
  min-height: 100%;
  border-left: 1px solid rgba(255, 255, 255, 0.32);
  border-right: 1px solid rgba(66, 45, 27, 0.36);
  background:
    linear-gradient(90deg, rgba(79, 58, 36, 0.42), transparent 22%, transparent 74%, rgba(68, 49, 30, 0.34)),
    linear-gradient(90deg, #aa9a7f, #fbf0db 42%, #d5c2a4 78%, #8f8068);
}

.register-feature-rail {
  width: min(88vw, 1040px);
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: clamp(18px, 3vw, 38px);
  padding: 0;
  margin: 0;
  list-style: none;
  color: rgba(28, 32, 34, 0.76);
}

.register-feature-rail li {
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

.register-feature-rail__icon {
  width: 34px;
  height: 34px;
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  color: rgba(28, 32, 34, 0.76);
  filter: drop-shadow(0 2px 3px rgba(28, 32, 34, 0.16));
}

.register-feature-rail__icon :deep(svg) {
  width: 27px;
  height: 27px;
}

.register-feature-rail__copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.register-feature-rail strong {
  font-family: var(--md-font-serif);
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.06em;
}

.register-feature-rail small {
  color: rgba(85, 98, 101, 0.78);
  font-size: 12px;
  white-space: nowrap;
}

@media (max-width: 1024px) {
  .register-scroll {
    grid-template-columns: minmax(300px, 0.9fr) minmax(380px, 1.1fr);
  }

  .register-panel {
    padding: 44px 46px;
  }

  .register-feature-rail {
    grid-template-columns: repeat(3, minmax(180px, 1fr));
  }
}

@media (max-width: 833px) {
  .register-page {
    justify-content: flex-start;
    gap: 22px;
    padding: max(18px, env(safe-area-inset-top)) 10px max(18px, env(safe-area-inset-bottom));
    background-position: 46% center;
  }

  .register-scroll {
    width: min(100%, 500px);
    min-height: auto;
    display: block;
    overflow: hidden;
    border-radius: 10px;
  }

  .register-scroll::before {
    background:
      linear-gradient(180deg, transparent 0 31%, rgba(42, 36, 28, 0.1) 32%, rgba(255, 255, 255, 0.18) 33%, transparent 34%),
      repeating-linear-gradient(90deg, rgba(28, 32, 34, 0.016) 0 1px, transparent 1px 14px);
  }

  .register-intro {
    min-height: 276px;
    border-radius: 10px 10px 0 0;
    background-position: 42% center;
  }

  .register-intro__spine {
    top: 28px;
    left: 24px;
    font-size: 13px;
  }

  .register-intro__brand {
    top: 54px;
    left: 58px;
    width: 250px;
    height: 178px;
  }

  .register-intro__brand h1 {
    font-size: 50px;
  }

  .register-intro__seal {
    width: 28px;
    height: 28px;
    top: 118px;
    left: 86px;
    font-size: 16px;
  }

  .register-intro__kind {
    position: absolute;
    top: 2px;
    left: 126px;
    margin: 0;
    font-size: 12px;
    line-height: 1.5;
    letter-spacing: 0.14em;
  }

  .register-intro__slogan {
    top: 128px;
    left: 0;
    width: 126px;
    writing-mode: horizontal-tb;
    font-size: 15px;
    line-height: 1.55;
    letter-spacing: 0.08em;
  }

  .register-intro__footmark {
    right: 18px;
    left: auto;
    bottom: 30px;
    width: 166px;
    box-sizing: border-box;
    gap: 8px;
    padding: 8px 9px;
    background: rgba(240, 231, 211, 0.42);
    font-size: 11px;
    letter-spacing: 0.04em;
  }

  .register-intro__stamp {
    width: 30px;
    height: 30px;
    font-size: 16px;
  }

  .register-panel {
    padding: 32px 24px 30px;
    border-radius: 0 0 10px 10px;
  }

  .register-panel__corner {
    display: none;
  }

  .register-card__header {
    margin-bottom: 22px;
  }

  .register-card__header h2,
  .register-closed-panel h2 {
    font-size: 30px;
  }

  .register-form {
    gap: 14px;
  }

  .register-code-row {
    grid-template-columns: 1fr;
  }

  .register-code-button {
    width: 100%;
  }

  .register-link {
    flex-wrap: wrap;
  }

  .register-scroll__roller,
  .register-feature-rail {
    display: none;
  }
}

@media (max-width: 390px) {
  .register-intro__brand {
    left: 52px;
  }

  .register-intro__kind {
    left: 120px;
  }

  .register-intro__slogan {
    left: 0;
  }

  .register-intro__footmark {
    right: 18px;
    max-width: 230px;
  }

  .register-panel {
    padding-left: 18px;
    padding-right: 18px;
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
