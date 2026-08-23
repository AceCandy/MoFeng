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
  /* 引子透明立于暖纸门面，底色由认证页面承担 */
  border-radius: var(--md-radius-xs);
  color: var(--md-on-surface);
}

/* 灯下暖晕：品牌簇后方一团纸光，名章附近叠极淡朱光（大面积低透明度，渐隐到无） */
.auth-intro::before {
  content: '';
  position: absolute;
  inset: -6%;
  z-index: 0;
  background:
    radial-gradient(48% 42% at 47% 36%, var(--md-tint-warm) 0%, transparent 72%),
    radial-gradient(18% 15% at 58% 34%, var(--md-miaohong-wash) 0%, transparent 70%);
  pointer-events: none;
}

/* 灯下现格：书名号正后方一小块界格发线，radial mask 渐隐到无，绝不铺满；
   跟随品牌簇左锚（不再栏内居中），格光落在题字身后 */
.auth-intro::after {
  content: '';
  position: absolute;
  top: 6%;
  left: clamp(40px, 10%, 160px);
  z-index: 0;
  width: min(70%, 440px);
  height: 62%;
  background-image:
    repeating-linear-gradient(0deg, var(--md-outline-variant) 0 1px, transparent 1px 72px),
    repeating-linear-gradient(90deg, var(--md-outline-variant) 0 1px, transparent 1px 72px);
  -webkit-mask-image: radial-gradient(closest-side, #000 30%, transparent 78%);
  mask-image: radial-gradient(closest-side, #000 30%, transparent 78%);
  pointer-events: none;
}

.auth-intro__spine {
  position: absolute;
  top: clamp(40px, 12%, 72px);
  left: clamp(24px, 11%, 56px);
  z-index: 1;
  color: var(--md-on-surface-variant);
  font-family: var(--md-font-kai);
  font-size: clamp(13px, 1.1vw, 15px);
  letter-spacing: 0.18em;
  writing-mode: vertical-rl;
}

/* 品牌簇：竖排书名 + 方印 + 竖排题跋，左锚定位于墨碑「墨」字右下缘，
   与出血大字错位叠压成纵深（不再栏内居中悬浮） */
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

/* 名章落印：描红实底 + 深朱 1px 边，印章无影 */
.auth-intro__seal {
  align-self: center;
  width: 30px;
  height: 30px;
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--md-miaohong-strong);
  border-radius: var(--md-radius-xs);
  background-color: var(--md-miaohong);
  color: var(--md-btn-seal-text);
  font-family: var(--md-font-serif);
  font-size: 18px;
  font-weight: 600;
  line-height: 1;
  /* 静息斜印 -4°，与 auth-seal-drop 落印终态一致（reduce 下直落此态） */
  transform: rotate(-4deg);
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

/* 脚印小章：描红实底，印章无影 */
.auth-intro__stamp {
  width: clamp(30px, 2.6vw, 38px);
  height: clamp(30px, 2.6vw, 38px);
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--md-miaohong-strong);
  border-radius: var(--md-radius-xs);
  background-color: var(--md-miaohong);
  color: var(--md-btn-seal-text);
  font-size: clamp(15px, 1.35vw, 21px);
  font-weight: 600;
  line-height: 1;
  transform: rotate(3deg);
}

@media (max-width: 833px) {
  .auth-intro {
    min-height: 172px;
  }

  .auth-intro__spine {
    top: 12px;
    left: 24px;
    font-size: 13px;
  }

  .auth-intro__brand {
    top: 22px;
    left: clamp(24px, 12vw, 56px);
    right: 24px;
    justify-content: flex-start;
    gap: 14px;
    padding: 0;
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
    display: none;
  }

  .auth-intro__stamp {
    width: 26px;
    height: 26px;
    font-size: 14px;
  }
}
</style>
