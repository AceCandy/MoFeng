<!-- AIMETA P=认证品牌区_墨风创作引子|R=认证页品牌信息|NR=不含表单逻辑|E=-|X=ui|A=认证品牌区|D=vue|S=dom|RD=./README.ai -->
<template>
  <aside class="auth-intro" :class="`auth-intro--${variant}`" aria-label="墨风">
    <div class="auth-intro__brand">
      <h1>墨风</h1>
      <div class="auth-intro__meta">
        <p class="auth-intro__kind">AI<br />长篇创作</p>
        <p class="auth-intro__slogan">让每一次落笔，<br />都续写昨日的世界。</p>
      </div>
    </div>

    <p class="auth-intro__footmark" aria-hidden="true">
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
  border-radius: var(--md-radius-xs);
  color: var(--md-on-surface);
}

.auth-intro__brand {
  position: absolute;
  top: clamp(84px, 19%, 148px);
  left: clamp(88px, 16%, 220px);
  z-index: 1;
  display: flex;
  align-items: flex-start;
  justify-content: flex-start;
  gap: clamp(18px, 2.2vw, 30px);
}

.auth-intro__brand h1 {
  margin: 0;
  color: var(--md-on-surface);
  font-family: var(--md-font-serif);
  font-size: clamp(56px, 8vw, 88px); /* 展示级书名号（≤6rem 纪律） */
  font-weight: 600;
  line-height: 1.02;
  letter-spacing: -0.02em;
  writing-mode: vertical-rl;
}

.auth-intro__meta {
  display: flex;
  flex-direction: row-reverse;
  align-items: flex-start;
  gap: clamp(12px, 1.5vw, 22px);
}

/* 引子文案：kind 作 AI 之声（真楷描红），slogan 作作家许诺（松烟辅文） */
.auth-intro__kind,
.auth-intro__slogan {
  margin: 0;
  font-family: var(--md-font-kai);
  writing-mode: vertical-rl;
}

.auth-intro__kind {
  color: var(--md-miaohong);
  font-size: clamp(14px, 1.25vw, 17px);
  font-weight: 600;
  line-height: 1.7;
  letter-spacing: 0.18em;
}

.auth-intro__slogan {
  margin-top: clamp(28px, 3.5vw, 48px);
  color: var(--md-on-surface-variant);
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

@media (max-width: 833px) {
  .auth-intro {
    min-height: 172px;
  }

  .auth-intro__brand {
    top: 22px;
    left: clamp(24px, 12vw, 56px);
    right: 24px;
    justify-content: flex-start;
    gap: 14px;
    padding: 0;
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
    display: none;
  }
}
</style>
