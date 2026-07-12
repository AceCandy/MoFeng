// AIMETA P=TTS_API客户端_单段语音合成|R=认证_二进制音频请求|NR=不含播放逻辑|E=api:tts|X=internal|A=ttsApi|D=fetch,pinia|S=net|RD=./README.ai
import { API_BASE_URL, API_PREFIX } from './base'
import { authRaw } from './client'


const TTS_BASE = `${API_BASE_URL}${API_PREFIX}/tts`


export const synthesizeSpeech = async (
  text: string,
  options?: { voice?: string; speed?: number },
  signal?: AbortSignal,
): Promise<Blob> => {
  const response = await authRaw(`${TTS_BASE}/speech`, {
    method: 'POST',
    body: JSON.stringify({ text, voice: options?.voice, speed: options?.speed }),
    signal,
    timeoutMs: 65_000,
    fallbackErrorMessage: '语音合成失败',
  })
  return response.blob()
}
