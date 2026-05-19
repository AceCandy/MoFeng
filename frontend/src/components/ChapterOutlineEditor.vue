<!-- AIMETA P=章节大纲编辑_大纲编辑器|R=大纲编辑|NR=不含章节内容|E=component:ChapterOutlineEditor|X=internal|A=编辑器|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="space-y-4 max-h-96 overflow-y-auto p-1">
    <div v-for="(chapter, index) in localOutline" :key="index" class="p-4 border border-[var(--md-outline-variant)] rounded-lg bg-[var(--md-surface-container-low)]">
      <div class="flex items-center mb-2">
        <span class="font-bold text-[var(--md-primary)] mr-2">第 {{ chapter.chapter_number }} 章</span>
        <input
          :id="`outline-title-${index}`"
          type="text"
          v-model="chapter.title"
          :aria-label="`第 ${chapter.chapter_number} 章标题`"
          class="flex-grow p-1 border-b-2 border-[var(--md-outline-variant)] focus:border-[var(--md-primary)] outline-none transition"
          placeholder="章节标题"
        />
        <button
          type="button"
          @click="removeChapter(index)"
          class="ml-2 text-[var(--md-error)] hover:text-[var(--md-error)] transition-colors p-1"
          :aria-label="`删除第 ${chapter.chapter_number} 章`"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm4 0a1 1 0 012 0v6a1 1 0 11-2 0V8z" clip-rule="evenodd" />
          </svg>
        </button>
      </div>
        <textarea
          :id="`outline-summary-${index}`"
          v-model="chapter.summary"
          :aria-label="`第 ${chapter.chapter_number} 章摘要`"
          class="w-full h-24 p-2 mt-2 border border-[var(--md-outline-variant)] rounded-md focus:ring-1 focus:ring-[var(--md-primary-light)] focus:border-[var(--md-primary)] transition text-sm"
          placeholder="章节摘要"
        ></textarea>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';
import type { ChapterOutline } from '@/api/novel';

const props = defineProps({
  modelValue: {
    type: Array as () => ChapterOutline[],
    default: () => []
  }
});

const emit = defineEmits(['update:modelValue']);

const localOutline = ref<ChapterOutline[]>([]);
let syncing = false;

const cloneOutline = <T>(value: T): T => {
  if (typeof structuredClone === 'function') {
    return structuredClone(value)
  }
  return JSON.parse(JSON.stringify(value))
}

watch(() => props.modelValue, (newVal) => {
  syncing = true;
  // Deep copy to prevent modifying the original prop
  localOutline.value = cloneOutline(newVal || []);
  nextTick(() => {
    syncing = false;
  });
}, { immediate: true });

// Watch for local changes and emit them upwards
watch(localOutline, (newVal) => {
  if (syncing) return;
  emit('update:modelValue', cloneOutline(newVal));
}, { deep: true });

const removeChapter = (index: number) => {
  localOutline.value.splice(index, 1);
  // Re-number all subsequent chapters to ensure they are sequential
  localOutline.value.forEach((chapter, i) => {
    chapter.chapter_number = i + 1;
  });
};
</script>
