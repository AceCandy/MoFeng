// AIMETA P=小说客户端状态_灵感流程临时状态|R=conversation_state_reset|NR=不含API调用|E=store:novel|X=internal|A=useNovelStore|D=pinia|S=none|RD=./README.ai
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useNovelStore = defineStore('novel', () => {
  const currentConversationState = ref<Record<string, unknown>>({})
  const isAssistantPanelVisible = ref(true)

  function resetConversationState() {
    currentConversationState.value = {}
  }

  return {
    currentConversationState,
    isAssistantPanelVisible,
    resetConversationState,
  }
})
