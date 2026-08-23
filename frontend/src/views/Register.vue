<!-- AIMETA P=注册页_用户注册|R=注册表单|NR=不含登录功能|E=route:/register#component:Register|X=ui|A=注册表单|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <main class="register-page">
    <!-- 墨碑排印层：出血大字衬于暖纸底与品牌簇/纸卡之间（纯装饰） -->
    <div class="auth-monument" aria-hidden="true">
      <span class="auth-monument__char auth-monument__char--mo">墨</span>
      <span class="auth-monument__char auth-monument__char--feng">风</span>
    </div>

    <section class="register-scroll" aria-labelledby="register-title">
      <AuthIntro variant="register" />

      <section class="register-panel" aria-label="注册表单">
        <div v-if="allowRegistration" class="register-panel__content">
          <div class="register-card__header">
            <h2 id="register-title">
              开新卷
              <span aria-hidden="true">启</span>
            </h2>
            <p>开启你的创作新篇章</p>
          </div>

          <form class="register-form" novalidate @submit.prevent="handleRegister">
            <div class="md-text-field">
              <label for="username" class="md-text-field-label">用户名</label>
              <div class="md-text-field-wrapper">
                <input
                  id="username"
                  ref="usernameInputRef"
                  v-model="username"
                  name="username"
                  type="text"
                  required
                  :aria-invalid="Boolean(fieldErrors.username)"
                  :aria-describedby="fieldErrors.username ? 'username-help username-error' : 'username-help'"
                  class="md-text-field-input"
                  placeholder="请输入用户名"
                  autocomplete="username"
                  maxlength="64"
                  spellcheck="false"
                  autocapitalize="none"
                  @input="fieldErrors.username = ''"
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
              <p id="username-help" class="register-field-help">
                中文至少 2 个字符；字母或数字组合至少 7 位，且不能为纯数字。
              </p>
              <p v-if="fieldErrors.username" id="username-error" class="register-field-error">
                {{ fieldErrors.username }}
              </p>
            </div>

            <div class="md-text-field">
              <label for="email" class="md-text-field-label">邮箱</label>
              <div class="md-text-field-wrapper">
                <input
                  id="email"
                  ref="emailInputRef"
                  v-model="email"
                  name="email"
                  type="email"
                  required
                  :aria-invalid="Boolean(fieldErrors.email)"
                  :aria-describedby="fieldErrors.email ? 'email-error' : undefined"
                  class="md-text-field-input"
                  placeholder="请输入邮箱"
                  autocomplete="email"
                  maxlength="254"
                  spellcheck="false"
                  autocapitalize="none"
                  @input="fieldErrors.email = ''"
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
              <p v-if="fieldErrors.email" id="email-error" class="register-field-error">
                {{ fieldErrors.email }}
              </p>
            </div>

            <div class="register-code-row">
              <div class="md-text-field">
                <label for="verificationCode" class="md-text-field-label">验证码</label>
                <div class="md-text-field-wrapper">
                  <input
                    id="verificationCode"
                    ref="verificationCodeInputRef"
                    v-model="verificationCode"
                    name="verificationCode"
                    type="text"
                    required
                    :aria-invalid="Boolean(fieldErrors.verificationCode)"
                    :aria-describedby="fieldErrors.verificationCode ? 'verification-code-error' : undefined"
                    class="md-text-field-input"
                    placeholder="验证码"
                    inputmode="numeric"
                    autocomplete="one-time-code"
                    maxlength="12"
                    spellcheck="false"
                    autocapitalize="none"
                    @input="fieldErrors.verificationCode = ''"
                  />
                </div>
                <p
                  v-if="fieldErrors.verificationCode"
                  id="verification-code-error"
                  class="register-field-error"
                >
                  {{ fieldErrors.verificationCode }}
                </p>
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
                  ref="passwordInputRef"
                  v-model="password"
                  name="password"
                  :type="showPassword ? 'text' : 'password'"
                  required
                  :aria-invalid="Boolean(fieldErrors.password)"
                  :aria-describedby="fieldErrors.password ? 'password-help password-error' : 'password-help'"
                  class="md-text-field-input"
                  placeholder="至少 8 个字符"
                  autocomplete="new-password"
                  minlength="8"
                  maxlength="256"
                  @input="fieldErrors.password = ''"
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
              <p id="password-help" class="register-field-help">至少 8 个字符。</p>
              <p v-if="fieldErrors.password" id="password-error" class="register-field-error">
                {{ fieldErrors.password }}
              </p>
            </div>

            <Transition name="ink-fade">
              <div v-if="error" id="register-error" class="register-feedback is-error" role="alert">
                <span class="register-feedback__stamp" aria-hidden="true">误</span>
                <span>{{ error }}</span>
              </div>
            </Transition>
            <Transition name="ink-fade">
              <div v-if="success" class="register-feedback is-success" role="status">
                <span class="register-feedback__stamp" aria-hidden="true">成</span>
                <span>{{ success }}</span>
              </div>
            </Transition>

            <button
              type="submit"
              class="md-btn md-btn-primary md-ripple register-submit"
              :disabled="isRegistering"
            >
              <svg v-if="isRegistering" class="register-spinner" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="3" opacity="0.25" />
                <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" stroke-width="3" stroke-linecap="round" />
              </svg>
              <span>{{ isRegistering ? '正在开卷...' : '开卷写意' }}</span>
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
    </section>

    <AuthFeatureRail />
  </main>
</template>

<script setup lang="ts">
import { computed, onUnmounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  useAuthOptionsQuery,
  useRegisterMutation,
  useSendVerificationCodeMutation,
} from '@/queries/auth'
import AuthIntro from '@/components/auth/AuthIntro.vue'
import AuthFeatureRail from '@/components/auth/AuthFeatureRail.vue'

const username = ref('')
const email = ref('')
const verificationCode = ref('')
const password = ref('')
const showPassword = ref(false)
const countdown = ref(0)
const error = ref('')
const success = ref('')
const usernameInputRef = ref<HTMLInputElement | null>(null)
const emailInputRef = ref<HTMLInputElement | null>(null)
const verificationCodeInputRef = ref<HTMLInputElement | null>(null)
const passwordInputRef = ref<HTMLInputElement | null>(null)
const fieldErrors = reactive({
  username: '',
  email: '',
  verificationCode: '',
  password: '',
})
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

const clearFieldErrors = () => {
  fieldErrors.username = ''
  fieldErrors.email = ''
  fieldErrors.verificationCode = ''
  fieldErrors.password = ''
}

const validateInput = () => {
  clearFieldErrors()
  const usernameVal = username.value.trim()
  const emailVal = email.value.trim()
  const hasChinese = /[\u4e00-\u9fa5]/.test(usernameVal)
  const isNumeric = /^\d+$/.test(usernameVal)
  const isAlphanumeric = /^[a-zA-Z0-9]+$/.test(usernameVal)

  if (!usernameVal) fieldErrors.username = '请输入用户名'
  else if (isNumeric) fieldErrors.username = '用户名不能是纯数字'
  else if (hasChinese && usernameVal.length <= 1) fieldErrors.username = '用户名至少需要 2 个字符'
  else if (isAlphanumeric && !hasChinese && usernameVal.length <= 6) {
    fieldErrors.username = '用户名长度必须大于 6 个字母或数字'
  }

  if (!emailVal) fieldErrors.email = '请输入邮箱'
  else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailVal)) fieldErrors.email = '邮箱格式不正确'
  if (!verificationCode.value.trim()) fieldErrors.verificationCode = '请输入验证码'
  if (password.value.length < 8) fieldErrors.password = '密码必须至少 8 个字符'

  return !Object.values(fieldErrors).some(Boolean)
}

const focusFirstFieldError = () => {
  if (fieldErrors.username) usernameInputRef.value?.focus()
  else if (fieldErrors.email) emailInputRef.value?.focus()
  else if (fieldErrors.verificationCode) verificationCodeInputRef.value?.focus()
  else if (fieldErrors.password) passwordInputRef.value?.focus()
}

const sendCode = async () => {
  error.value = ''
  success.value = ''
  fieldErrors.email = ''
  const normalizedEmail = email.value.trim()

  if (!allowRegistration.value) {
    error.value = '当前已关闭注册，请联系管理员。'
    return
  }

  if (!normalizedEmail) {
    fieldErrors.email = '请输入邮箱'
    emailInputRef.value?.focus()
    return
  }
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!emailRegex.test(normalizedEmail)) {
    fieldErrors.email = '邮箱格式不正确'
    emailInputRef.value?.focus()
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

  if (!validateInput()) {
    focusFirstFieldError()
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
  position: relative; /* 墨碑排印层的定位上下文 */
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
  /* 暖纸门面：素骨大底向老宣边缘轻压，一次绘成 */
  background-color: var(--md-background);
  background-image: radial-gradient(118% 92% at 50% 38%, transparent 52%, var(--md-surface-dim) 100%);
  color: var(--md-on-surface);
}

.register-scroll {
  width: min(96vw, 1180px);
  min-height: clamp(580px, 72vh, 720px);
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 470px);
  gap: clamp(20px, 3vw, 48px);
  color: var(--md-on-surface);
}

.register-panel {
  min-width: 0;
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-self: center;
  padding: clamp(28px, 3vw, 44px) clamp(24px, 3vw, 48px);
  /* 浮起稿纸：熟宣表单面无边框，Paper 2 柔影承担层级 */
  border: 0;
  border-radius: var(--md-radius-xs);
  background:
    repeating-linear-gradient(90deg, transparent 0 39px, var(--md-miaohong-line) 39px 40px),
    linear-gradient(var(--md-surface), var(--md-surface));
  box-shadow: var(--md-elevation-paper-2); /* 纸卡浮于页面之上 */
  color: var(--md-on-surface);
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
  color: var(--md-on-surface);
  font-family: var(--md-font-serif);
  font-size: 35px;
  font-weight: 600;
  line-height: 1.2;
  letter-spacing: 0.08em;
}

/* 题字旁落印：朱砂实底钤章，印章无影 */
.register-card__header h2 span {
  width: 22px;
  height: 22px;
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

.register-card__header p,
.register-closed-panel p {
  margin: 10px 0 0;
  color: var(--md-on-surface-variant);
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

.register-field-help,
.register-field-error {
  margin: 0;
  font-size: var(--md-label-small);
  line-height: 1.5;
}

.register-field-help {
  color: var(--md-on-surface-variant);
}

.register-field-error {
  color: var(--md-error-text);
}

.md-text-field-label {
  color: var(--md-on-surface);
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
  border: 1px solid var(--md-outline);
  border-radius: var(--md-radius-xs);
  background-color: var(--md-surface-container-low);
  color: var(--md-on-surface);
  font-family: var(--md-font-serif);
  font-size: 14.5px;
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
  right: 16px;
  width: 22px;
  height: 22px;
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
  border: 1px solid var(--md-outline);
  border-radius: var(--md-radius-xs);
  background: var(--md-surface-container-low);
  color: var(--md-on-surface);
  font-family: var(--md-font-serif);
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  cursor: pointer;
  box-shadow: none; /* 静无影 */
  transition:
    background-color 180ms cubic-bezier(0.22, 1, 0.36, 1),
    border-color 180ms cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 180ms cubic-bezier(0.22, 1, 0.36, 1);
}

.register-code-button:hover:not(:disabled) {
  border-color: var(--md-primary);
  background-color: var(--md-surface);
  box-shadow: var(--md-elevation-paper-1); /* hover 浮起 */
}

.register-code-button:disabled {
  opacity: 0.62;
  cursor: not-allowed;
}

.register-feedback {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--md-radius-xs);
  font-size: 13px;
  line-height: 1.5;
}

.register-feedback__stamp {
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

.register-feedback.is-error {
  border: 1px dashed color-mix(in srgb, var(--md-secondary) 52%, transparent);
  background: var(--md-error-container);
  color: var(--md-error-text);
}

.register-feedback.is-success {
  border: 1px dashed color-mix(in srgb, var(--md-success) 48%, transparent);
  background: var(--md-success-container);
  color: var(--md-success-text);
}

/* 落印钮：提交即钤章——配色/重力链/禁用态统一收编全局 .md-btn-primary（--md-btn-seal-*），
   此处仅保留整卷幅面与字号的版面覆写 */
.register-submit {
  width: 100%;
  min-height: 52px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  font-family: var(--md-font-serif);
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.14em;
  transition:
    background-color 180ms cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 180ms cubic-bezier(0.22, 1, 0.36, 1),
    transform 180ms cubic-bezier(0.22, 1, 0.36, 1);
}

.register-spinner {
  width: 19px;
  height: 19px;
  animation: md-spin 900ms linear infinite;
}

.register-divider {
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 14px;
  color: var(--md-outline);
}

.register-divider::before,
.register-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--md-outline-variant), transparent);
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
  color: var(--md-on-surface-variant);
  font-family: var(--md-font-serif);
  font-size: 14px;
}

.register-link__cta {
  min-height: 44px;
  padding: 0 10px;
  color: var(--md-secondary-readable);
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
  border-radius: var(--md-radius-xs);
}

@media (max-width: 1024px) {
  .register-scroll {
    grid-template-columns: minmax(0, 1fr) minmax(340px, 420px);
  }
}

@media (max-width: 833px) {
  .register-page {
    justify-content: flex-start;
    gap: 22px;
    padding: max(18px, env(safe-area-inset-top)) 10px max(18px, env(safe-area-inset-bottom));
  }

  .register-scroll {
    width: min(100%, 500px);
    min-height: auto;
    display: block;
  }

  .register-panel {
    margin-top: 8px;
    padding: 24px 24px;
  }

  .register-card__header {
    margin-bottom: 16px;
  }

  .register-card__header h2,
  .register-closed-panel h2 {
    font-size: 30px;
  }

  .register-form {
    gap: 12px;
  }

  .register-code-row {
    grid-template-columns: minmax(0, 1fr) auto;
  }

  .register-code-button {
    width: auto;
  }

  .register-link {
    flex-wrap: wrap;
  }
}

@media (max-width: 390px) {
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
