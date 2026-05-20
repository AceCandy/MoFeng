<!-- AIMETA P=LLM设置_模型配置界面|R=LLM配置表单|NR=不含模型调用|E=component:LLMSettings|X=internal|A=设置组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <section
    class="md-card md-card-elevated llm-settings"
    :class="props.embedded ? `llm-settings--embedded` : ''"
  >
    <header v-if="!props.embedded" class="llm-settings__header">
      <h2 class="md-headline-small llm-settings__title">LLM 配置</h2>
      <p class="md-body-medium llm-settings__subtitle">
        必须配置用户级 API URL、API Key 与 Model，系统不再读取默认 LLM 配置。
      </p>
    </header>

    <div
      v-if="saveFeedback.message"
      :class="['llm-feedback', `is-${saveFeedback.type}`]"
      :role="saveFeedback.type === 'error' ? 'alert' : 'status'"
      aria-live="polite"
      aria-atomic="true"
    >
      {{ saveFeedback.message }}
    </div>

    <PersonalModelRouting v-if="props.showRouting" @saved="emit('saved')" />

    <form @submit.prevent="handleSave" class="llm-settings__form">
      <div class="llm-settings__section md-card md-card-outlined">
        <h3 class="md-title-medium llm-settings__section-title">主模型</h3>
        <div class="llm-settings__grid">
          <label class="md-text-field">
            <span class="md-text-field-label">API URL</span>
            <input
              id="url"
              v-model="config.llm_provider_url"
              type="text"
              class="md-text-field-input"
              placeholder="https://api.example.com/v1"
            />
          </label>

          <label class="md-text-field">
            <span class="md-text-field-label">API Key</span>
            <div class="llm-input-with-action">
              <input
                id="key"
                v-model="config.llm_provider_api_key"
                :type="showApiKey ? 'text' : 'password'"
                class="md-text-field-input"
                placeholder="请输入用户级 API Key"
              />
              <button type="button" class="llm-inline-action" @click="toggleApiKeyVisibility">
                {{ showApiKey ? '隐藏' : '显示' }}
              </button>
            </div>
          </label>
        </div>

        <div class="llm-model-row">
          <label class="md-text-field llm-model-row__input">
            <span class="md-text-field-label">Model</span>
            <input
              id="model"
              v-model="config.llm_provider_model"
              type="text"
              class="md-text-field-input"
              placeholder="请输入用户级模型名"
              @focus="handleModelFocus"
            />
          </label>

          <button
            type="button"
            class="md-btn md-btn-tonal md-ripple llm-model-row__action"
            :disabled="isLoadingModels"
            @click="manualTryLoadModels"
          >
            {{ isLoadingModels ? '加载中...' : '获取模型列表' }}
          </button>
        </div>
        <div v-if="showModelDropdown" class="llm-suggestion-panel">
          <div class="llm-suggestion-panel__header">
            <span class="md-label-medium">可用主模型（{{ availableModels.length }}）</span>
            <button type="button" class="llm-panel-action" @click="showModelDropdown = false">
              收起
            </button>
          </div>
          <div v-if="isLoadingModels" class="llm-suggestion-panel__empty">正在加载模型列表...</div>
          <div v-else-if="filteredModels.length === 0" class="llm-suggestion-panel__empty">
            无匹配模型
          </div>
          <div v-else class="llm-suggestion-panel__list">
            <button
              v-for="model in filteredModels"
              :key="model"
              type="button"
              class="llm-suggestion-chip"
              @click="selectModel(model)"
            >
              {{ model }}
            </button>
          </div>
        </div>

        <p v-if="lastLoadError" class="llm-hint is-error">{{ lastLoadError }}</p>
        <p v-else-if="lastLoadInfo" class="llm-hint is-info">{{ lastLoadInfo }}</p>
      </div>

      <div class="llm-settings__section md-card md-card-outlined">
        <h3 class="md-title-medium llm-settings__section-title">向量模型</h3>

        <div class="llm-format-switch">
          <span class="md-label-medium">请求格式</span>
          <div class="llm-format-switch__group" role="group" aria-label="向量模型请求格式">
            <button
              type="button"
              class="llm-format-switch__item"
              :class="{ active: config.embedding_provider_format === 'openai' }"
              :aria-pressed="config.embedding_provider_format === 'openai'"
              aria-label="切换为 OpenAI 兼容请求格式"
              @click="setEmbeddingProviderFormat('openai')"
            >
              OpenAI 兼容
            </button>
            <button
              type="button"
              class="llm-format-switch__item"
              :class="{ active: config.embedding_provider_format === 'ollama' }"
              :aria-pressed="config.embedding_provider_format === 'ollama'"
              aria-label="切换为 Ollama 请求格式"
              @click="setEmbeddingProviderFormat('ollama')"
            >
              Ollama
            </button>
          </div>
        </div>

        <p class="llm-hint">
          当前格式：<code class="llm-code">{{ config.embedding_provider_format }}</code>
          <span v-if="config.embedding_provider_format === 'openai'"
            >，接口走 <code class="llm-code">/v1/embeddings</code>。</span
          >
          <span v-else
            >，接口走 <code class="llm-code">/api/embed</code> 或
            <code class="llm-code">/api/embeddings</code>。</span
          >
        </p>

        <label class="llm-checkbox-row">
          <input v-model="useMainUrlForEmbedding" type="checkbox" />
          <span>复用主模型 API URL</span>
        </label>

        <label v-if="!useMainUrlForEmbedding" class="md-text-field">
          <span class="md-text-field-label">向量 API URL</span>
          <input
            id="embedding-url"
            v-model="config.embedding_provider_url"
            type="text"
            class="md-text-field-input"
            :placeholder="embeddingUrlPlaceholder"
          />
          <span class="llm-hint">{{ embeddingUrlHint }}</span>
        </label>

        <label class="llm-checkbox-row">
          <input v-model="useDedicatedEmbeddingApiKey" type="checkbox" />
          <span>使用独立向量 API Key（可选）</span>
        </label>

        <label v-if="useDedicatedEmbeddingApiKey" class="md-text-field">
          <span class="md-text-field-label">向量 API Key</span>
          <div class="llm-input-with-action">
            <input
              id="embedding-key"
              v-model="config.embedding_provider_api_key"
              :type="showEmbeddingApiKey ? 'text' : 'password'"
              class="md-text-field-input"
              placeholder="留空则复用主模型 API Key"
            />
            <button
              type="button"
              class="llm-inline-action"
              @click="toggleEmbeddingApiKeyVisibility"
            >
              {{ showEmbeddingApiKey ? '隐藏' : '显示' }}
            </button>
          </div>
        </label>

        <div class="llm-model-row">
          <label class="md-text-field llm-model-row__input">
            <span class="md-text-field-label">向量 Model</span>
            <input
              id="embedding-model"
              v-model="config.embedding_provider_model"
              type="text"
              class="md-text-field-input"
              placeholder="留空则使用系统默认向量模型"
              @focus="handleEmbeddingModelFocus"
            />
          </label>

          <button
            type="button"
            class="md-btn md-btn-tonal md-ripple llm-model-row__action"
            :disabled="isLoadingEmbeddingModels"
            @click="manualTryLoadEmbeddingModels"
          >
            {{ isLoadingEmbeddingModels ? '加载中...' : '获取向量模型' }}
          </button>
        </div>
        <div v-if="showEmbeddingModelDropdown" class="llm-suggestion-panel">
          <div class="llm-suggestion-panel__header">
            <span class="md-label-medium"
              >可用向量模型（{{ availableEmbeddingModels.length }}）</span
            >
            <button
              type="button"
              class="llm-panel-action"
              @click="showEmbeddingModelDropdown = false"
            >
              收起
            </button>
          </div>
          <p class="llm-suggestion-panel__note">
            接口返回的是全部模型，请手动选择支持向量/Embedding 的模型。
          </p>
          <div v-if="isLoadingEmbeddingModels" class="llm-suggestion-panel__empty">
            正在加载向量模型...
          </div>
          <div v-else-if="filteredEmbeddingModels.length === 0" class="llm-suggestion-panel__empty">
            无匹配模型
          </div>
          <div v-else class="llm-suggestion-panel__list">
            <button
              v-for="model in filteredEmbeddingModels"
              :key="model"
              type="button"
              class="llm-suggestion-chip"
              @click="selectEmbeddingModel(model)"
            >
              {{ model }}
            </button>
          </div>
        </div>

        <p v-if="lastEmbeddingLoadError" class="llm-hint is-error">{{ lastEmbeddingLoadError }}</p>
        <p v-else-if="lastEmbeddingLoadInfo" class="llm-hint is-info">
          {{ lastEmbeddingLoadInfo }}
        </p>
      </div>

      <footer class="llm-settings__actions">
        <button
          type="button"
          class="md-btn md-btn-outlined md-ripple llm-delete-btn"
          @click="handleDelete"
        >
          删除配置
        </button>
        <button type="submit" class="md-btn md-btn-filled md-ripple" :disabled="isSaving">
          {{ isSaving ? '保存中...' : '保存配置' }}
        </button>
      </footer>
    </form>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch, type Ref } from 'vue'
import type { LLMConfigCreate } from '@/api/llm'
import { globalAlert } from '@/composables/useAlert'
import PersonalModelRouting from './llm-settings/PersonalModelRouting.vue'
import {
  useAvailableModelsMutation,
  useDeleteLegacyLLMConfigMutation,
  useLegacyLLMConfigQuery,
  useSaveLegacyLLMConfigMutation,
} from '@/queries/llm'

type EmbeddingProviderFormat = 'openai' | 'ollama'

interface LLMSettingsForm {
  llm_provider_url: string
  llm_provider_api_key: string
  llm_provider_model: string
  embedding_provider_url: string
  embedding_provider_api_key: string
  embedding_provider_model: string
  embedding_provider_format: EmbeddingProviderFormat
}

const emit = defineEmits<{
  (e: 'saved'): void
}>()
const legacyConfigQuery = useLegacyLLMConfigQuery()
const saveLegacyLLMConfigMutation = useSaveLegacyLLMConfigMutation()
const deleteLegacyLLMConfigMutation = useDeleteLegacyLLMConfigMutation()
const availableModelsMutation = useAvailableModelsMutation()

const props = withDefaults(
  defineProps<{
    embedded?: boolean
    showRouting?: boolean
  }>(),
  {
    embedded: false,
    showRouting: true,
  },
)

const createEmptyConfig = (): LLMSettingsForm => ({
  llm_provider_url: '',
  llm_provider_api_key: '',
  llm_provider_model: '',
  embedding_provider_url: '',
  embedding_provider_api_key: '',
  embedding_provider_model: '',
  embedding_provider_format: 'openai',
})

const config = ref<LLMSettingsForm>(createEmptyConfig())
const useMainUrlForEmbedding = ref(true)
const useDedicatedEmbeddingApiKey = ref(false)

const showApiKey = ref(false)
const showEmbeddingApiKey = ref(false)
const availableModels = ref<string[]>([])
const isLoadingModels = ref(false)
const showModelDropdown = ref(false)
const lastLoadError = ref('')
const lastLoadInfo = ref('')
const hasTriedAutoLoadModels = ref(false)
const availableEmbeddingModels = ref<string[]>([])
const isLoadingEmbeddingModels = ref(false)
const showEmbeddingModelDropdown = ref(false)
const lastEmbeddingLoadError = ref('')
const lastEmbeddingLoadInfo = ref('')
const hasTriedAutoLoadEmbeddingModels = ref(false)
const isSaving = computed(() => saveLegacyLLMConfigMutation.isPending.value)
const saveFeedback = ref<{ type: 'success' | 'error'; message: string }>({
  type: 'success',
  message: '',
})

const inferEmbeddingProviderFormat = (rawUrl: string): EmbeddingProviderFormat => {
  const lower = rawUrl.toLowerCase()
  if (lower.includes(':11434') || lower.includes('ollama')) {
    return 'ollama'
  }
  return 'openai'
}

const normalizeEmbeddingUrlByFormat = (rawUrl: string, format: EmbeddingProviderFormat): string => {
  const trimmed = rawUrl.trim().replace(/\/+$/, '')
  if (!trimmed) {
    return ''
  }

  if (format !== 'ollama') {
    return trimmed
  }

  let normalized = trimmed
  const removableSuffixes = [/\/v1\/models$/i, /\/v1\/embeddings$/i, /\/v1$/i, /\/api$/i]
  let changed = true
  while (changed) {
    changed = false
    for (const suffix of removableSuffixes) {
      if (suffix.test(normalized)) {
        normalized = normalized.replace(suffix, '').replace(/\/+$/, '')
        changed = true
        break
      }
    }
  }
  return normalized
}

const embeddingUrlPlaceholder = computed(() =>
  config.value.embedding_provider_format === 'ollama'
    ? 'http://127.0.0.1:11434（Ollama 不要带 /v1）'
    : 'https://api.example.com/v1',
)

const embeddingUrlHint = computed(() =>
  config.value.embedding_provider_format === 'ollama'
    ? '使用 Ollama 向量模型时，地址应为 http://host:11434，不要追加 /v1 或 /api。'
    : '使用 OpenAI 兼容格式时，地址建议为 https://host/v1，系统将请求 /embeddings。',
)

// 根据输入过滤模型列表
const filteredModels = computed(() => {
  if (!config.value.llm_provider_model) {
    return availableModels.value
  }
  const searchTerm = config.value.llm_provider_model.toLowerCase()
  return availableModels.value.filter((model) => model.toLowerCase().includes(searchTerm))
})

const filteredEmbeddingModels = computed(() => {
  if (!config.value.embedding_provider_model) {
    return availableEmbeddingModels.value
  }
  const searchTerm = config.value.embedding_provider_model.toLowerCase()
  return availableEmbeddingModels.value.filter((model) => model.toLowerCase().includes(searchTerm))
})

watch(
  () => legacyConfigQuery.data.value,
  (existingConfig) => {
    if (!existingConfig) {
      return
    }

    const effectiveUrl = (
      existingConfig.embedding_provider_url ||
      existingConfig.llm_provider_url ||
      ''
    ).trim()
    const resolvedEmbeddingFormat: EmbeddingProviderFormat =
      existingConfig.embedding_provider_format || inferEmbeddingProviderFormat(effectiveUrl)

    config.value = {
      llm_provider_url: existingConfig.llm_provider_url || '',
      llm_provider_api_key: existingConfig.llm_provider_api_key || '',
      llm_provider_model: existingConfig.llm_provider_model || '',
      embedding_provider_url: existingConfig.embedding_provider_url || '',
      embedding_provider_api_key: existingConfig.embedding_provider_api_key || '',
      embedding_provider_model: existingConfig.embedding_provider_model || '',
      embedding_provider_format: resolvedEmbeddingFormat,
    }
    useMainUrlForEmbedding.value = !existingConfig.embedding_provider_url
    useDedicatedEmbeddingApiKey.value = !!existingConfig.embedding_provider_api_key
  },
  { immediate: true },
)

watch(
  () => legacyConfigQuery.error.value,
  (error) => {
    if (!error) return
    const message = error instanceof Error ? error.message : '未知错误'
    saveFeedback.value = { type: 'error', message: `读取配置失败：${message}` }
  },
)

const buildPayload = (): LLMConfigCreate => {
  const normalizedEmbeddingUrl = normalizeEmbeddingUrlByFormat(
    config.value.embedding_provider_url,
    config.value.embedding_provider_format,
  )

  return {
    llm_provider_url: config.value.llm_provider_url.trim() || null,
    llm_provider_api_key: config.value.llm_provider_api_key.trim() || null,
    llm_provider_model: config.value.llm_provider_model.trim() || null,
    embedding_provider_url: useMainUrlForEmbedding.value ? null : normalizedEmbeddingUrl || null,
    embedding_provider_api_key: useDedicatedEmbeddingApiKey.value
      ? config.value.embedding_provider_api_key.trim() || null
      : null,
    embedding_provider_model: config.value.embedding_provider_model.trim() || null,
    embedding_provider_format: config.value.embedding_provider_format,
  }
}

const handleSave = async () => {
  if (isSaving.value) {
    return
  }

  saveFeedback.value.message = ''
  try {
    await saveLegacyLLMConfigMutation.mutateAsync(buildPayload())
    saveFeedback.value = { type: 'success', message: '配置已保存。' }
    emit('saved')
  } catch (error) {
    const message = error instanceof Error ? error.message : '未知错误'
    saveFeedback.value = { type: 'error', message: `保存失败：${message}` }
  }
}

const handleDelete = async () => {
  const confirmed = await globalAlert.showConfirm(
    '确定要删除您的自定义LLM配置吗？删除后将恢复为默认配置。',
    '删除 LLM 配置',
  )
  if (!confirmed) {
    return
  }

  try {
    await deleteLegacyLLMConfigMutation.mutateAsync()
    config.value = createEmptyConfig()
    useMainUrlForEmbedding.value = true
    useDedicatedEmbeddingApiKey.value = false
    availableModels.value = []
    availableEmbeddingModels.value = []
    saveFeedback.value = { type: 'success', message: '配置已删除。' }
  } catch (error) {
    const message = error instanceof Error ? error.message : '未知错误'
    saveFeedback.value = { type: 'error', message: `删除失败：${message}` }
  }
}

const setEmbeddingProviderFormat = (format: EmbeddingProviderFormat) => {
  config.value.embedding_provider_format = format
}

const toggleApiKeyVisibility = () => {
  showApiKey.value = !showApiKey.value
}

const toggleEmbeddingApiKeyVisibility = () => {
  showEmbeddingApiKey.value = !showEmbeddingApiKey.value
}

const getEffectiveEmbeddingUrl = (): string =>
  normalizeEmbeddingUrlByFormat(
    useMainUrlForEmbedding.value
      ? config.value.llm_provider_url.trim()
      : config.value.embedding_provider_url.trim(),
    config.value.embedding_provider_format,
  )

const getEffectiveEmbeddingApiKey = (): string =>
  useDedicatedEmbeddingApiKey.value
    ? config.value.embedding_provider_api_key.trim()
    : config.value.llm_provider_api_key.trim()

const fetchModelsViaBackend = async (apiKey: string, apiUrl: string): Promise<string[]> => {
  const requestPayload: { llm_provider_url: string; llm_provider_api_key?: string } = {
    llm_provider_url: apiUrl,
  }
  if (apiKey) {
    requestPayload.llm_provider_api_key = apiKey
  }

  const models = await availableModelsMutation.mutateAsync(requestPayload)

  if (!Array.isArray(models)) {
    return []
  }

  return models
    .filter((model): model is string => typeof model === 'string' && model.length > 0)
    .sort((a, b) => a.localeCompare(b))
}

interface ModelListLoadContext {
  apiKey: string
  apiUrl: string
  silent: boolean
  isLoading: Ref<boolean>
  lastError: Ref<string>
  lastInfo: Ref<string>
  availableModelList: Ref<string[]>
  showDropdown: Ref<boolean>
  missingUrlMessage: string
  emptyListMessage: string
  successInfoMessage: string
  errorLabel: string
}

const loadModelList = async ({
  apiKey,
  apiUrl,
  silent,
  isLoading,
  lastError,
  lastInfo,
  availableModelList,
  showDropdown,
  missingUrlMessage,
  emptyListMessage,
  successInfoMessage,
  errorLabel,
}: ModelListLoadContext): Promise<void> => {
  if (isLoading.value) {
    return
  }

  if (!apiUrl) {
    if (!silent) {
      lastError.value = missingUrlMessage
    }
    return
  }

  isLoading.value = true
  lastError.value = ''
  lastInfo.value = ''
  try {
    const models = await fetchModelsViaBackend(apiKey, apiUrl)
    availableModelList.value = models
    if (models.length > 0) {
      lastInfo.value = successInfoMessage
      showDropdown.value = true
    } else if (!silent) {
      lastInfo.value = emptyListMessage
    }
  } catch (error) {
    console.error(`Failed to load ${errorLabel}:`, error)
    const errorMessage = error instanceof Error ? error.message : '未知错误'
    lastError.value = `${errorLabel}失败：${errorMessage}`
  } finally {
    isLoading.value = false
  }
}

const loadModels = async (options?: { silent?: boolean }) => {
  await loadModelList({
    apiKey: config.value.llm_provider_api_key?.trim() || '',
    apiUrl: config.value.llm_provider_url?.trim() || '',
    silent: options?.silent ?? false,
    isLoading: isLoadingModels,
    lastError: lastLoadError,
    lastInfo: lastLoadInfo,
    availableModelList: availableModels,
    showDropdown: showModelDropdown,
    missingUrlMessage: '请先填写 API URL',
    emptyListMessage: '未获取到模型列表，请检查 API URL 与认证配置（如需要）是否正确',
    successInfoMessage: '已通过后端代理获取模型列表',
    errorLabel: '获取模型列表',
  })
}

const manualTryLoadModels = async () => {
  showModelDropdown.value = true
  await loadModels()
}

const loadEmbeddingModels = async (options?: { silent?: boolean }) => {
  await loadModelList({
    apiKey: getEffectiveEmbeddingApiKey(),
    apiUrl: getEffectiveEmbeddingUrl(),
    silent: options?.silent ?? false,
    isLoading: isLoadingEmbeddingModels,
    lastError: lastEmbeddingLoadError,
    lastInfo: lastEmbeddingLoadInfo,
    availableModelList: availableEmbeddingModels,
    showDropdown: showEmbeddingModelDropdown,
    missingUrlMessage: useMainUrlForEmbedding.value
      ? '请先填写主模型 API URL'
      : '请先填写向量 API URL',
    emptyListMessage: '未获取到向量模型列表，请检查 API URL 与认证配置（如需要）是否正确',
    successInfoMessage: '已获取全部模型列表，请手动选择支持向量/Embedding 的模型',
    errorLabel: '获取向量模型列表',
  })
}

const manualTryLoadEmbeddingModels = async () => {
  showEmbeddingModelDropdown.value = true
  await loadEmbeddingModels()
}

interface AutoLoadOnFocusContext {
  showDropdown: Ref<boolean>
  availableModelList: Ref<string[]>
  isLoading: Ref<boolean>
  lastError: Ref<string>
  hasTriedAutoLoad: Ref<boolean>
  canAutoLoad: () => boolean
  loadSilently: () => Promise<void>
}

const autoLoadOnFocus = async ({
  showDropdown,
  availableModelList,
  isLoading,
  lastError,
  hasTriedAutoLoad,
  canAutoLoad,
  loadSilently,
}: AutoLoadOnFocusContext): Promise<void> => {
  showDropdown.value = true
  if (
    availableModelList.value.length === 0 &&
    canAutoLoad() &&
    !isLoading.value &&
    !lastError.value &&
    !hasTriedAutoLoad.value
  ) {
    hasTriedAutoLoad.value = true
    await loadSilently()
  }
}

const handleModelFocus = async () => {
  await autoLoadOnFocus({
    showDropdown: showModelDropdown,
    availableModelList: availableModels,
    isLoading: isLoadingModels,
    lastError: lastLoadError,
    hasTriedAutoLoad: hasTriedAutoLoadModels,
    canAutoLoad: () => Boolean(config.value.llm_provider_url),
    loadSilently: () => loadModels({ silent: true }),
  })
}

const handleEmbeddingModelFocus = async () => {
  await autoLoadOnFocus({
    showDropdown: showEmbeddingModelDropdown,
    availableModelList: availableEmbeddingModels,
    isLoading: isLoadingEmbeddingModels,
    lastError: lastEmbeddingLoadError,
    hasTriedAutoLoad: hasTriedAutoLoadEmbeddingModels,
    canAutoLoad: () => Boolean(getEffectiveEmbeddingUrl()),
    loadSilently: () => loadEmbeddingModels({ silent: true }),
  })
}

const selectModel = (model: string) => {
  config.value.llm_provider_model = model
  showModelDropdown.value = false
}

const selectEmbeddingModel = (model: string) => {
  config.value.embedding_provider_model = model
  showEmbeddingModelDropdown.value = false
}
</script>

<style scoped>
.llm-settings {
  border-radius: var(--md-radius-xl);
  padding: var(--md-spacing-6);
}

.llm-settings--embedded {
  box-shadow: none;
  padding: 0;
  border-radius: 0;
  background: transparent;
  overflow: visible;
}

.llm-settings__header {
  margin-bottom: var(--md-spacing-4);
}

.llm-settings__title {
  margin: 0;
  color: var(--md-on-surface);
}

.llm-settings__subtitle {
  margin: var(--md-spacing-1) 0 0;
  color: var(--md-on-surface-variant);
}

.llm-settings__form {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--md-spacing-4);
}

.llm-settings__section {
  border-radius: var(--md-radius-lg);
  padding: var(--md-spacing-4);
  overflow: visible;
}

.llm-settings__section-title {
  margin: 0 0 var(--md-spacing-4);
  color: var(--md-on-surface);
}

.llm-settings__grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--md-spacing-3);
}

.llm-model-row {
  margin-top: var(--md-spacing-2);
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-2);
}

.llm-model-row__input {
  min-width: 0;
}

.llm-model-row__action {
  width: 100%;
}

.llm-input-with-action {
  position: relative;
}

.llm-input-with-action .md-text-field-input {
  padding-right: 72px;
}

.llm-inline-action {
  position: absolute;
  top: 50%;
  right: 10px;
  transform: translateY(-50%);
  border: none;
  background: transparent;
  color: var(--md-primary);
  font-size: var(--md-label-medium);
  font-weight: 600;
  cursor: pointer;
}

.llm-inline-action:hover {
  color: var(--md-primary-dark);
}

.llm-panel-action {
  display: inline-flex;
  align-items: center;
  border: none;
  background: transparent;
  color: var(--md-primary);
  font-size: var(--md-label-medium);
  font-weight: 600;
  cursor: pointer;
  padding: 0;
  min-height: 44px;
}

.llm-panel-action:hover {
  color: var(--md-primary-dark);
  text-decoration: underline;
}

.llm-suggestion-panel {
  margin-top: var(--md-spacing-2);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-md);
  background-color: var(--md-surface-container-low);
  padding: var(--md-spacing-3);
}

.llm-suggestion-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--md-spacing-2);
}

.llm-suggestion-panel__header .md-label-medium {
  color: var(--md-on-surface-variant);
}

.llm-suggestion-panel__empty {
  font-size: var(--md-body-small);
  color: var(--md-on-surface-variant);
  padding: var(--md-spacing-2) 0;
}

.llm-suggestion-panel__note {
  margin: 0 0 var(--md-spacing-2);
  font-size: var(--md-body-small);
  color: var(--md-on-surface-variant);
}

.llm-suggestion-panel__list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--md-spacing-2);
  max-height: 220px;
  overflow: auto;
}

.llm-suggestion-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-full);
  background-color: var(--md-surface);
  color: var(--md-on-surface);
  min-height: 44px;
  padding: 0 14px;
  font-size: var(--md-body-small);
  cursor: pointer;
  transition:
    background-color var(--md-duration-short) var(--md-easing-standard),
    border-color var(--md-duration-short) var(--md-easing-standard),
    color var(--md-duration-short) var(--md-easing-standard);
}

.llm-suggestion-chip:hover {
  border-color: var(--md-primary);
  background-color: var(--md-primary-container);
  color: var(--md-on-primary-container);
}

.llm-format-switch {
  display: flex;
  flex-wrap: wrap;
  gap: var(--md-spacing-2);
  align-items: center;
}

.llm-format-switch .md-label-medium {
  color: var(--md-on-surface-variant);
}

.llm-format-switch__group {
  display: inline-flex;
  border: 1px solid var(--md-outline);
  border-radius: var(--md-radius-full);
  overflow: hidden;
}

.llm-format-switch__item {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  min-height: 44px;
  padding: 10px 16px;
  color: var(--md-on-surface-variant);
  cursor: pointer;
  transition:
    background-color var(--md-duration-short) var(--md-easing-standard),
    color var(--md-duration-short) var(--md-easing-standard);
}

.llm-format-switch__item.active {
  background-color: var(--md-primary);
  color: var(--md-on-primary);
}

.llm-format-switch__item:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: -2px;
}

.llm-format-switch__item:not(.active):hover {
  background-color: color-mix(in srgb, var(--md-primary-container) 62%, var(--md-surface));
}

.llm-checkbox-row {
  display: flex;
  align-items: center;
  gap: var(--md-spacing-2);
  color: var(--md-on-surface);
  font-size: var(--md-body-medium);
}

.llm-checkbox-row input {
  width: 16px;
  height: 16px;
}

.llm-hint {
  margin: var(--md-spacing-1) 0 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.llm-hint.is-error {
  color: var(--md-error);
}

.llm-hint.is-info {
  color: var(--md-primary);
}

.llm-code {
  font-family: var(--md-font-mono);
  font-size: 0.8rem;
}

.llm-settings__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--md-spacing-2);
  grid-column: 1 / -1;
}

.llm-delete-btn {
  color: var(--md-error);
  border-color: color-mix(in srgb, var(--md-error) 40%, var(--md-outline));
}

.llm-delete-btn:hover {
  background-color: var(--md-error-container);
  color: var(--md-on-error-container);
}

.llm-feedback {
  margin-bottom: var(--md-spacing-3);
  border-radius: var(--md-radius-md);
  padding: var(--md-spacing-3);
  font-size: var(--md-body-medium);
}

.llm-feedback.is-success {
  background-color: var(--md-success-container);
  color: var(--md-on-success-container);
}

.llm-feedback.is-error {
  background-color: var(--md-error-container);
  color: var(--md-on-error-container);
}

@media (min-width: 834px) {
  .llm-model-row {
    flex-direction: row;
    align-items: flex-end;
  }

  .llm-model-row__action {
    width: auto;
    white-space: nowrap;
  }
}

@media (min-width: 1280px) {
  .llm-settings__form {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    align-items: start;
  }
}
</style>
