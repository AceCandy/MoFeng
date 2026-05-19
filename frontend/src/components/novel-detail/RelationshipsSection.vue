<!-- AIMETA P=关系区_角色关系展示|R=关系图谱|NR=不含编辑功能|E=component:RelationshipsSection|X=ui|A=关系组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-2xl font-bold text-[var(--md-on-surface)]">人物关系</h2>
        <p class="text-sm text-[var(--md-on-surface-variant)]">角色之间的纽带与冲突</p>
      </div>
      <button
        v-if="editable"
        type="button"
        class="text-[var(--md-on-surface-variant)] hover:text-[var(--md-primary)] transition-colors"
        @click="emitEdit('relationships', '人物关系', data?.relationships)">
        <svg class="h-6 w-6" viewBox="0 0 20 20" fill="currentColor">
          <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
          <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
        </svg>
      </button>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <div
        v-for="(relation, index) in relationships"
        :key="index"
        class="bg-[var(--md-surface)] rounded-2xl border border-[var(--md-outline-variant)] shadow-sm p-6">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-3">
            <div class="w-10 h-10 rounded-full bg-[var(--md-primary-container)] flex items-center justify-center text-[var(--md-primary)] font-semibold">
              {{ relation.character_from?.slice(0, 1) || '角' }}
            </div>
            <span class="font-semibold text-[var(--md-on-surface)] truncate">{{ relation.character_from || '未知角色' }}</span>
          </div>
          <svg class="text-[var(--md-on-surface-variant)]" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>
          <div class="flex items-center space-x-3">
            <span class="font-semibold text-[var(--md-on-surface)] truncate">{{ relation.character_to || '未知角色' }}</span>
            <div class="w-10 h-10 rounded-full bg-[var(--md-success-container)] flex items-center justify-center text-[var(--md-success)] font-semibold">
              {{ relation.character_to?.slice(0, 1) || '角' }}
            </div>
          </div>
        </div>
        <div class="mt-4 bg-[var(--md-surface-container-low)] border border-[var(--md-outline-variant)] rounded-xl p-4 text-center">
          <p class="text-sm font-semibold text-[var(--md-on-surface)]">{{ relation.relationship_type || '关系' }}</p>
          <p class="text-xs text-[var(--md-on-surface-variant)] leading-5 mt-1">{{ relation.description || '暂无描述' }}</p>
        </div>
      </div>
      <div v-if="!relationships.length" class="bg-[var(--md-surface)] rounded-2xl border border-dashed border-[var(--md-outline-variant)] p-10 text-center text-[var(--md-on-surface-variant)]">
        暂无人际关系信息
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface RelationshipItem {
  character_from?: string
  character_to?: string
  relationship_type?: string
  description?: string
}

const props = defineProps<{
  data: { relationships?: RelationshipItem[] } | null
  editable?: boolean
}>()

const emit = defineEmits<{
  (e: 'edit', payload: { field: string; title: string; value: any }): void
}>()

const relationships = computed(() => props.data?.relationships || [])

const emitEdit = (field: string, title: string, value: any) => {
  if (!props.editable) return
  emit('edit', { field, title, value })
}
</script>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'RelationshipsSection'
})
</script>
