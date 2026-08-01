<!-- AIMETA P=认证品牌区_墨风竖排印章引子|R=认证页品牌装饰|NR=不含表单逻辑|E=-|X=ui|A=认证品牌区|D=vue|S=dom|RD=./README.ai -->
<template>
  <aside class="auth-intro" :class="`auth-intro--${variant}`" aria-label="墨风">
    <span class="auth-intro__spine" aria-hidden="true">墨风</span>

    <div class="auth-intro__brand">
      <h1>墨风</h1>
      <span class="auth-intro__seal" aria-hidden="true">墨</span>
      <div class="auth-intro__meta">
        <p class="auth-intro__kind">AI<br />长篇创作</p>
        <p class="auth-intro__slogan">让每一次落笔，<br />都续写昨日的世界。</p>
      </div>
    </div>

    <p class="auth-intro__footmark" aria-hidden="true">
      <span class="auth-intro__stamp">墨</span>
      <span>一案 · 一砚 · 一方长卷</span>
    </p>
  </aside>
</template>

<script setup lang="ts">
// variant 仅切换移动端装饰底图：login 用立轴案头场景，register 用横幅山水。
withDefaults(defineProps<{ variant?: 'login' | 'register' }>(), { variant: 'register' })
</script>

<style scoped>
.auth-intro {
  min-width: 0;
  position: relative;
  overflow: hidden;
  border-radius: var(--md-radius-sm) 0 0 var(--md-radius-sm);
  background-color: var(--md-surface-container-high);
  background-image:
    linear-gradient(
      color-mix(in srgb, var(--md-surface-container-high) 14%, transparent),
      color-mix(in srgb, var(--md-surface-container-high) 14%, transparent)
    ),
    url('../../assets/mofeng_scroll_left_v2.webp');
  background-position: center;
  background-size: cover;
  color: var(--md-on-surface);
}

.auth-intro::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(
      circle at 62% 18%,
      color-mix(in srgb, var(--md-surface-container-low) 50%, transparent),
      transparent 25%
    ),
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--md-surface-container-low) 40%, transparent),
      color-mix(in srgb, var(--md-surface-container-high) 16%, transparent)
    );
}

.auth-intro__spine {
  position: absolute;
  top: clamp(40px, 12%, 72px);
  left: clamp(24px, 11%, 56px);
  z-index: 1;
  color: color-mix(in srgb, var(--md-primary-light) 56%, transparent);
  font-family: var(--md-font-serif);
  font-size: clamp(13px, 1.1vw, 15px);
  letter-spacing: 0.18em;
  writing-mode: vertical-rl;
}

/* 品牌簇：竖排书名 + 方印 + 竖排文案，弹性居中，不依赖底图对位 */
.auth-intro__brand {
  position: absolute;
  top: clamp(72px, 18%, 108px);
  left: 0;
  right: 0;
  z-index: 1;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  gap: clamp(18px, 2.2vw, 30px);
  padding: 0 clamp(16px, 4%, 40px);
}

.auth-intro__brand h1 {
  margin: 0;
  color: color-mix(in srgb, var(--md-on-surface) 96%, transparent);
  font-family: var(--md-font-serif);
  font-size: clamp(54px, 5.3vw, 86px);
  font-weight: 600;
  line-height: 1.02;
  letter-spacing: 0.06em;
  writing-mode: vertical-rl;
  text-shadow: 0 0 10px color-mix(in srgb, var(--md-surface-container-low) 88%, transparent);
}

.auth-intro__seal {
  align-self: center;
  width: 30px;
  height: 30px;
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border: 2px solid var(--md-secondary-dark);
  border-radius: var(--md-radius-none);
  background: color-mix(in srgb, var(--md-surface-container-high) 45%, transparent);
  color: var(--md-secondary-dark);
  font-family: var(--md-font-serif);
  font-size: 18px;
  font-weight: 600;
  line-height: 1;
}

.auth-intro__meta {
  display: flex;
  flex-direction: row-reverse;
  align-items: flex-start;
  gap: clamp(12px, 1.5vw, 22px);
}

.auth-intro__kind,
.auth-intro__slogan {
  margin: 0;
  font-family: var(--md-font-serif);
  writing-mode: vertical-rl;
  text-shadow: 0 0 10px color-mix(in srgb, var(--md-surface-container-low) 84%, transparent);
}

.auth-intro__kind {
  color: color-mix(in srgb, var(--md-primary-light) 86%, transparent);
  font-size: clamp(14px, 1.25vw, 17px);
  font-weight: 600;
  line-height: 1.7;
  letter-spacing: 0.18em;
}

.auth-intro__slogan {
  margin-top: clamp(28px, 3.5vw, 48px);
  color: color-mix(in srgb, var(--md-on-surface) 90%, transparent);
  font-size: clamp(16px, 1.45vw, 22px);
  font-weight: 600;
  line-height: 1.82;
  letter-spacing: 0.17em;
}

.auth-intro__footmark {
  position: absolute;
  left: clamp(24px, 11%, 56px);
  bottom: clamp(24px, 8%, 48px);
  z-index: 1;
  display: inline-flex;
  align-items: center;
  gap: clamp(8px, 1vw, 14px);
  margin: 0;
  color: color-mix(in srgb, var(--md-on-surface) 78%, transparent);
  font-family: var(--md-font-serif);
  font-size: clamp(12px, 1vw, 14px);
  letter-spacing: 0.08em;
}

.auth-intro__stamp {
  width: clamp(30px, 2.6vw, 38px);
  height: clamp(30px, 2.6vw, 38px);
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border: 2px solid var(--md-secondary-dark);
  border-radius: var(--md-radius-none);
  color: var(--md-secondary-dark);
  font-size: clamp(15px, 1.35vw, 21px);
  font-weight: 600;
  line-height: 1;
}

@media (max-width: 833px) {
  .auth-intro {
    min-height: 276px;
    border-radius: var(--md-radius-sm) var(--md-radius-sm) 0 0;
    background-position: 42% center;
  }

  /* 登录页移动端沿用立轴案头场景（register 维持横幅山水） */
  .auth-intro--login {
    background-image:
      linear-gradient(
        color-mix(in srgb, var(--md-surface-container-high) 14%, transparent),
        color-mix(in srgb, var(--md-surface-container-high) 14%, transparent)
      ),
      url('../../assets/mofeng_login_scene_v3.webp');
    background-position: center 18%;
  }

  .auth-intro__spine {
    top: 24px;
    left: 24px;
    font-size: 13px;
  }

  .auth-intro__brand {
    top: 48px;
    left: clamp(24px, 12vw, 56px);
    right: 24px;
    justify-content: flex-start;
    gap: 14px;
    padding: 0;
  }

  .auth-intro__brand h1 {
    font-size: 48px;
  }

  .auth-intro__seal {
    width: 26px;
    height: 26px;
    font-size: 15px;
  }

  /* 移动端竖排文案转横排，随品牌簇流式排列 */
  .auth-intro__meta {
    flex-direction: column;
    gap: 8px;
    margin-top: 4px;
  }

  .auth-intro__kind,
  .auth-intro__slogan {
    margin-top: 0;
    font-size: 13px;
    line-height: 1.6;
    letter-spacing: 0.1em;
    writing-mode: horizontal-tb;
  }

  .auth-intro__footmark {
    left: auto;
    right: 16px;
    bottom: 14px;
    gap: 8px;
    padding: 5px 8px;
    border-radius: var(--md-radius-xs);
    background: color-mix(in srgb, var(--md-surface-container-high) 55%, transparent);
    font-size: 11px;
    letter-spacing: 0.04em;
  }

  .auth-intro__stamp {
    width: 26px;
    height: 26px;
    font-size: 14px;
  }
}
</style>
