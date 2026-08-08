<!-- AIMETA P=灵感加载_加载动画组件|R=加载动画|NR=不含业务逻辑|E=component:InspirationLoading|X=internal|A=加载组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="inspiration-loading">
    <div class="inspiration-loading__icon">
      <!-- 国风毛笔意象（与全站 stroke 风格一致） -->
      <svg class="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" xmlns="http://www.w3.org/2000/svg">
        <path d="M18.5 2.5l3 3" />
        <path d="M16 5l2.5 2.5L9 17c-1.5 1.5-4 2.7-5.5 3 .3-1.5 1.5-4 3-5.5L16 5z" />
      </svg>
    </div>
    <h2 class="inspiration-loading__title">正在为你准备灵感空间...</h2>
    <div class="inspiration-loading__steps">
      <p>连接文思泉涌的AI...</p>
      <p>铺开创意的画卷...</p>
      <p>准备开启灵感之旅</p>
    </div>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.inspiration-loading {
  position: absolute;
  inset: 0;
  background-color: var(--md-surface);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: var(--md-spacing-8);
}

.inspiration-loading__icon {
  width: 5rem;
  height: 5rem;
  border-radius: var(--md-radius-xs); /* 微直角方函，弃正圆 */
  background-color: var(--md-surface); /* 熟宣函底（石青归朗读域，不挪用） */
  color: var(--md-on-surface);
  border: 1px solid var(--md-jiege); /* 界格发线 */
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: var(--md-spacing-6);
  animation: inspiration-loading-pulse 2s ease-in-out infinite;
}

.inspiration-loading__title {
  font-family: var(--md-font-display); /* 碑拓宋体 */
  font-size: var(--md-title-large);
  font-weight: 600;
  letter-spacing: 0.03em; /* 碑拓骨力：小标题字距 */
  color: var(--md-on-surface);
  margin-bottom: var(--md-spacing-4);
}

.inspiration-loading__steps {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-2);
  color: var(--md-on-surface-variant);
  font-family: var(--md-font-kai); /* 灵感絮语用楷体 */
  font-size: var(--md-body-medium);
  letter-spacing: 0.04em;
}

.inspiration-loading__steps p {
  animation: inspiration-loading-fade 1.8s ease-in-out infinite;
}

.inspiration-loading__steps p:nth-child(2) {
  animation-delay: 0.3s;
}

.inspiration-loading__steps p:nth-child(3) {
  animation-delay: 0.6s;
}

@keyframes inspiration-loading-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.7; transform: scale(0.95); }
}

@keyframes inspiration-loading-fade {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

@media (prefers-reduced-motion: reduce) {
  .inspiration-loading__icon,
  .inspiration-loading__steps p {
    animation: none;
  }
}
</style>
