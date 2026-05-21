<!-- AIMETA P=势力编辑器_势力信息编辑|R=势力CRUD|NR=不含角色编辑|E=component:FactionsEditor|X=internal|A=编辑器|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="space-y-4 max-h-96 overflow-y-auto p-1">
    <div v-for="(faction, index) in localFactions" :key="index" class="p-4 border border-[var(--md-outline-variant)] rounded-lg bg-[var(--md-surface-container-low)] relative">
      <button
        type="button"
        @click="removeFaction(index)"
        class="blueprint-editor__delete-button absolute top-2 right-2 text-[var(--md-error)] hover:text-[var(--md-error)] transition-colors"
        :aria-label="`删除阵营 ${faction.name || index + 1}`"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm4 0a1 1 0 012 0v6a1 1 0 11-2 0V8z" clip-rule="evenodd" />
        </svg>
      </button>
      <div class="mb-2">
        <label :for="`faction-name-${index}`" class="block text-sm font-medium text-[var(--md-on-surface-variant)] mb-1">阵营名称</label>
        <input
          :id="`faction-name-${index}`"
          type="text"
          v-model="faction.name"
          class="w-full p-1 border-b-2 border-[var(--md-outline-variant)] focus:border-[var(--md-primary)] outline-none transition bg-transparent"
          placeholder="例如：幽灵侦探林远"
        />
      </div>
      <div>
        <label :for="`faction-description-${index}`" class="block text-sm font-medium text-[var(--md-on-surface-variant)] mb-1">描述</label>
        <textarea
          :id="`faction-description-${index}`"
          v-model="faction.description"
          class="w-full h-20 p-2 mt-1 border border-[var(--md-outline-variant)] rounded-md focus:ring-1 focus:ring-[var(--md-primary-light)] focus:border-[var(--md-primary)] transition text-sm"
          placeholder="关于这个阵营的详细描述..."
        ></textarea>
      </div>
    </div>
    <button type="button" @click="addFaction" class="w-full mt-4 min-h-[44px] px-4 py-2 text-sm font-medium text-[var(--md-on-primary-container)] bg-[var(--md-primary-container)] border border-[var(--md-primary-container)] rounded-md hover:bg-[var(--md-tint-focus)] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[var(--md-primary-light)]">
      + 添加新阵营
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';

interface Faction {
  name: string;
  description: string;
}

const props = defineProps({
  modelValue: {
    type: Array as () => Faction[],
    default: () => []
  }
});

const emit = defineEmits(['update:modelValue']);

const localFactions = ref<Faction[]>([]);
let syncing = false;

const cloneFactions = <T>(value: T): T => {
  if (typeof structuredClone === 'function') {
    return structuredClone(value)
  }
  return JSON.parse(JSON.stringify(value))
}

watch(() => props.modelValue, (newVal) => {
  syncing = true;
  localFactions.value = cloneFactions(newVal || []);
  nextTick(() => {
    syncing = false;
  });
}, { immediate: true });

watch(localFactions, (newVal) => {
  if (syncing) return;
  emit('update:modelValue', cloneFactions(newVal));
}, { deep: true });

const addFaction = () => {
  localFactions.value.push({ name: '', description: '' });
};

const removeFaction = (index: number) => {
  localFactions.value.splice(index, 1);
};
</script>
