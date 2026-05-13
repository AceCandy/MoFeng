<template>
  <section class="model-routing">
    <div class="model-routing__topbar">
      <div class="model-routing__section-copy">
        <p class="md-label-medium model-routing__eyebrow">{{ sectionEyebrow }}</p>
        <h3 class="md-title-medium">{{ sectionHeading }}</h3>
        <p class="model-routing__hint">{{ sectionDescription }}</p>
      </div>
      <div class="model-routing__topbar-actions">
        <button
          type="button"
          class="md-btn md-btn-outlined md-ripple"
          :disabled="isLoading"
          @click="loadBundle"
        >
          {{ isLoading ? '刷新中...' : '刷新' }}
        </button>
        <button
          v-if="activeSection === 'routes'"
          type="button"
          class="md-btn md-btn-tonal md-ripple"
          :disabled="isSavingRoutes"
          @click="saveRoutes"
        >
          {{ isSavingRoutes ? '保存中...' : '保存阶段路由' }}
        </button>
        <button
          v-else
          type="button"
          class="md-btn md-btn-filled md-ripple"
          @click="beginCreateProvider"
        >
          新增供应商
        </button>
      </div>
    </div>

    <div
      v-if="feedback.message"
      :class="['model-routing__feedback', `is-${feedback.type}`]"
      :role="feedback.type === 'error' ? 'alert' : 'status'"
      aria-live="polite"
    >
      {{ feedback.message }}
    </div>

    <div class="model-routing__readiness" aria-label="模型配置状态">
      <div
        v-for="card in sectionReadinessCards"
        :key="card.label"
        :class="['model-routing__readiness-item', `is-${card.tone}`]"
        :title="card.description"
      >
        <span class="model-routing__readiness-label">{{ card.label }}</span>
        <strong>{{ card.value }}</strong>
      </div>
    </div>

    <template v-if="activeSection === 'routes'">
      <section class="model-routing__stages">
        <div v-if="enabledChatModels.length === 0" class="model-routing__empty-state">
          <p class="md-title-small">还不能配置阶段路由</p>
          <p class="model-routing__empty">请先在文本生成里启用至少一个模型，并指定主模型。</p>
          <button
            type="button"
            class="md-btn md-btn-tonal md-ripple"
            @click="emit('navigate', 'llm')"
          >
            去配置文本生成
          </button>
        </div>

        <div v-else class="model-routing__stage-groups">
          <div
            v-for="group in chatStageGroups"
            :key="group.title"
            class="model-routing__stage-group"
          >
            <h4 class="md-title-small">{{ group.title }}</h4>
            <div class="model-routing__stage-list">
              <label
                v-for="stage in group.stages"
                :key="stage.key"
                class="model-routing__stage-row"
              >
                <span>
                  <strong>{{ stage.label }}</strong>
                  <small>{{ stage.description }}</small>
                </span>
                <select v-model="routeSelections[stage.key]" class="md-text-field-input">
                  <option value="">使用主模型</option>
                  <option
                    v-for="model in enabledChatModels"
                    :key="model.id"
                    :value="String(model.id)"
                  >
                    {{ model.display_name }} · {{ providerName(model.provider_id) }}
                  </option>
                </select>
              </label>
            </div>
          </div>
        </div>
      </section>
    </template>

    <template v-else>
      <section v-if="providerFormMode" class="model-routing__panel model-routing__provider-form">
        <div class="model-routing__form-head">
          <h3 class="md-title-medium">
            {{ providerFormMode === 'create' ? '新增供应商' : '编辑供应商' }}
          </h3>
          <button type="button" class="model-routing__link" @click="cancelProviderForm">
            取消
          </button>
        </div>

        <div class="model-routing__form">
          <label class="md-text-field">
            <span class="md-text-field-label">名称</span>
            <input
              v-model="providerForm.name"
              class="md-text-field-input"
              type="text"
              placeholder="如 OpenAI / Anthropic / DeepSeek / 本地 Ollama"
            />
          </label>

          <label class="md-text-field">
            <span class="md-text-field-label">类型</span>
            <select v-model="providerForm.provider_type" class="md-text-field-input">
              <option value="openai_compatible">OpenAI 兼容</option>
              <option value="anthropic">Anthropic</option>
              <option value="ollama">Ollama</option>
              <option value="custom">自定义</option>
            </select>
          </label>

          <label class="md-text-field">
            <span class="md-text-field-label">API URL</span>
            <input
              v-model="providerForm.base_url"
              class="md-text-field-input"
              type="text"
              placeholder="https://api.example.com/v1"
            />
          </label>

          <label class="md-text-field">
            <span class="md-text-field-label">API Key</span>
            <input
              v-model="providerForm.api_key"
              class="md-text-field-input"
              type="password"
              :placeholder="
                editingProviderId ? '留空则保留已保存 Key' : '请输入 API Key，Ollama 可留空'
              "
            />
          </label>

          <label class="model-routing__check">
            <input v-model="providerForm.is_enabled" type="checkbox" />
            <span>启用供应商</span>
          </label>

          <button
            type="button"
            class="md-btn md-btn-filled md-ripple"
            :disabled="isSavingProvider"
            @click="saveProviderForm"
          >
            {{ isSavingProvider ? '保存中...' : '保存供应商' }}
          </button>
        </div>
      </section>

      <section
        v-if="activeSection === 'llm'"
        class="model-routing__panel model-routing__primary-panel"
      >
        <div class="model-routing__primary-copy">
          <h3 class="md-title-medium">主模型</h3>
          <p class="model-routing__hint">未设置阶段路由时，所有文本生成任务会使用这里的模型。</p>
        </div>
        <label class="md-text-field model-routing__primary-field">
          <span class="md-text-field-label">主模型</span>
          <select
            class="md-text-field-input"
            :value="primaryChatModel ? String(primaryChatModel.id) : ''"
            :disabled="enabledChatModels.length === 0"
            @change="setPrimaryChatModelById"
          >
            <option value="">请先勾选一个文本生成模型</option>
            <option v-for="model in enabledChatModels" :key="model.id" :value="String(model.id)">
              {{ model.display_name }} · {{ providerName(model.provider_id) }}
            </option>
          </select>
        </label>
      </section>

      <div class="model-routing__provider-grid">
        <article
          v-for="provider in activeProviders"
          :key="provider.id"
          class="model-routing__provider-card"
        >
          <header class="model-routing__provider-head">
            <div class="model-routing__provider-main">
              <div class="model-routing__provider-title-row">
                <h3 class="md-title-medium">{{ provider.name }}</h3>
                <span
                  :class="[
                    'model-routing__provider-state',
                    provider.is_enabled ? 'is-enabled' : 'is-disabled',
                  ]"
                >
                  {{ provider.is_enabled ? '已启用' : '已停用' }}
                </span>
              </div>
              <div class="model-routing__provider-meta">
                <span class="model-routing__provider-type">
                  {{ providerTypeLabel(provider.provider_type) }}
                </span>
                <span>{{ providerKeyLabel(provider) }}</span>
              </div>
              <p class="model-routing__provider-url">{{ provider.base_url }}</p>
            </div>
            <div class="model-routing__provider-card-actions">
              <button
                type="button"
                :class="['model-routing__toggle', provider.is_enabled ? 'is-on' : 'is-off']"
                :disabled="isSavingProvider"
                @click="toggleProviderEnabled(provider)"
              >
                {{ provider.is_enabled ? '停用' : '启用' }}
              </button>
              <button
                type="button"
                class="model-routing__provider-delete"
                :disabled="isSavingProvider"
                @click="deleteProviderFromCard(provider)"
              >
                删除供应商
              </button>
            </div>
          </header>

          <div class="model-routing__provider-actions">
            <button
              type="button"
              class="md-btn md-btn-text md-ripple"
              @click="beginEditProvider(provider)"
            >
              编辑供应商
            </button>
            <button
              type="button"
              class="md-btn md-btn-tonal md-ripple"
              :disabled="!provider.is_enabled || providerFetchState(provider.id).isLoading"
              @click="openProviderModelPicker(provider)"
            >
              {{ providerFetchState(provider.id).isLoading ? '拉取中...' : '拉取模型' }}
            </button>
          </div>

          <div
            v-if="isModelPickerOpen(provider.id)"
            class="model-routing__model-picker"
            role="dialog"
            :aria-label="activeSection === 'llm' ? '选择文本生成模型' : '选择记忆检索模型'"
            @click.stop
          >
            <div class="model-routing__picker-head">
              <div>
                <strong>{{
                  activeSection === 'llm' ? '选择文本生成模型' : '选择记忆检索模型'
                }}</strong>
                <p class="model-routing__hint">
                  {{
                    activeSection === 'llm' ? '勾选后加入可用模型池。' : '单选后作为当前检索模型。'
                  }}
                </p>
              </div>
              <button type="button" class="model-routing__link" @click="closeModelPicker">
                关闭
              </button>
            </div>

            <label class="md-text-field model-routing__picker-search">
              <span class="md-text-field-label">搜索模型</span>
              <input
                v-model="modelPickerQuery"
                class="md-text-field-input"
                type="search"
                placeholder="输入模型名过滤"
              />
            </label>

            <p v-if="providerFetchState(provider.id).isLoading" class="model-routing__empty">
              正在拉取模型...
            </p>
            <p
              v-else-if="filteredModelNamesForProvider(provider.id).length === 0"
              class="model-routing__empty"
            >
              没有可选模型。
            </p>
            <div v-else class="model-routing__picker-list">
              <label
                v-for="modelName in filteredModelNamesForProvider(provider.id)"
                :key="`${provider.id}-${modelName}`"
                :class="[
                  'model-routing__picker-row',
                  {
                    'is-selected': isModelSelectedForActiveSection(provider.id, modelName),
                  },
                ]"
              >
                <span class="model-routing__picker-model-name">
                  {{ modelName }}
                  <small v-if="activeModelStateLabel(provider.id, modelName)">
                    {{ activeModelStateLabel(provider.id, modelName) }}
                  </small>
                </span>
                <input
                  v-if="activeSection === 'llm'"
                  type="checkbox"
                  :checked="Boolean(chatModelForName(provider.id, modelName)?.is_enabled)"
                  :disabled="!provider.is_enabled"
                  aria-label="启用文本生成模型"
                  @change="toggleChatModel(provider, modelName, $event)"
                />
                <input
                  v-else
                  name="embedding-model"
                  type="radio"
                  :checked="
                    Boolean(
                      embeddingModelForName(provider.id, modelName)?.is_enabled &&
                      embeddingModelForName(provider.id, modelName)?.is_default_embedding,
                    )
                  "
                  :disabled="!provider.is_enabled"
                  aria-label="选择向量模型"
                  @change="selectEmbeddingModel(provider, modelName)"
                />
              </label>
            </div>
          </div>

          <p v-if="!provider.is_enabled" class="model-routing__hint">
            启用供应商后才能使用里面的模型。
          </p>
          <p v-if="providerFetchState(provider.id).error" class="model-routing__hint is-error">
            {{ providerFetchState(provider.id).error }}
          </p>

          <div class="model-routing__selected-models">
            <p class="md-label-medium model-routing__model-list-title">
              {{ activeSection === 'llm' ? '已选文本生成模型' : '已选检索模型' }}
            </p>
            <p
              v-if="selectedModelChipsForProvider(provider.id).length === 0"
              class="model-routing__empty"
            >
              点击“拉取模型”后勾选模型。
            </p>
            <div v-else class="model-routing__selected-chip-list">
              <span
                v-for="chip in selectedModelChipsForProvider(provider.id)"
                :key="chip.id"
                class="model-routing__selected-chip"
              >
                <span>{{ chip.display_name || chip.model_name }}</span>
                <small v-if="activeSection === 'llm' && chip.is_default_chat"> 主模型 </small>
                <small v-else-if="activeSection === 'embedding' && chip.is_default_embedding">
                  当前使用
                </small>
                <button
                  type="button"
                  class="model-routing__delete-btn"
                  :aria-label="`删除模型 ${chip.display_name || chip.model_name}`"
                  :title="`删除模型 ${chip.display_name || chip.model_name}`"
                  @click="deleteModelForActiveSection(provider, chip.model_name)"
                >
                  删除
                </button>
              </span>
            </div>
          </div>
        </article>
      </div>

      <div v-if="activeProviders.length === 0" class="model-routing__empty-state">
        <p class="md-title-small">尚未配置供应商</p>
        <p class="model-routing__empty">
          先新增一个{{
            activeSection === 'llm' ? '文本生成' : '记忆检索'
          }}供应商，再拉取并启用模型。
        </p>
        <button type="button" class="md-btn md-btn-filled md-ripple" @click="beginCreateProvider">
          新增供应商
        </button>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  createProvider,
  createUserModel,
  deleteProvider,
  deleteUserModel,
  getLLMConfigBundle,
  getProviderModels,
  saveStageRoutes,
  updateProvider,
  updateUserModel,
  type ProviderCreate,
  type ProviderType,
  type UserAIModel,
  type UserAIModelCreate,
  type UserModelProvider,
} from '@/api/llm'
import { globalAlert } from '@/composables/useAlert'

type Capability = 'chat' | 'embedding'
type RoutingSection = 'llm' | 'embedding' | 'routes'
type ProviderFormMode = 'create' | 'edit' | null
type ReadinessTone = 'success' | 'warning' | 'neutral'

interface StageDefinition {
  key: string
  label: string
  capability: Capability
  description: string
}

interface StageGroup {
  title: string
  stages: StageDefinition[]
}

interface ProviderForm {
  name: string
  provider_type: ProviderType
  base_url: string
  api_key: string
  is_enabled: boolean
}

interface ProviderFetchState {
  isLoading: boolean
  modelsByCapability: Record<Capability, string[]>
  error: string
}

interface ReadinessCard {
  label: string
  value: string
  description: string
  tone: ReadinessTone
}

const emit = defineEmits<{
  (event: 'saved'): void
  (event: 'navigate', section: RoutingSection): void
}>()

const props = defineProps<{ activeSection?: RoutingSection }>()

const activeSection = computed<RoutingSection>(() => props.activeSection || 'llm')

const stageGroups: StageGroup[] = [
  {
    title: '导入与灵感',
    stages: [
      {
        key: 'import_analysis',
        label: '导入分析',
        capability: 'chat',
        description: '导入小说角色筛选与结构分析',
      },
      {
        key: 'concept_conversation',
        label: '灵感对话',
        capability: 'chat',
        description: '灵感模式多轮概念对话',
      },
      {
        key: 'world_blueprint',
        label: '完整蓝图',
        capability: 'chat',
        description: '由灵感历史生成整本书蓝图',
      },
    ],
  },
  {
    title: '规划',
    stages: [
      {
        key: 'chapter_outline',
        label: '章节大纲',
        capability: 'chat',
        description: '续写章节大纲',
      },
      {
        key: 'chapter_blueprint',
        label: '章节蓝图',
        capability: 'chat',
        description: '单章或批量章节蓝图',
      },
      {
        key: 'chapter_mission',
        label: '导演脚本',
        capability: 'chat',
        description: '章节写作前的执行脚本',
      },
    ],
  },
  {
    title: '写作',
    stages: [
      {
        key: 'chapter_preview',
        label: '章节预览',
        capability: 'chat',
        description: '预览、评估与扩写',
      },
      {
        key: 'chapter_writing',
        label: '正文生成',
        capability: 'chat',
        description: '章节正文主生成',
      },
      {
        key: 'chapter_rewrite',
        label: '护栏重写',
        capability: 'chat',
        description: '一致性和护栏自动修复',
      },
      {
        key: 'chapter_compression',
        label: '字数压缩',
        capability: 'chat',
        description: '超长章节压缩',
      },
      {
        key: 'chapter_enrichment',
        label: '章节润色',
        capability: 'chat',
        description: '对话、场景和章节增强',
      },
    ],
  },
  {
    title: '复盘与优化',
    stages: [
      {
        key: 'version_review',
        label: '版本评审',
        capability: 'chat',
        description: '多版本评审和单版本评价',
      },
      {
        key: 'chapter_optimization',
        label: '章节优化',
        capability: 'chat',
        description: '节奏、心理、环境、对白优化',
      },
      {
        key: 'deep_review',
        label: '深度审稿',
        capability: 'chat',
        description: '六维复盘、读者模拟、自我批评',
      },
      {
        key: 'emotion_analysis',
        label: '情绪曲线',
        capability: 'chat',
        description: '章节情绪曲线分析',
      },
      {
        key: 'consistency_check',
        label: '一致性检查',
        capability: 'chat',
        description: '只诊断问题，不改正文',
      },
    ],
  },
  {
    title: '记忆与 RAG',
    stages: [
      {
        key: 'summary_memory',
        label: '摘要记忆',
        capability: 'chat',
        description: '章节摘要、全局摘要、角色状态',
      },
      {
        key: 'rag_query',
        label: '检索规划',
        capability: 'chat',
        description: '检索查询生成和上下文过滤',
      },
      {
        key: 'foreshadowing',
        label: '伏笔处理',
        capability: 'chat',
        description: '伏笔候选、状态判断和提醒',
      },
    ],
  },
]

const providers = ref<UserModelProvider[]>([])
const models = ref<UserAIModel[]>([])
const routeSelections = reactive<Record<string, string>>({})
const providerFetchStates = reactive<Record<number, ProviderFetchState>>({})
const isLoading = ref(false)
const isSavingProvider = ref(false)
const isSavingRoutes = ref(false)
const editingProviderId = ref<number | null>(null)
const providerFormMode = ref<ProviderFormMode>(null)
const activeModelPickerProviderId = ref<number | null>(null)
const modelPickerQuery = ref('')
const feedback = ref<{ type: 'success' | 'error'; message: string }>({
  type: 'success',
  message: '',
})

const emptyProviderForm = (): ProviderForm => ({
  name: '',
  provider_type: 'openai_compatible',
  base_url: '',
  api_key: '',
  is_enabled: true,
})

const providerForm = reactive<ProviderForm>(emptyProviderForm())
const providerTypeLabels: Record<ProviderType, string> = {
  openai_compatible: 'OpenAI 兼容',
  anthropic: 'Anthropic',
  ollama: 'Ollama',
  custom: '自定义',
}

const chatStageGroups = computed(() => stageGroups)
const allStageKeys = computed(() =>
  chatStageGroups.value.flatMap((group) => group.stages.map((stage) => stage.key)),
)
const enabledChatModels = computed(() =>
  models.value.filter((model) => model.is_enabled && Boolean(model.capabilities.chat)),
)
const primaryChatModel = computed(() =>
  enabledChatModels.value.find((model) => model.is_default_chat),
)
const enabledEmbeddingModels = computed(() =>
  models.value.filter((model) => model.is_enabled && Boolean(model.capabilities.embedding)),
)
const defaultEmbeddingModel = computed(() =>
  enabledEmbeddingModels.value.find((model) => model.is_default_embedding),
)
const configuredRouteCount = computed(
  () => Object.values(routeSelections).filter((modelId) => Boolean(modelId)).length,
)
const chatModelsByProvider = computed(() => groupModelsByProvider('chat'))
const embeddingModelsByProvider = computed(() => groupModelsByProvider('embedding'))
const activeProviders = computed(() =>
  providers.value.filter((provider) => providerCapabilities(provider)[activeModelCapability()]),
)
const sectionEyebrow = computed(() =>
  activeSection.value === 'routes'
    ? '阶段覆盖'
    : activeSection.value === 'embedding'
      ? '记忆检索'
      : '文本生成',
)
const sectionHeading = computed(() => {
  if (activeSection.value === 'routes') {
    return '按创作阶段选择默认模型'
  }
  return activeSection.value === 'embedding' ? '配置向量供应商和检索模型' : '配置供应商和主模型'
})
const sectionDescription = computed(() => {
  if (activeSection.value === 'routes') {
    return '只有特殊阶段需要覆盖；未设置的阶段会继续使用文本生成主模型。'
  }
  if (activeSection.value === 'embedding') {
    return '记忆检索只使用一个当前向量模型，避免索引和查询维度不一致。'
  }
  return '先保存供应商，再拉取模型并指定主模型，写作流程才能稳定生成正文。'
})
const sectionReadinessCards = computed<ReadinessCard[]>(() => {
  if (activeSection.value === 'routes') {
    return [
      {
        label: '已覆盖阶段',
        value: `${configuredRouteCount.value}/${allStageKeys.value.length}`,
        description: configuredRouteCount.value > 0 ? '其余阶段使用主模型' : '当前全部使用主模型',
        tone: configuredRouteCount.value > 0 ? 'success' : 'neutral',
      },
      {
        label: '可用文本模型',
        value: String(enabledChatModels.value.length),
        description: primaryChatModel.value ? '可用于阶段覆盖' : '先设置主模型',
        tone: enabledChatModels.value.length > 0 ? 'success' : 'warning',
      },
      {
        label: '主模型',
        value: modelDisplayName(primaryChatModel.value),
        description: primaryChatModel.value ? '未覆盖阶段的默认选择' : '阶段路由暂不可用',
        tone: primaryChatModel.value ? 'success' : 'warning',
      },
    ]
  }

  if (activeSection.value === 'embedding') {
    return [
      {
        label: '当前检索模型',
        value: modelDisplayName(defaultEmbeddingModel.value),
        description: defaultEmbeddingModel.value ? '记忆检索会使用它' : '尚未选择向量模型',
        tone: defaultEmbeddingModel.value ? 'success' : 'warning',
      },
      {
        label: '可用向量模型',
        value: String(enabledEmbeddingModels.value.length),
        description: enabledEmbeddingModels.value.length > 0 ? '已进入模型池' : '需要先拉取并选择',
        tone: enabledEmbeddingModels.value.length > 0 ? 'success' : 'warning',
      },
      {
        label: '供应商',
        value: String(activeProviders.value.length),
        description: activeProviders.value.length > 0 ? '可维护 API Key' : '尚未配置',
        tone: activeProviders.value.length > 0 ? 'success' : 'warning',
      },
    ]
  }

  return [
    {
      label: '主模型',
      value: modelDisplayName(primaryChatModel.value),
      description: primaryChatModel.value ? '默认文本生成模型' : '生成任务会被阻塞',
      tone: primaryChatModel.value ? 'success' : 'warning',
    },
    {
      label: '可用文本模型',
      value: String(enabledChatModels.value.length),
      description: enabledChatModels.value.length > 0 ? '可被阶段路由使用' : '需要先拉取并勾选',
      tone: enabledChatModels.value.length > 0 ? 'success' : 'warning',
    },
    {
      label: '供应商',
      value: String(activeProviders.value.length),
      description: activeProviders.value.length > 0 ? '可维护 API Key' : '尚未配置',
      tone: activeProviders.value.length > 0 ? 'success' : 'warning',
    },
  ]
})

const providerFetchState = (providerId: number): ProviderFetchState => {
  if (!providerFetchStates[providerId]) {
    providerFetchStates[providerId] = {
      isLoading: false,
      modelsByCapability: { chat: [], embedding: [] },
      error: '',
    }
  }
  return providerFetchStates[providerId]
}

const modelDisplayName = (model?: UserAIModel): string => {
  if (!model) {
    return '未设置'
  }
  return model.display_name || model.model_name
}

const providerTypeLabel = (providerType: ProviderType): string => providerTypeLabels[providerType]

const providerKeyLabel = (provider: UserModelProvider): string =>
  provider.api_key_preview ? `Key ${provider.api_key_preview}` : '未保存 Key'

const groupModelsByProvider = (capability: Capability): Record<number, UserAIModel[]> => {
  return models.value.reduce<Record<number, UserAIModel[]>>((result, model) => {
    if (!model.capabilities[capability]) {
      return result
    }
    result[model.provider_id] = result[model.provider_id] || []
    result[model.provider_id].push(model)
    return result
  }, {})
}

const modelNamesForProvider = (providerId: number): string[] => {
  const capability = activeModelCapability()
  const existing =
    capability === 'chat'
      ? (chatModelsByProvider.value[providerId] || []).map((model) => model.model_name)
      : (embeddingModelsByProvider.value[providerId] || []).map((model) => model.model_name)
  const fetched = providerFetchState(providerId).modelsByCapability[capability]
  return Array.from(new Set([...existing, ...fetched])).sort((a, b) => a.localeCompare(b))
}

const filteredModelNamesForProvider = (providerId: number): string[] => {
  const query = modelPickerQuery.value.trim().toLowerCase()
  const names = modelNamesForProvider(providerId)
  if (!query) {
    return names
  }
  return names.filter((modelName) => modelName.toLowerCase().includes(query))
}

const selectedModelChipsForProvider = (providerId: number): UserAIModel[] => {
  const capability = activeModelCapability()
  const source =
    capability === 'chat'
      ? chatModelsByProvider.value[providerId] || []
      : embeddingModelsByProvider.value[providerId] || []
  return source.filter((model) => model.is_enabled)
}

const chatModelForName = (providerId: number, modelName: string): UserAIModel | undefined =>
  models.value.find(
    (model) =>
      model.provider_id === providerId &&
      model.model_name === modelName &&
      Boolean(model.capabilities.chat),
  )

const embeddingModelForName = (providerId: number, modelName: string): UserAIModel | undefined =>
  models.value.find(
    (model) =>
      providerId === model.provider_id &&
      model.model_name === modelName &&
      Boolean(model.capabilities.embedding),
  )

const savedModelForActiveSection = (
  providerId: number,
  modelName: string,
): UserAIModel | undefined =>
  activeSection.value === 'embedding'
    ? embeddingModelForName(providerId, modelName)
    : chatModelForName(providerId, modelName)

const isModelSelectedForActiveSection = (providerId: number, modelName: string): boolean =>
  Boolean(savedModelForActiveSection(providerId, modelName)?.is_enabled)

const activeModelStateLabel = (providerId: number, modelName: string): string => {
  const model = savedModelForActiveSection(providerId, modelName)
  if (!model?.is_enabled) {
    return ''
  }
  if (activeSection.value === 'embedding') {
    return model.is_default_embedding ? '当前使用' : '已登记'
  }
  return model.is_default_chat ? '主模型' : '已启用'
}

const setFeedback = (type: 'success' | 'error', message: string) => {
  feedback.value = { type, message }
}

const assignProviderForm = (next: ProviderForm) => {
  Object.assign(providerForm, next)
}

const activeModelCapability = (): Capability =>
  activeSection.value === 'embedding' ? 'embedding' : 'chat'

const createProviderCapabilities = (): Record<Capability, boolean> => {
  const capability = activeModelCapability()
  return {
    chat: capability === 'chat',
    embedding: capability === 'embedding',
  }
}

const providerCapabilities = (provider: UserModelProvider): Record<Capability, boolean> => ({
  chat: Boolean(provider.capabilities?.chat),
  embedding: Boolean(provider.capabilities?.embedding),
})

const isModelPickerOpen = (providerId: number): boolean =>
  activeModelPickerProviderId.value === providerId

const closeModelPicker = () => {
  activeModelPickerProviderId.value = null
  modelPickerQuery.value = ''
}

const loadBundle = async () => {
  isLoading.value = true
  try {
    const bundle = await getLLMConfigBundle()
    providers.value = bundle.providers
    models.value = bundle.models
    for (const key of allStageKeys.value) {
      routeSelections[key] = ''
    }
    for (const route of bundle.stage_routes) {
      if (allStageKeys.value.includes(route.stage)) {
        routeSelections[route.stage] = String(route.model_id)
      }
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : '未知错误'
    setFeedback('error', `读取模型设置失败：${message}`)
  } finally {
    isLoading.value = false
  }
}

const beginCreateProvider = () => {
  editingProviderId.value = null
  providerFormMode.value = 'create'
  assignProviderForm(emptyProviderForm())
}

const beginEditProvider = (provider: UserModelProvider) => {
  editingProviderId.value = provider.id
  providerFormMode.value = 'edit'
  assignProviderForm({
    name: provider.name,
    provider_type: provider.provider_type,
    base_url: provider.base_url,
    api_key: '',
    is_enabled: provider.is_enabled,
  })
}

const cancelProviderForm = () => {
  editingProviderId.value = null
  providerFormMode.value = null
  assignProviderForm(emptyProviderForm())
}

const saveProviderForm = async () => {
  const payload: ProviderCreate = {
    name: providerForm.name.trim(),
    provider_type: providerForm.provider_type,
    base_url: providerForm.base_url.trim(),
    api_key: providerForm.api_key.trim() || null,
    capabilities: createProviderCapabilities(),
    is_enabled: providerForm.is_enabled,
  }
  if (!payload.name || !payload.base_url) {
    setFeedback('error', '请填写供应商名称和 API URL。')
    return
  }

  isSavingProvider.value = true
  try {
    const saved = editingProviderId.value
      ? await updateProvider(editingProviderId.value, {
          name: payload.name,
          provider_type: payload.provider_type,
          base_url: payload.base_url,
          ...(providerForm.api_key.trim() ? { api_key: payload.api_key } : {}),
          is_enabled: payload.is_enabled,
        })
      : await createProvider(payload)

    const index = providers.value.findIndex((provider) => provider.id === saved.id)
    if (index >= 0) {
      providers.value[index] = saved
    } else {
      providers.value.push(saved)
    }
    cancelProviderForm()
    setFeedback('success', '供应商已保存。')
    emit('saved')
  } catch (error) {
    const message = error instanceof Error ? error.message : '未知错误'
    setFeedback('error', `供应商保存失败：${message}`)
  } finally {
    isSavingProvider.value = false
  }
}

const toggleProviderEnabled = async (provider: UserModelProvider) => {
  isSavingProvider.value = true
  try {
    await updateProvider(provider.id, { is_enabled: !provider.is_enabled })
    await loadBundle()
    setFeedback('success', provider.is_enabled ? '供应商已停用。' : '供应商已启用。')
    emit('saved')
  } catch (error) {
    const message = error instanceof Error ? error.message : '未知错误'
    setFeedback('error', `供应商状态更新失败：${message}`)
  } finally {
    isSavingProvider.value = false
  }
}

const deleteProviderFromCard = async (provider: UserModelProvider) => {
  const confirmed = await globalAlert.showConfirm(
    `确定删除供应商“${provider.name}”吗？关联模型和阶段路由也会一起删除。`,
    '删除供应商',
  )
  if (!confirmed) {
    return
  }

  isSavingProvider.value = true
  try {
    await deleteProvider(provider.id)
    if (editingProviderId.value === provider.id) {
      cancelProviderForm()
    }
    delete providerFetchStates[provider.id]
    await loadBundle()
    setFeedback('success', '供应商已删除。')
    emit('saved')
  } catch (error) {
    const message = error instanceof Error ? error.message : '未知错误'
    setFeedback('error', `删除供应商失败：${message}`)
  } finally {
    isSavingProvider.value = false
  }
}

const loadProviderModels = async (provider: UserModelProvider) => {
  const state = providerFetchState(provider.id)
  const capability = activeModelCapability()
  state.isLoading = true
  state.error = ''
  try {
    state.modelsByCapability[capability] = await getProviderModels(provider.id)
    if (state.modelsByCapability[capability].length === 0) {
      state.error = '未拉取到模型，请检查 API URL 与 API Key。'
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : '未知错误'
    state.error = `拉取模型失败：${message}`
  } finally {
    state.isLoading = false
  }
}

const openProviderModelPicker = async (provider: UserModelProvider) => {
  if (!provider.is_enabled) {
    return
  }
  activeModelPickerProviderId.value = provider.id
  modelPickerQuery.value = ''
  await loadProviderModels(provider)
}

const createModelPayload = (
  provider: UserModelProvider,
  modelName: string,
  capability: Capability,
): UserAIModelCreate => {
  const isChat = capability === 'chat'
  if (isChat) {
    return {
      provider_id: provider.id,
      display_name: modelName,
      model_name: modelName,
      capabilities: { chat: true, embedding: false },
      context_window: null,
      is_default_chat: !primaryChatModel.value,
      is_default_embedding: false,
      is_enabled: true,
      sort_order: 0,
    }
  }

  return {
    provider_id: provider.id,
    display_name: modelName,
    model_name: modelName,
    capabilities: { chat: false, embedding: true },
    context_window: null,
    is_default_chat: false,
    is_default_embedding: true,
    is_enabled: true,
    sort_order: 0,
  }
}

const upsertModelForCapability = async (
  provider: UserModelProvider,
  modelName: string,
  capability: Capability,
): Promise<UserAIModel> => {
  const existing =
    capability === 'chat'
      ? chatModelForName(provider.id, modelName)
      : embeddingModelForName(provider.id, modelName)
  if (!existing) {
    return createUserModel(createModelPayload(provider, modelName, capability))
  }
  if (!existing.is_enabled) {
    return updateUserModel(existing.id, { is_enabled: true })
  }
  return existing
}

const toggleChatModel = async (provider: UserModelProvider, modelName: string, event: Event) => {
  const checked = (event.target as HTMLInputElement).checked
  const existing = chatModelForName(provider.id, modelName)
  try {
    if (checked) {
      await upsertModelForCapability(provider, modelName, 'chat')
    } else if (existing) {
      if (existing.is_default_chat) {
        setFeedback('error', '主模型不能直接停用，请先选择另一个主模型。')
        ;(event.target as HTMLInputElement).checked = true
        return
      }
      await updateUserModel(existing.id, { is_enabled: false })
    }
    await loadBundle()
    emit('saved')
  } catch (error) {
    const message = error instanceof Error ? error.message : '未知错误'
    setFeedback('error', `更新文本生成模型失败：${message}`)
  }
}

const setPrimaryChatModel = async (model?: UserAIModel) => {
  if (!model) {
    return
  }
  try {
    await updateUserModel(model.id, { is_enabled: true, is_default_chat: true })
    await loadBundle()
    emit('saved')
  } catch (error) {
    const message = error instanceof Error ? error.message : '未知错误'
    setFeedback('error', `设置主模型失败：${message}`)
  }
}

const setPrimaryChatModelById = async (event: Event) => {
  const modelId = Number((event.target as HTMLSelectElement).value)
  if (!modelId) {
    return
  }
  await setPrimaryChatModel(models.value.find((model) => model.id === modelId))
}

const selectEmbeddingModel = async (provider: UserModelProvider, modelName: string) => {
  try {
    const selected = await upsertModelForCapability(provider, modelName, 'embedding')
    const embeddingModels = models.value.filter((model) => model.capabilities.embedding)
    await Promise.all(
      embeddingModels.map((model) =>
        updateUserModel(model.id, {
          is_enabled: model.id === selected.id,
          is_default_embedding: model.id === selected.id,
        }),
      ),
    )
    if (!embeddingModels.some((model) => model.id === selected.id)) {
      await updateUserModel(selected.id, { is_enabled: true, is_default_embedding: true })
    }
    await loadBundle()
    emit('saved')
  } catch (error) {
    const message = error instanceof Error ? error.message : '未知错误'
    setFeedback('error', `设置向量模型失败：${message}`)
  }
}

const deleteModelForActiveSection = async (provider: UserModelProvider, modelName: string) => {
  const model = savedModelForActiveSection(provider.id, modelName)
  if (!model) {
    return
  }
  if (model.is_default_chat) {
    setFeedback('error', '主模型不能直接删除，请先选择另一个主模型。')
    return
  }
  if (model.is_default_embedding) {
    setFeedback('error', '当前向量模型不能直接删除，请先选择另一个向量模型。')
    return
  }

  const label = model.display_name || model.model_name
  const confirmed = await globalAlert.showConfirm(
    `确定删除模型“${label}”吗？关联的阶段路由也会一起移除。`,
    '删除模型',
  )
  if (!confirmed) {
    return
  }

  try {
    await deleteUserModel(model.id)
    await loadBundle()
    setFeedback('success', '模型已删除。')
    emit('saved')
  } catch (error) {
    const message = error instanceof Error ? error.message : '未知错误'
    setFeedback('error', `删除模型失败：${message}`)
  }
}

const saveRoutes = async () => {
  const routes = Object.entries(routeSelections)
    .filter(([, modelId]) => modelId)
    .map(([stage, modelId]) => ({ stage, model_id: Number(modelId) }))

  isSavingRoutes.value = true
  try {
    const savedRoutes = await saveStageRoutes({ routes })
    for (const key of allStageKeys.value) {
      routeSelections[key] = ''
    }
    for (const route of savedRoutes) {
      if (allStageKeys.value.includes(route.stage)) {
        routeSelections[route.stage] = String(route.model_id)
      }
    }
    setFeedback('success', '阶段路由已保存。')
    emit('saved')
  } catch (error) {
    const message = error instanceof Error ? error.message : '未知错误'
    setFeedback('error', `阶段路由保存失败：${message}`)
  } finally {
    isSavingRoutes.value = false
  }
}

const providerName = (providerId: number): string =>
  providers.value.find((provider) => provider.id === providerId)?.name || `供应商 ${providerId}`

onMounted(() => {
  void loadBundle()
})
</script>

<style scoped>
.model-routing {
  display: grid;
  gap: var(--md-spacing-5);
}

.model-routing__topbar,
.model-routing__form-head,
.model-routing__provider-head,
.model-routing__provider-actions,
.model-routing__model-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--md-spacing-3);
}

.model-routing__topbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
  gap: var(--md-spacing-4);
}

.model-routing__section-copy {
  min-width: 0;
}

.model-routing__eyebrow {
  margin: 0 0 var(--md-spacing-1);
  color: var(--md-primary-dark);
}

.model-routing__section-copy h3 {
  margin: 0;
  color: var(--md-on-surface);
}

.model-routing__topbar-actions {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: var(--md-spacing-2);
  flex: 0 0 auto;
}

.model-routing__readiness {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--md-spacing-3);
  padding-bottom: var(--md-spacing-4);
  border-bottom: 1px solid var(--md-outline-variant);
}

.model-routing__readiness-item {
  display: grid;
  align-content: start;
  min-width: 0;
  gap: var(--md-spacing-1);
  min-height: 76px;
  padding: var(--md-spacing-3) var(--md-spacing-4);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-md);
  background: var(--md-surface);
  color: var(--md-on-surface-variant);
}

.model-routing__readiness-item.is-success strong {
  color: var(--md-success);
}

.model-routing__readiness-item.is-warning strong {
  color: var(--md-on-warning-container);
}

.model-routing__readiness-label {
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-small);
  font-weight: 600;
}

.model-routing__readiness-item strong {
  min-width: 0;
  overflow: hidden;
  color: var(--md-on-surface);
  font-size: var(--md-title-medium);
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-routing__panel,
.model-routing__provider-card {
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-lg);
  padding: var(--md-spacing-4);
  background: var(--md-surface);
}

.model-routing__provider-grid,
.model-routing__form,
.model-routing__model-list,
.model-routing__selected-models,
.model-routing__stage-list,
.model-routing__stage-groups {
  display: grid;
  gap: var(--md-spacing-3);
}

.model-routing__provider-card {
  position: relative;
  display: grid;
  gap: var(--md-spacing-3);
  overflow: visible;
}

.model-routing__primary-panel {
  display: grid;
  grid-template-columns: minmax(180px, 0.65fr) minmax(260px, 1fr);
  align-items: end;
  gap: var(--md-spacing-4);
  background: color-mix(in srgb, var(--md-surface) 88%, var(--md-surface-dim));
}

.model-routing__primary-copy h3 {
  margin: 0;
  color: var(--md-on-surface);
}

.model-routing__primary-field {
  margin: 0;
}

.model-routing__provider-head h3,
.model-routing__form-head h3,
.model-routing__stage-group h4 {
  margin: 0;
  color: var(--md-on-surface);
}

.model-routing__provider-head p,
.model-routing__hint,
.model-routing__empty {
  margin: 4px 0 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.model-routing__provider-url {
  display: block;
  max-width: 100%;
  margin-top: var(--md-spacing-2);
  color: var(--md-on-surface-variant);
  font-family: var(--md-font-mono);
  font-size: var(--md-body-small);
  word-break: break-all;
}

.model-routing__provider-main {
  min-width: 0;
}

.model-routing__provider-title-row,
.model-routing__provider-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--md-spacing-2);
}

.model-routing__provider-state,
.model-routing__provider-type {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  border-radius: var(--md-radius-full);
  padding: 0 10px;
  font-size: var(--md-label-small);
  font-weight: 600;
  white-space: nowrap;
}

.model-routing__provider-state.is-enabled {
  background: var(--md-success-container);
  color: var(--md-on-success-container);
}

.model-routing__provider-state.is-disabled {
  background: var(--md-surface-container-high);
  color: var(--md-on-surface-variant);
}

.model-routing__provider-type {
  border: 1px solid var(--md-outline-variant);
  background: var(--md-surface);
  color: var(--md-on-surface);
}

.model-routing__provider-meta {
  margin-top: var(--md-spacing-2);
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.model-routing__provider-card-actions {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--md-spacing-2);
}

.model-routing__model-list-title {
  margin: 0;
  color: var(--md-on-surface-variant);
}

.model-routing__model-picker {
  position: absolute;
  top: 132px;
  right: var(--md-spacing-4);
  z-index: 20;
  width: min(420px, calc(100% - var(--md-spacing-8)));
  max-height: 420px;
  overflow: auto;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-lg);
  padding: var(--md-spacing-3);
  background: var(--md-surface);
  box-shadow: var(--md-elevation-3);
}

.model-routing__picker-head,
.model-routing__picker-row,
.model-routing__selected-chip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--md-spacing-3);
}

.model-routing__picker-head {
  margin-bottom: var(--md-spacing-3);
  color: var(--md-on-surface);
}

.model-routing__picker-search {
  margin-bottom: var(--md-spacing-3);
}

.model-routing__picker-list {
  display: grid;
  gap: var(--md-spacing-1);
}

.model-routing__picker-row {
  min-height: 44px;
  border: 1px solid transparent;
  border-radius: var(--md-radius-md);
  padding: var(--md-spacing-2) var(--md-spacing-3);
  color: var(--md-on-surface);
  cursor: pointer;
  transition:
    background-color var(--md-duration-short) var(--md-easing-standard),
    border-color var(--md-duration-short) var(--md-easing-standard);
}

.model-routing__picker-row:hover {
  background: var(--md-surface-container);
}

.model-routing__picker-row.is-selected {
  border-color: var(--md-primary);
  background: var(--md-primary-container);
  color: var(--md-on-primary-container);
}

.model-routing__picker-model-name {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: var(--md-spacing-2);
}

.model-routing__picker-model-name,
.model-routing__picker-model-name > small {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-routing__picker-model-name > small {
  flex: 0 0 auto;
  border-radius: var(--md-radius-full);
  padding: 2px 6px;
  background: var(--md-surface);
  color: var(--md-primary-dark);
  font-size: var(--md-label-small);
  font-weight: 600;
}

.model-routing__selected-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--md-spacing-2);
}

.model-routing__selected-chip {
  max-width: 100%;
  min-height: 34px;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-full);
  padding: 4px 6px 4px 12px;
  background: var(--md-surface);
  color: var(--md-on-surface);
}

.model-routing__selected-chip > span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-routing__selected-chip small {
  border-radius: var(--md-radius-full);
  padding: 2px 6px;
  background: var(--md-primary-container);
  color: var(--md-on-primary-container);
  font-size: var(--md-label-small);
  white-space: nowrap;
}

.model-routing__model-row {
  width: 100%;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-md);
  background: var(--md-surface);
  color: var(--md-on-surface);
  padding: var(--md-spacing-3);
  text-align: left;
  cursor: pointer;
}

.model-routing__model-row:hover:not(.is-disabled) {
  border-color: var(--md-primary);
  background: var(--md-primary-container);
  color: var(--md-on-primary-container);
}

.model-routing__model-row.is-disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.model-routing__model-row strong,
.model-routing__stage-row strong {
  display: block;
  font-size: var(--md-body-medium);
}

.model-routing__model-row small,
.model-routing__stage-row small {
  display: block;
  margin-top: 2px;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.model-routing__model-controls {
  display: inline-flex;
  align-items: center;
  gap: var(--md-spacing-2);
}

.model-routing__delete-btn {
  border: none;
  border-radius: var(--md-radius-full);
  min-width: 44px;
  min-height: 44px;
  padding: 0 12px;
  background: var(--md-error-container);
  color: var(--md-on-error-container);
  cursor: pointer;
  font-size: var(--md-label-small);
  font-weight: 600;
  white-space: nowrap;
}

.model-routing__delete-btn:hover {
  filter: brightness(0.96);
}

.model-routing__toggle {
  border: none;
  border-radius: var(--md-radius-full);
  min-width: 44px;
  min-height: 44px;
  padding: 0 12px;
  cursor: pointer;
  font-size: var(--md-label-small);
  font-weight: 600;
  white-space: nowrap;
}

.model-routing__toggle:disabled,
.model-routing__provider-delete:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.model-routing__toggle.is-on {
  border: 1px solid var(--md-outline);
  background: var(--md-surface);
  color: var(--md-primary-dark);
}

.model-routing__toggle.is-off {
  background: var(--md-primary-container);
  color: var(--md-on-primary-container);
}

.model-routing__toggle:hover:not(:disabled) {
  background: var(--md-surface-container);
}

.model-routing__provider-delete {
  border: none;
  border-radius: var(--md-radius-full);
  min-width: 44px;
  min-height: 44px;
  padding: 0 12px;
  background: var(--md-error-container);
  color: var(--md-error-strong);
  cursor: pointer;
  font-size: var(--md-label-small);
  font-weight: 600;
  white-space: nowrap;
}

.model-routing__provider-delete:hover:not(:disabled) {
  background: var(--md-error-container);
  color: var(--md-on-error-container);
}

.model-routing__check {
  display: flex;
  align-items: center;
  gap: var(--md-spacing-2);
  color: var(--md-on-surface);
  font-size: var(--md-body-medium);
}

.model-routing__check input,
.model-routing__model-controls input,
.model-routing__picker-row input {
  width: 20px;
  height: 20px;
  flex: 0 0 auto;
}

.model-routing__link {
  border: none;
  background: transparent;
  color: var(--md-primary-dark);
  cursor: pointer;
  font-weight: 600;
  min-height: 44px;
  padding: 0 var(--md-spacing-2);
}

.model-routing__link:focus-visible,
.model-routing__delete-btn:focus-visible,
.model-routing__toggle:focus-visible,
.model-routing__provider-delete:focus-visible,
.model-routing__picker-row:focus-within {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}

.model-routing__feedback {
  border-radius: var(--md-radius-md);
  padding: var(--md-spacing-3);
  font-size: var(--md-body-medium);
}

.model-routing__feedback.is-success {
  background-color: var(--md-success-container);
  color: var(--md-on-success-container);
}

.model-routing__feedback.is-error,
.model-routing__hint.is-error {
  background-color: var(--md-error-container);
  color: var(--md-on-error-container);
}

.model-routing__hint.is-error {
  border-radius: var(--md-radius-md);
  padding: var(--md-spacing-2);
}

.model-routing__empty-state {
  display: grid;
  justify-items: start;
  gap: var(--md-spacing-2);
  padding: var(--md-spacing-5);
  border: 1px dashed var(--md-outline);
  border-radius: var(--md-radius-lg);
  background: var(--md-surface);
}

.model-routing__empty-state p {
  margin: 0;
}

.model-routing__stage-group {
  display: grid;
  gap: var(--md-spacing-3);
}

.model-routing__stage-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--md-spacing-2);
  align-items: center;
  padding: var(--md-spacing-3);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-md);
  background: var(--md-surface);
}

@media (min-width: 960px) {
  .model-routing__provider-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .model-routing__stage-row {
    grid-template-columns: minmax(220px, 0.8fr) minmax(240px, 1fr);
  }
}

@media (max-width: 860px) {
  .model-routing__primary-panel {
    grid-template-columns: minmax(0, 1fr);
  }

  .model-routing__readiness {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 640px) {
  .model-routing__topbar,
  .model-routing__form-head,
  .model-routing__provider-head,
  .model-routing__provider-actions,
  .model-routing__model-row {
    flex-direction: column;
    align-items: stretch;
  }

  .model-routing__topbar-actions {
    width: 100%;
  }

  .model-routing__topbar-actions .md-btn {
    flex: 1 1 140px;
  }

  .model-routing__topbar {
    grid-template-columns: minmax(0, 1fr);
  }

  .model-routing__model-picker {
    position: static;
    width: 100%;
    max-height: 360px;
  }
}
</style>
