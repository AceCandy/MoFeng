// AIMETA P=LLM_API客户端_模型配置接口|R=LLM配置CRUD|NR=不含UI逻辑|E=api:llm|X=internal|A=llmApi对象|D=axios|S=net|RD=./README.ai
import { useAuthStore } from '@/stores/auth';
import { API_BASE_URL, API_PREFIX } from './base';
import { requestJson } from './http';

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

export type ProviderType = 'openai_compatible' | 'anthropic' | 'ollama' | 'custom';

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

const llmRequest = <T>(
  path: string,
  options: RequestInit = {},
  fallbackErrorMessage = 'LLM 配置请求失败',
) =>
  requestJson<T>(`${LLM_BASE}${path}`, {
    ...options,
    headers: getHeaders(),
    timeoutMs: 20_000,
    fallbackErrorMessage,
  });

export const getLLMConfigBundle = async (): Promise<LLMConfigBundle> => {
  return llmRequest<LLMConfigBundle>('', { method: 'GET' }, '获取 LLM 配置失败');
};

export const getLLMConfig = async (): Promise<LLMConfig | null> => {
  const bundle = await getLLMConfigBundle();
  return bundle.legacy;
};

export const createOrUpdateLLMConfig = async (config: LLMConfigCreate): Promise<LLMConfig> => {
  return llmRequest<LLMConfig>('', {
    method: 'PUT',
    body: JSON.stringify(config),
  }, '保存 LLM 配置失败');
};

export const deleteLLMConfig = async (): Promise<void> => {
  await llmRequest<void>('', {
    method: 'DELETE',
  }, '删除 LLM 配置失败');
};

export interface ModelListRequest {
  llm_provider_url?: string;
  llm_provider_api_key?: string;
}

export const getAvailableModels = async (request: ModelListRequest): Promise<string[]> => {
  try {
    return await llmRequest<string[]>('/models', {
      method: 'POST',
      body: JSON.stringify(request),
    }, '获取可用模型失败');
  } catch {
    // 获取模型列表失败时返回空数组，不影响主流程
    return [];
  }
};

export const getProviderModels = async (providerId: number): Promise<string[]> => {
  return llmRequest<string[]>(`/providers/${providerId}/models`, {
    method: 'GET',
  }, '获取供应商模型列表失败');
};

export const createProvider = async (payload: ProviderCreate): Promise<UserModelProvider> => {
  return llmRequest<UserModelProvider>('/providers', {
    method: 'POST',
    body: JSON.stringify(payload),
  }, '创建模型供应商失败');
};

export const updateProvider = async (providerId: number, payload: ProviderUpdate): Promise<UserModelProvider> => {
  return llmRequest<UserModelProvider>(`/providers/${providerId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  }, '更新模型供应商失败');
};

export const deleteProvider = async (providerId: number): Promise<void> => {
  await llmRequest<void>(`/providers/${providerId}`, {
    method: 'DELETE',
  }, '删除模型供应商失败');
};

export const createUserModel = async (payload: UserAIModelCreate): Promise<UserAIModel> => {
  return llmRequest<UserAIModel>('/user-models', {
    method: 'POST',
    body: JSON.stringify(payload),
  }, '创建模型失败');
};

export const updateUserModel = async (modelId: number, payload: UserAIModelUpdate): Promise<UserAIModel> => {
  return llmRequest<UserAIModel>(`/user-models/${modelId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  }, '更新模型失败');
};

export const deleteUserModel = async (modelId: number): Promise<void> => {
  await llmRequest<void>(`/user-models/${modelId}`, {
    method: 'DELETE',
  }, '删除模型失败');
};

export const saveStageRoutes = async (payload: StageRoutesPayload): Promise<StageRoute[]> => {
  return llmRequest<StageRoute[]>('/stage-routes', {
    method: 'PUT',
    body: JSON.stringify(payload),
  }, '保存阶段路由失败');
};
