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
// variant 保留以兼容 login/register 调用方；描红引子视觉已统一，不再按变体切换底图。
withDefaults(defineProps<{ variant?: 'login' | 'register' }>(), { variant: 'register' })
</script>

<style scoped>
.auth-intro {
  min-width: 0;
  position: relative;
  overflow: hidden;
  /* 描红引子：淡朱 wash 底 + 界格行线（AI 侧描红稿），明暗场随令牌自适应 */
  border-radius: var(--md-radius-xs);
  background-color: var(--md-miaohong-wash);
  background-image:
    repeating-linear-gradient(0deg, var(--md-miaohong-line) 0 1px, transparent 1px 56px),
    repeating-linear-gradient(90deg, var(--md-miaohong-line) 0 1px, transparent 1px 56px);
  color: var(--md-on-surface);
}

.auth-intro__spine {
  position: absolute;
  top: clamp(40px, 12%, 72px);
  left: clamp(24px, 11%, 56px);
  z-index: 1;
  color: var(--md-miaohong-strong);
  font-family: var(--md-font-kai);
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
  color: var(--md-on-surface);
  font-family: var(--md-font-serif);
  font-size: clamp(54px, 5.3vw, 86px);
  font-weight: 600;
  line-height: 1.02;
  letter-spacing: 0.06em;
  writing-mode: vertical-rl;
}

/* 名章落印：朱砂实底 + 深朱 1px 边，印章无影 */
.auth-intro__seal {
  align-self: center;
  width: 30px;
  height: 30px;
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--md-secondary-dark);
  border-radius: var(--md-radius-xs);
  background-color: var(--md-secondary);
  color: var(--md-on-secondary);
  font-family: var(--md-font-serif);
  font-size: 18px;
  font-weight: 600;
  line-height: 1;
  transform: rotate(-3deg);
}

.auth-intro__meta {
  display: flex;
  flex-direction: row-reverse;
  align-items: flex-start;
  gap: clamp(12px, 1.5vw, 22px);
}

/* 引子文案：kind 作 AI 之声（真楷描红），slogan 作作家许诺（真楷落墨） */
.auth-intro__kind,
.auth-intro__slogan {
  margin: 0;
  font-family: var(--md-font-kai);
  writing-mode: vertical-rl;
}

.auth-intro__kind {
  color: var(--md-miaohong-strong);
  font-size: clamp(14px, 1.25vw, 17px);
  font-weight: 600;
  line-height: 1.7;
  letter-spacing: 0.18em;
}

.auth-intro__slogan {
  margin-top: clamp(28px, 3.5vw, 48px);
  color: var(--md-on-surface);
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
  color: var(--md-on-surface-variant);
  font-family: var(--md-font-serif);
  font-size: clamp(12px, 1vw, 14px);
  letter-spacing: 0.08em;
}

/* 脚印小章：朱砂实底，印章无影 */
.auth-intro__stamp {
  width: clamp(30px, 2.6vw, 38px);
  height: clamp(30px, 2.6vw, 38px);
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--md-secondary-dark);
  border-radius: var(--md-radius-xs);
  background-color: var(--md-secondary);
  color: var(--md-on-secondary);
  font-size: clamp(15px, 1.35vw, 21px);
  font-weight: 600;
  line-height: 1;
  transform: rotate(3deg);
}

@media (max-width: 833px) {
  .auth-intro {
    min-height: 276px;
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
    border: 1px solid var(--md-miaohong-line);
    border-radius: var(--md-radius-xs);
    background: var(--md-surface);
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
