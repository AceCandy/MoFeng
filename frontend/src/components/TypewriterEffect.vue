<!-- AIMETA P=打字机效果_文字动画组件|R=打字动画|NR=不含业务逻辑|E=component:TypewriterEffect|X=internal|A=动画组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <h1
    class="typewriter text-4xl md:text-5xl font-extrabold text-center text-[var(--md-on-surface)] tracking-wider"
    :style="{ '--char-count': fullText.length }"
  >
    {{ displayedText }}
  </h1>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps<{
  text: string
}>()

const fullText = props.text
const prefersReducedMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches
const displayedText = ref(prefersReducedMotion() ? fullText : '')
let index = 0
let timer: number | null = null

onMounted(() => {
  if (prefersReducedMotion()) {
    displayedText.value = fullText
    return
  }

  timer = window.setInterval(() => {
    if (index < fullText.length) {
      displayedText.value += fullText.charAt(index)
      index++
    } else {
      if (timer !== null) {
        window.clearInterval(timer)
        timer = null
      }
    }
  }, 150)
})

onBeforeUnmount(() => {
  if (timer !== null) {
    window.clearInterval(timer)
    timer = null
  }
})
</script>

<style scoped>
.typewriter {
  display: inline-block;
  overflow: hidden;
  white-space: nowrap;
  border-right: 0.1em solid var(--md-on-surface);
  animation: blink-caret 0.75s step-end infinite;
  width: 100%;
}

/* Cursor blinking effect */
@keyframes blink-caret {
  from,
  to {
    border-color: transparent;
  }
  50% {
    border-color: var(--md-on-surface);
  }
}

@media (prefers-reduced-motion: reduce) {
  .typewriter {
    animation: none;
    border-right-color: transparent;
  }
}
</style>
