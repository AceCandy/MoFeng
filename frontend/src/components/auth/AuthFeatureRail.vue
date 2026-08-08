<!-- AIMETA P=认证流程栏_墨风创作五步|R=认证页底部特性栏|NR=不含表单逻辑|E=-|X=ui|A=认证流程栏|D=vue|S=dom|RD=./README.ai -->
<template>
  <ul class="auth-feature-rail" aria-label="墨风创作流程">
    <li v-for="item in featureRail" :key="item.title">
      <span class="auth-feature-rail__icon" aria-hidden="true" v-html="item.icon"></span>
      <span class="auth-feature-rail__copy">
        <strong>{{ item.title }}</strong>
        <small>{{ item.desc }}</small>
      </span>
    </li>
  </ul>
</template>

<script setup lang="ts">
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
</script>

<style scoped>
.auth-feature-rail {
  width: min(88vw, 1040px);
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: clamp(12px, 2.4vw, 38px);
  padding: 0;
  margin: 0;
  list-style: none;
  color: color-mix(in srgb, var(--md-on-surface) 76%, transparent);
}

.auth-feature-rail li {
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 12px;
}

.auth-feature-rail__icon {
  width: 34px;
  height: 34px;
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  color: var(--md-miaohong); /* AI 流程描红 */
}

.auth-feature-rail__icon :deep(svg) {
  width: 27px;
  height: 27px;
}

.auth-feature-rail__copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.auth-feature-rail strong {
  font-family: var(--md-font-serif);
  font-size: var(--md-body-large);
  font-weight: 600;
  letter-spacing: 0.06em;
}

.auth-feature-rail small {
  color: color-mix(in srgb, var(--md-on-surface-variant) 78%, transparent);
  font-size: var(--md-body-small);
  white-space: nowrap;
}

@media (max-width: 833px) {
  .auth-feature-rail {
    display: none;
  }
}
</style>
