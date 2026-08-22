<!-- AIMETA P=蓝图编辑_蓝图编辑弹窗|R=蓝图编辑表单|NR=不含展示功能|E=component:BlueprintEditModal|X=internal|A=编辑弹窗|D=vue|S=dom|RD=./README.ai -->
<template>
  <transition
    enter-active-class="transition-opacity duration-200"
    leave-active-class="transition-opacity duration-200"
    enter-from-class="opacity-0"
    leave-to-class="opacity-0"
  >
    <div v-if="show" class="md-dialog-overlay" @click.self="handleClose">
      <transition
        enter-active-class="transition-[opacity,transform] duration-300"
        leave-active-class="transition-[opacity,transform] duration-200"
        enter-from-class="opacity-0 scale-95"
        leave-to-class="opacity-0 scale-95"
      >
        <div
          ref="dialogRef"
          class="md-dialog w-full max-w-2xl mx-4 max-h-[90vh] flex flex-col"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="dialogTitleId"
        >
          <!-- Material 3 Dialog Header -->
          <div class="md-dialog-header flex items-center justify-between">
            <h3 :id="dialogTitleId" class="md-dialog-title">编辑 {{ title }}</h3>
            <button 
              ref="closeButtonRef"
              data-dialog-initial-focus
              @click="handleClose" 
              class="md-icon-btn md-ripple"
              aria-label="关闭"
            >
              <svg class="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <!-- Dialog Content -->
          <div class="md-dialog-content flex-1 overflow-y-auto py-4">
            <ChapterOutlineEditor v-if="props.field === 'chapter_outline'" v-model="chapterOutlineContent" />
            <KeyLocationsEditor v-else-if="props.field === 'world_setting.key_locations'" v-model="keyLocationsContent" />
            <CharactersEditor v-else-if="props.field === 'characters'" v-model="charactersContent" />
            <RelationshipsEditor v-else-if="props.field === 'relationships'" v-model="relationshipsContent" />
            <FactionsEditor v-else-if="props.field === 'world_setting.factions'" v-model="factionsContent" />
            <div v-else class="md-text-field">
              <textarea
                v-model="textContent"
                class="md-textarea w-full blueprint-edit-modal__textarea"
                placeholder="请输入内容..."
                :aria-label="`编辑${title ? ` ${title}` : '内容'}`"
              ></textarea>
            </div>
          </div>

          <!-- Material 3 Dialog Actions -->
          <div class="md-dialog-actions blueprint-edit-modal__actions">
            <button 
              @click="handleClose" 
              class="md-btn md-btn-text md-ripple"
            >
              取消
            </button>
            <button 
              @click="saveChanges" 
              class="md-btn md-btn-filled md-ripple"
            >
              <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              保存
            </button>
          </div>
        </div>
      </transition>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { computed, ref, watch, toRef } from 'vue';
import ChapterOutlineEditor from './ChapterOutlineEditor.vue';
import KeyLocationsEditor from './KeyLocationsEditor.vue';
import CharactersEditor from './CharactersEditorEnhanced.vue';
import RelationshipsEditor from './RelationshipsEditor.vue';
import FactionsEditor from './FactionsEditor.vue';
import { useDialogA11y } from '@/composables/useDialogA11y'
import type { Blueprint, BlueprintPatch, ChapterOutline } from '@/api/novel'

type BlueprintEditContent = string | Record<string, unknown> | unknown[]
type BlueprintPatchValue = BlueprintPatch[keyof BlueprintPatch]

interface NamedDescription extends Record<string, unknown> {
  name: string
  description: string
}

interface Props {
  show?: boolean
  title?: string
  content?: BlueprintEditContent
  field: string
}

const props = withDefaults(defineProps<Props>(), {
  show: false,
  content: '',
})

const emit = defineEmits<{
  close: []
  save: [payload: { field: string; content: BlueprintPatchValue }]
}>()

const editableContent = ref<BlueprintEditContent>('')
const arrayContent = computed(() => Array.isArray(editableContent.value) ? editableContent.value : [])
const chapterOutlineContent = computed<ChapterOutline[]>({
  get: () => arrayContent.value as ChapterOutline[],
  set: (value) => { editableContent.value = value },
})
const keyLocationsContent = computed<NamedDescription[]>({
  get: () => arrayContent.value as NamedDescription[],
  set: (value) => { editableContent.value = value },
})
const charactersContent = computed<Blueprint['characters']>({
  get: () => arrayContent.value as Blueprint['characters'],
  set: (value) => { editableContent.value = value },
})
const relationshipsContent = computed<Blueprint['relationships']>({
  get: () => arrayContent.value as Blueprint['relationships'],
  set: (value) => { editableContent.value = value },
})
const factionsContent = computed<NamedDescription[]>({
  get: () => arrayContent.value as NamedDescription[],
  set: (value) => { editableContent.value = value },
})
const textContent = computed({
  get: () => typeof editableContent.value === 'string' ? editableContent.value : '',
  set: (value: string) => { editableContent.value = value },
})
const dialogRef = ref<HTMLElement | null>(null)
const closeButtonRef = ref<HTMLElement | null>(null)
const dialogInstanceId = `blueprint-edit-${Math.random().toString(36).slice(2, 10)}`
const dialogTitleId = `${dialogInstanceId}-title`

const handleClose = () => {
  emit('close')
}

watch(() => props.show, (isVisible) => {
  if (isVisible) {
    try {
      editableContent.value =
        typeof structuredClone === 'function'
          ? structuredClone(props.content || '')
          : JSON.parse(JSON.stringify(props.content || ''));
    } catch (e) {
      editableContent.value = props.content || '';
    }
  }
}, { immediate: true });

const saveChanges = () => {
  emit('save', { field: props.field, content: editableContent.value as BlueprintPatchValue });
};

useDialogA11y({
  active: toRef(props, 'show'),
  dialogRef,
  onClose: handleClose,
  initialFocusRef: closeButtonRef,
})
</script>

<style scoped>
.blueprint-edit-modal__textarea {
  min-height: 256px;
}

.blueprint-edit-modal__actions {
  border-top: 1px solid var(--md-outline-variant);
}
</style>
