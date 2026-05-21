<!-- AIMETA P=打字机效果_文字动画组件|R=打字动画|NR=不含业务逻辑|E=component:TypewriterEffect|X=internal|A=动画组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <h1
    class="typewriter text-4xl md:text-5xl font-extrabold text-center text-[var(--md-on-surface)] tracking-wider"
  >
    {{ displayedText }}
  </h1>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  text: string
}>()

const displayedText = computed(() => props.text)
</script>

<style scoped>
.typewriter {
  display: inline-block;
  overflow: hidden;
  white-space: nowrap;
  width: 100%;
}
</style>
