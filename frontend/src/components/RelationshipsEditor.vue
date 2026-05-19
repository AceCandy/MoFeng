<!-- AIMETA P=关系编辑器_角色关系编辑|R=关系CRUD|NR=不含角色编辑|E=component:RelationshipsEditor|X=internal|A=编辑器|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="space-y-4 max-h-96 overflow-y-auto p-1">
    <div v-for="(relationship, index) in localRelationships" :key="index" class="p-4 border border-[var(--md-outline-variant)] rounded-lg bg-[var(--md-surface-container-low)] relative">
      <button
        type="button"
        @click="removeRelationship(index)"
        class="absolute top-2 right-2 text-[var(--md-error)] hover:text-[var(--md-error)] transition-colors p-1"
        :aria-label="`删除关系 ${relationship.character_from || index + 1}`"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm4 0a1 1 0 012 0v6a1 1 0 11-2 0V8z" clip-rule="evenodd" />
        </svg>
      </button>
      
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-2">
        <div>
          <label :for="`relationship-from-${index}`" class="block text-sm font-medium text-[var(--md-on-surface-variant)] mb-1">从</label>
          <input :id="`relationship-from-${index}`" type="text" v-model="relationship.character_from" class="w-full p-1 border-b-2 border-[var(--md-outline-variant)] focus:border-[var(--md-primary)] outline-none transition bg-transparent" placeholder="例如：林远" />
        </div>
        <div>
          <label :for="`relationship-to-${index}`" class="block text-sm font-medium text-[var(--md-on-surface-variant)] mb-1">到</label>
          <input :id="`relationship-to-${index}`" type="text" v-model="relationship.character_to" class="w-full p-1 border-b-2 border-[var(--md-outline-variant)] focus:border-[var(--md-primary)] outline-none transition bg-transparent" placeholder="例如：苏晴" />
        </div>
      </div>
      <div>
        <label :for="`relationship-description-${index}`" class="block text-sm font-medium text-[var(--md-on-surface-variant)] mb-1">关系描述</label>
        <textarea
          :id="`relationship-description-${index}`"
          v-model="relationship.description"
          class="w-full h-20 p-2 mt-1 border border-[var(--md-outline-variant)] rounded-md focus:ring-1 focus:ring-[var(--md-primary-light)] focus:border-[var(--md-primary)] transition text-sm"
          placeholder="关于这段关系的详细描述..."
        ></textarea>
      </div>
    </div>
    <button type="button" @click="addRelationship" class="w-full mt-4 min-h-[44px] px-4 py-2 text-sm font-medium text-[var(--md-on-primary-container)] bg-[var(--md-primary-container)] border border-[var(--md-primary-container)] rounded-md hover:bg-[var(--md-tint-focus)] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[var(--md-primary-light)]">
      + 添加新关系
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';

interface Relationship {
  character_from: string;
  character_to: string;
  description: string;
}

const props = defineProps({
  modelValue: {
    type: Array as () => Relationship[],
    default: () => []
  }
});

const emit = defineEmits(['update:modelValue']);

const localRelationships = ref<Relationship[]>([]);
let syncing = false;

const cloneRelationships = <T>(value: T): T => {
  if (typeof structuredClone === 'function') {
    return structuredClone(value)
  }
  return JSON.parse(JSON.stringify(value))
}

watch(() => props.modelValue, (newVal) => {
  syncing = true;
  localRelationships.value = cloneRelationships(newVal || []);
  nextTick(() => {
    syncing = false;
  });
}, { immediate: true });

watch(localRelationships, (newVal) => {
  if (syncing) return;
  emit('update:modelValue', cloneRelationships(newVal));
}, { deep: true });

const addRelationship = () => {
  localRelationships.value.push({ 
    character_from: '', 
    character_to: '', 
    description: '' 
  });
};

const removeRelationship = (index: number) => {
  localRelationships.value.splice(index, 1);
};
</script>
