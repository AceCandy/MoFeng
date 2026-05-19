<!-- AIMETA P=关键地点编辑_地点信息编辑|R=地点CRUD|NR=不含角色编辑|E=component:KeyLocationsEditor|X=internal|A=编辑器|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="space-y-4 max-h-96 overflow-y-auto p-1">
    <div v-for="(location, index) in localLocations" :key="index" class="p-4 border border-[var(--md-outline-variant)] rounded-lg bg-[var(--md-surface-container-low)] relative">
      <button
        type="button"
        @click="removeLocation(index)"
        class="absolute top-2 right-2 text-[var(--md-error)] hover:text-[var(--md-error)] transition-colors p-1"
        :aria-label="`删除地点 ${location.name || index + 1}`"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm4 0a1 1 0 012 0v6a1 1 0 11-2 0V8z" clip-rule="evenodd" />
        </svg>
      </button>
      <div class="mb-2">
        <label :for="`location-name-${index}`" class="block text-sm font-medium text-[var(--md-on-surface-variant)] mb-1">地点名称</label>
        <input
          :id="`location-name-${index}`"
          type="text"
          v-model="location.name"
          class="w-full p-1 border-b-2 border-[var(--md-outline-variant)] focus:border-[var(--md-primary)] outline-none transition bg-transparent"
          placeholder="例如：林远生前的公寓"
        />
      </div>
      <div>
        <label :for="`location-description-${index}`" class="block text-sm font-medium text-[var(--md-on-surface-variant)] mb-1">描述</label>
        <textarea
          :id="`location-description-${index}`"
          v-model="location.description"
          class="w-full h-20 p-2 mt-1 border border-[var(--md-outline-variant)] rounded-md focus:ring-1 focus:ring-[var(--md-primary-light)] focus:border-[var(--md-primary)] transition text-sm"
          placeholder="关于这个地点的详细描述..."
        ></textarea>
      </div>
    </div>
    <button type="button" @click="addLocation" class="w-full mt-4 px-4 py-2 text-sm font-medium text-[var(--md-primary)] bg-[var(--md-primary-container)] border border-[var(--md-primary-container)] rounded-md hover:bg-[var(--md-primary-dark)] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[var(--md-primary-light)]">
      + 添加新地点
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';

interface KeyLocation {
  name: string;
  description: string;
}

const props = defineProps({
  modelValue: {
    type: Array as () => KeyLocation[],
    default: () => []
  }
});

const emit = defineEmits(['update:modelValue']);

const localLocations = ref<KeyLocation[]>([]);
let syncing = false;

const cloneLocations = <T>(value: T): T => {
  if (typeof structuredClone === 'function') {
    return structuredClone(value)
  }
  return JSON.parse(JSON.stringify(value))
}

watch(() => props.modelValue, (newVal) => {
  syncing = true;
  localLocations.value = cloneLocations(newVal || []);
  nextTick(() => {
    syncing = false;
  });
}, { immediate: true });

watch(localLocations, (newVal) => {
  if (syncing) return;
  emit('update:modelValue', cloneLocations(newVal));
}, { deep: true });

const addLocation = () => {
  localLocations.value.push({ name: '', description: '' });
};

const removeLocation = (index: number) => {
  localLocations.value.splice(index, 1);
};
</script>
