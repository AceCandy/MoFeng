<!-- AIMETA P=灵感加载_加载动画组件|R=加载动画|NR=不含业务逻辑|E=component:InspirationLoading|X=internal|A=加载组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="inspiration-loading">
    <div class="inspiration-loading__icon">
      <svg class="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707m12.728 0l-.707-.707"></path>
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
  border-radius: var(--md-radius-full);
  background-color: var(--md-primary-container);
  color: var(--md-on-primary-container);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: var(--md-spacing-6);
  animation: inspiration-loading-pulse 2s ease-in-out infinite;
}

.inspiration-loading__title {
  font-size: var(--md-title-large);
  font-weight: 600;
  color: var(--md-on-surface);
  margin-bottom: var(--md-spacing-4);
}

.inspiration-loading__steps {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-2);
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-medium);
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
