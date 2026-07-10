// AIMETA P=TTS_API客户端_单段语音合成|R=认证_二进制音频请求|NR=不含播放逻辑|E=api:tts|X=internal|A=ttsApi|D=fetch,pinia|S=net|RD=./README.ai
import { useAuthStore } from '@/stores/auth'
import { API_BASE_URL, API_PREFIX } from './base'
import { requestRaw } from './http'


const TTS_BASE = `${API_BASE_URL}${API_PREFIX}/tts`


export const synthesizeSpeech = async (text: string, signal?: AbortSignal): Promise<Blob> => {
  const authStore = useAuthStore()
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (authStore.token) {
    headers.Authorization = `Bearer ${authStore.token}`
  }
  const response = await requestRaw(`${TTS_BASE}/speech`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ text }),
    signal,
    timeoutMs: 65_000,
    fallbackErrorMessage: '语音合成失败',
  })
  return response.blob()
}
