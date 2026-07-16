<template>
  <div
    :class="['model-routing__feedback', `is-${feedback.type}`]"
    :role="feedback.type === 'error' ? 'alert' : 'status'"
    aria-live="polite"
  >
    {{ feedback.message }}
  </div>
</template>

<script setup lang="ts">
interface FeedbackMessage {
  type: 'success' | 'error'
  message: string
}

defineProps<{ feedback: FeedbackMessage }>()
</script>

<style scoped>
.model-routing__feedback {
  border-radius: var(--md-radius-md);
  padding: var(--md-spacing-3);
  font-size: var(--md-body-medium);
}

.model-routing__feedback.is-success {
  background-color: var(--md-success-container);
  color: var(--md-on-success-container);
}

.model-routing__feedback.is-error {
  background-color: var(--md-error-container);
  color: var(--md-on-error-container);
}
</style>
