// AIMETA P=LLM_API客户端_模型配置接口|R=LLM配置CRUD|NR=不含UI逻辑|E=api:llm|X=internal|A=llmApi对象|D=axios|S=net|RD=./README.ai
import { useAuthStore } from '@/stores/auth';
import { API_BASE_URL, API_PREFIX } from './base';

const LLM_BASE = `${API_BASE_URL}${API_PREFIX}/llm-config`;

export interface LLMConfig {
  user_id: number;
  llm_provider_url: string | null;
  llm_provider_api_key: string | null;
  llm_provider_model: string | null;
  embedding_provider_url: string | null;
  embedding_provider_api_key: string | null;
  embedding_provider_model: string | null;
  embedding_provider_format: 'openai' | 'ollama' | null;
}

export interface LLMConfigCreate {
  llm_provider_url?: string | null;
  llm_provider_api_key?: string | null;
  llm_provider_model?: string | null;
  embedding_provider_url?: string | null;
  embedding_provider_api_key?: string | null;
  embedding_provider_model?: string | null;
  embedding_provider_format?: 'openai' | 'ollama' | null;
}

export type ProviderType = 'openai_compatible' | 'ollama' | 'custom';

export interface UserModelProvider {
  id: number;
  user_id: number;
  name: string;
  provider_type: ProviderType;
  base_url: string;
  api_key_preview: string | null;
  capabilities: Record<string, boolean>;
  is_enabled: boolean;
}

export interface ProviderCreate {
  name: string;
  provider_type: ProviderType;
  base_url: string;
  api_key?: string | null;
  capabilities: Record<string, boolean>;
  is_enabled: boolean;
}

export type ProviderUpdate = Partial<ProviderCreate>;

export interface UserAIModel {
  id: number;
  user_id: number;
  provider_id: number;
  display_name: string;
  model_name: string;
  capabilities: Record<string, boolean>;
  context_window: number | null;
  is_default_chat: boolean;
  is_default_embedding: boolean;
  is_enabled: boolean;
  sort_order: number;
}

export interface UserAIModelCreate {
  provider_id: number;
  display_name: string;
  model_name: string;
  capabilities: Record<string, boolean>;
  context_window?: number | null;
  is_default_chat: boolean;
  is_default_embedding: boolean;
  is_enabled: boolean;
  sort_order: number;
}

export type UserAIModelUpdate = Partial<UserAIModelCreate>;

export interface StageRoute {
  stage: string;
  model_id: number;
}

export interface StageRoutesPayload {
  routes: StageRoute[];
}

export interface LLMConfigBundle {
  legacy: LLMConfig | null;
  providers: UserModelProvider[];
  models: UserAIModel[];
  stage_routes: StageRoute[];
}

const getHeaders = () => {
  const authStore = useAuthStore();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (authStore.token) {
    headers.Authorization = `Bearer ${authStore.token}`;
  }
  return headers;
};

const readError = async (response: Response, fallback: string): Promise<Error> => {
  try {
    const payload = await response.json();
    const detail = typeof payload?.detail === 'string' ? payload.detail : fallback;
    return new Error(detail);
  } catch {
    return new Error(fallback);
  }
};

export const getLLMConfigBundle = async (): Promise<LLMConfigBundle> => {
  const response = await fetch(LLM_BASE, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (!response.ok) {
    throw await readError(response, 'Failed to fetch LLM config');
  }
  return response.json();
};

export const getLLMConfig = async (): Promise<LLMConfig | null> => {
  const bundle = await getLLMConfigBundle();
  return bundle.legacy;
};

export const createOrUpdateLLMConfig = async (config: LLMConfigCreate): Promise<LLMConfig> => {
  const response = await fetch(LLM_BASE, {
    method: 'PUT',
    headers: getHeaders(),
    body: JSON.stringify(config),
  });
  if (!response.ok) {
    throw await readError(response, 'Failed to save LLM config');
  }
  return response.json();
};

export const deleteLLMConfig = async (): Promise<void> => {
  const response = await fetch(LLM_BASE, {
    method: 'DELETE',
    headers: getHeaders(),
  });
  if (!response.ok) {
    throw await readError(response, 'Failed to delete LLM config');
  }
};

export interface ModelListRequest {
  llm_provider_url?: string;
  llm_provider_api_key?: string;
}

export const getAvailableModels = async (request: ModelListRequest): Promise<string[]> => {
  const response = await fetch(`${LLM_BASE}/models`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    // 获取模型列表失败时返回空数组，不影响主流程
    return [];
  }
  return response.json();
};

export const getProviderModels = async (providerId: number): Promise<string[]> => {
  const response = await fetch(`${LLM_BASE}/providers/${providerId}/models`, {
    method: 'GET',
    headers: getHeaders(),
  });
  if (!response.ok) {
    throw await readError(response, 'Failed to fetch provider models');
  }
  return response.json();
};

export const createProvider = async (payload: ProviderCreate): Promise<UserModelProvider> => {
  const response = await fetch(`${LLM_BASE}/providers`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await readError(response, 'Failed to create provider');
  }
  return response.json();
};

export const updateProvider = async (providerId: number, payload: ProviderUpdate): Promise<UserModelProvider> => {
  const response = await fetch(`${LLM_BASE}/providers/${providerId}`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await readError(response, 'Failed to update provider');
  }
  return response.json();
};

export const deleteProvider = async (providerId: number): Promise<void> => {
  const response = await fetch(`${LLM_BASE}/providers/${providerId}`, {
    method: 'DELETE',
    headers: getHeaders(),
  });
  if (!response.ok) {
    throw await readError(response, 'Failed to delete provider');
  }
};

export const createUserModel = async (payload: UserAIModelCreate): Promise<UserAIModel> => {
  const response = await fetch(`${LLM_BASE}/user-models`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await readError(response, 'Failed to create model');
  }
  return response.json();
};

export const updateUserModel = async (modelId: number, payload: UserAIModelUpdate): Promise<UserAIModel> => {
  const response = await fetch(`${LLM_BASE}/user-models/${modelId}`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await readError(response, 'Failed to update model');
  }
  return response.json();
};

export const deleteUserModel = async (modelId: number): Promise<void> => {
  const response = await fetch(`${LLM_BASE}/user-models/${modelId}`, {
    method: 'DELETE',
    headers: getHeaders(),
  });
  if (!response.ok) {
    throw await readError(response, 'Failed to delete model');
  }
};

export const saveStageRoutes = async (payload: StageRoutesPayload): Promise<StageRoute[]> => {
  const response = await fetch(`${LLM_BASE}/stage-routes`, {
    method: 'PUT',
    headers: getHeaders(),
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await readError(response, 'Failed to save stage routes');
  }
  return response.json();
};
