<template>
  <section class="model-routing">
    <header class="model-routing__header">
      <div>
        <h3 class="md-title-large model-routing__title">个人模型路由</h3>
        <p class="md-body-medium model-routing__subtitle">{{ sectionSubtitle }}</p>
      </div>
      <button type="button" class="md-btn md-btn-outlined md-ripple" :disabled="isLoading" @click="loadBundle">
        {{ isLoading ? '刷新中...' : '刷新' }}
      </button>
    </header>

    <div v-if="feedback.message" :class="['model-routing__feedback', `is-${feedback.type}`]">
      {{ feedback.message }}
    </div>

    <section v-if="shouldRenderSection('providers')" class="model-routing__panel">
      <div class="model-routing__panel-head">
        <h4 class="md-title-medium">供应商与 API Key</h4>
        <button type="button" class="model-routing__link" @click="resetProviderForm">新增</button>
      </div>

      <div class="model-routing__list">
        <button
          v-for="provider in providers"
          :key="provider.id"
          type="button"
          class="model-routing__item"
          :class="{ active: editingProviderId === provider.id }"
          @click="editProvider(provider)"
        >
          <span>
            <strong>{{ provider.name }}</strong>
            <small>{{ provider.provider_type }} · {{ provider.api_key_preview || '未显示 Key' }}</small>
          </span>
          <span :class="['model-routing__status', provider.is_enabled ? 'is-on' : 'is-off']">
            {{ provider.is_enabled ? '启用' : '停用' }}
          </span>
        </button>
        <p v-if="providers.length === 0" class="model-routing__empty">还没有供应商。</p>
      </div>

      <div class="model-routing__form">
        <label class="md-text-field">
          <span class="md-text-field-label">名称</span>
          <input v-model="providerForm.name" class="md-text-field-input" type="text" placeholder="如 OpenAI / DeepSeek / 本地 Ollama">
        </label>

        <label class="md-text-field">
          <span class="md-text-field-label">类型</span>
          <select v-model="providerForm.provider_type" class="md-text-field-input">
            <option value="openai_compatible">OpenAI 兼容</option>
            <option value="ollama">Ollama</option>
            <option value="custom">自定义</option>
          </select>
        </label>

        <label class="md-text-field">
          <span class="md-text-field-label">API URL</span>
          <input v-model="providerForm.base_url" class="md-text-field-input" type="text" placeholder="https://api.example.com/v1">
        </label>

        <label class="md-text-field">
          <span class="md-text-field-label">API Key</span>
          <input
            v-model="providerForm.api_key"
            class="md-text-field-input"
            type="password"
            :placeholder="editingProviderId ? '留空则保留已保存 Key' : '请输入 API Key，Ollama 可留空'"
          >
        </label>

        <label class="model-routing__check">
          <input v-model="providerForm.is_enabled" type="checkbox">
          <span>启用供应商</span>
        </label>

        <button type="button" class="md-btn md-btn-filled md-ripple" :disabled="isSavingProvider" @click="saveProviderForm">
          {{ isSavingProvider ? '保存中...' : (editingProviderId ? '保存供应商' : '新增供应商') }}
        </button>
      </div>
    </section>

    <section v-if="shouldRenderSection('models')" class="model-routing__panel">
      <div class="model-routing__panel-head">
        <h4 class="md-title-medium">可用模型</h4>
        <button type="button" class="model-routing__link" @click="resetModelForm">新增</button>
      </div>

      <div class="model-routing__list">
        <button
          v-for="model in models"
          :key="model.id"
          type="button"
          class="model-routing__item"
          :class="{ active: editingModelId === model.id }"
          @click="editModel(model)"
        >
          <span>
            <strong>{{ model.display_name }}</strong>
            <small>{{ model.model_name }} · {{ providerName(model.provider_id) }}</small>
          </span>
          <span class="model-routing__badges">
            <em v-if="model.capabilities.chat">Chat</em>
            <em v-if="model.capabilities.embedding">Embedding</em>
          </span>
        </button>
        <p v-if="models.length === 0" class="model-routing__empty">还没有可用模型。</p>
      </div>

      <div class="model-routing__form">
        <label class="md-text-field">
          <span class="md-text-field-label">所属供应商</span>
          <select v-model.number="modelForm.provider_id" class="md-text-field-input" :disabled="providers.length === 0">
            <option :value="0">请选择供应商</option>
            <option v-for="provider in providers" :key="provider.id" :value="provider.id">
              {{ provider.name }}
            </option>
          </select>
        </label>

        <label class="md-text-field">
          <span class="md-text-field-label">显示名称</span>
          <input v-model="modelForm.display_name" class="md-text-field-input" type="text" placeholder="如 写作模型 / 复盘模型">
        </label>

        <label class="md-text-field">
          <span class="md-text-field-label">模型名</span>
          <input v-model="modelForm.model_name" class="md-text-field-input" type="text" placeholder="如 gpt-4o-mini">
        </label>

        <div class="model-routing__checks">
          <label class="model-routing__check">
            <input v-model="modelForm.capabilities.chat" type="checkbox">
            <span>Chat</span>
          </label>
          <label class="model-routing__check">
            <input v-model="modelForm.capabilities.embedding" type="checkbox">
            <span>Embedding</span>
          </label>
          <label class="model-routing__check">
            <input v-model="modelForm.is_default_chat" type="checkbox">
            <span>默认 Chat</span>
          </label>
          <label class="model-routing__check">
            <input v-model="modelForm.is_default_embedding" type="checkbox">
            <span>默认 Embedding</span>
          </label>
          <label class="model-routing__check">
            <input v-model="modelForm.is_enabled" type="checkbox">
            <span>启用模型</span>
          </label>
        </div>

        <button type="button" class="md-btn md-btn-filled md-ripple" :disabled="isSavingModel" @click="saveModelForm">
          {{ isSavingModel ? '保存中...' : (editingModelId ? '保存模型' : '新增模型') }}
        </button>
      </div>
    </section>

    <section v-if="shouldRenderSection('routes')" class="model-routing__panel model-routing__stages">
      <div class="model-routing__panel-head">
        <h4 class="md-title-medium">AI 阶段默认模型</h4>
        <button type="button" class="md-btn md-btn-filled-tonal md-ripple" :disabled="isSavingRoutes" @click="saveRoutes">
          {{ isSavingRoutes ? '保存中...' : '保存阶段路由' }}
        </button>
      </div>

      <div class="model-routing__stage-groups">
        <div v-for="group in stageGroups" :key="group.title" class="model-routing__stage-group">
          <h5 class="md-title-small">{{ group.title }}</h5>
          <div class="model-routing__stage-list">
            <label v-for="stage in group.stages" :key="stage.key" class="model-routing__stage-row">
              <span>
                <strong>{{ stage.label }}</strong>
                <small>{{ stage.description }}</small>
              </span>
              <select v-model="routeSelections[stage.key]" class="md-text-field-input">
                <option value="">使用默认 {{ stage.capability === 'embedding' ? 'Embedding' : 'Chat' }} 模型</option>
                <option v-for="model in modelsForCapability(stage.capability)" :key="model.id" :value="String(model.id)">
                  {{ model.display_name }} · {{ model.model_name }}
                </option>
              </select>
            </label>
          </div>
        </div>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import {
  createProvider,
  createUserModel,
  getLLMConfigBundle,
  saveStageRoutes,
  updateProvider,
  updateUserModel,
  type ProviderCreate,
  type ProviderType,
  type UserAIModel,
  type UserAIModelCreate,
  type UserModelProvider,
} from '@/api/llm';

type Capability = 'chat' | 'embedding';

interface StageDefinition {
  key: string;
  label: string;
  capability: Capability;
  description: string;
}

interface StageGroup {
  title: string;
  stages: StageDefinition[];
}

type RoutingSection = 'providers' | 'models' | 'routes';

interface ProviderForm {
  name: string;
  provider_type: ProviderType;
  base_url: string;
  api_key: string;
  is_enabled: boolean;
}

interface ModelForm {
  provider_id: number;
  display_name: string;
  model_name: string;
  capabilities: Record<Capability, boolean>;
  is_default_chat: boolean;
  is_default_embedding: boolean;
  is_enabled: boolean;
}

const emit = defineEmits<{
  (event: 'saved'): void;
}>();

const props = defineProps<{ activeSection?: RoutingSection }>();

const stageGroups: StageGroup[] = [
  {
    title: '导入与灵感',
    stages: [
      { key: 'import_analysis', label: '导入分析', capability: 'chat', description: '导入小说角色筛选与结构分析' },
      { key: 'concept_conversation', label: '灵感对话', capability: 'chat', description: '灵感模式多轮概念对话' },
      { key: 'world_blueprint', label: '完整蓝图', capability: 'chat', description: '由灵感历史生成整本书蓝图' },
    ],
  },
  {
    title: '规划',
    stages: [
      { key: 'chapter_outline', label: '章节大纲', capability: 'chat', description: '续写章节大纲' },
      { key: 'chapter_blueprint', label: '章节蓝图', capability: 'chat', description: '单章或批量章节蓝图' },
      { key: 'chapter_mission', label: '导演脚本', capability: 'chat', description: '章节写作前的执行脚本' },
    ],
  },
  {
    title: '写作',
    stages: [
      { key: 'chapter_preview', label: '章节预览', capability: 'chat', description: '预览、评估与扩写' },
      { key: 'chapter_writing', label: '正文生成', capability: 'chat', description: '章节正文主生成' },
      { key: 'chapter_rewrite', label: '护栏重写', capability: 'chat', description: '一致性和护栏自动修复' },
      { key: 'chapter_compression', label: '字数压缩', capability: 'chat', description: '超长章节压缩' },
      { key: 'chapter_enrichment', label: '章节润色', capability: 'chat', description: '对话、场景和章节增强' },
    ],
  },
  {
    title: '复盘与优化',
    stages: [
      { key: 'version_review', label: '版本评审', capability: 'chat', description: '多版本评审和单版本评价' },
      { key: 'chapter_optimization', label: '章节优化', capability: 'chat', description: '节奏、心理、环境、对白优化' },
      { key: 'deep_review', label: '深度审稿', capability: 'chat', description: '六维复盘、读者模拟、自我批评' },
      { key: 'emotion_analysis', label: '情绪曲线', capability: 'chat', description: '章节情绪曲线分析' },
      { key: 'consistency_check', label: '一致性检查', capability: 'chat', description: '只诊断问题，不改正文' },
    ],
  },
  {
    title: '记忆与 RAG',
    stages: [
      { key: 'summary_memory', label: '摘要记忆', capability: 'chat', description: '章节摘要、全局摘要、角色状态' },
      { key: 'rag_embedding', label: '向量生成', capability: 'embedding', description: '章节、摘要、查询向量' },
      { key: 'rag_query', label: '检索规划', capability: 'chat', description: '检索查询生成和上下文过滤' },
      { key: 'foreshadowing', label: '伏笔处理', capability: 'chat', description: '伏笔候选、状态判断和提醒' },
    ],
  },
];

const providers = ref<UserModelProvider[]>([]);
const models = ref<UserAIModel[]>([]);
const routeSelections = reactive<Record<string, string>>({});
const isLoading = ref(false);
const isSavingProvider = ref(false);
const isSavingModel = ref(false);
const isSavingRoutes = ref(false);
const editingProviderId = ref<number | null>(null);
const editingModelId = ref<number | null>(null);
const feedback = ref<{ type: 'success' | 'error'; message: string }>({ type: 'success', message: '' });

const emptyProviderForm = (): ProviderForm => ({
  name: '',
  provider_type: 'openai_compatible',
  base_url: '',
  api_key: '',
  is_enabled: true,
});

const emptyModelForm = (): ModelForm => ({
  provider_id: providers.value[0]?.id ?? 0,
  display_name: '',
  model_name: '',
  capabilities: { chat: true, embedding: false },
  is_default_chat: false,
  is_default_embedding: false,
  is_enabled: true,
});

const providerForm = reactive<ProviderForm>(emptyProviderForm());
const modelForm = reactive<ModelForm>(emptyModelForm());

const allStageKeys = computed(() => stageGroups.flatMap(group => group.stages.map(stage => stage.key)));
const sectionSubtitles: Record<RoutingSection, string> = {
  providers: '维护供应商地址、类型与 API Key。',
  models: '维护可用模型、能力标签和默认模型。',
  routes: '为不同 AI 阶段指定默认模型。',
};

const shouldRenderSection = (section: RoutingSection): boolean => (
  props.activeSection === undefined || props.activeSection === section
);

const sectionSubtitle = computed(() => {
  return props.activeSection
    ? sectionSubtitles[props.activeSection]
    : '配置多套供应商、可用模型，并为不同 AI 阶段指定默认模型。';
});

const setFeedback = (type: 'success' | 'error', message: string) => {
  feedback.value = { type, message };
};

const assignProviderForm = (next: ProviderForm) => {
  Object.assign(providerForm, next);
};

const assignModelForm = (next: ModelForm) => {
  Object.assign(modelForm, next);
};

const loadBundle = async () => {
  isLoading.value = true;
  try {
    const bundle = await getLLMConfigBundle();
    providers.value = bundle.providers;
    models.value = bundle.models;
    for (const key of allStageKeys.value) {
      routeSelections[key] = '';
    }
    for (const route of bundle.stage_routes) {
      routeSelections[route.stage] = String(route.model_id);
    }

    if (providers.value.length === 0 && bundle.legacy) {
      assignProviderForm({
        name: '默认供应商',
        provider_type: 'openai_compatible',
        base_url: bundle.legacy.llm_provider_url || '',
        api_key: bundle.legacy.llm_provider_api_key || '',
        is_enabled: true,
      });
      assignModelForm({
        provider_id: 0,
        display_name: bundle.legacy.llm_provider_model || '默认 Chat 模型',
        model_name: bundle.legacy.llm_provider_model || '',
        capabilities: { chat: true, embedding: false },
        is_default_chat: true,
        is_default_embedding: false,
        is_enabled: true,
      });
    } else {
      resetProviderForm();
      resetModelForm();
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : '未知错误';
    setFeedback('error', `读取模型路由失败：${message}`);
  } finally {
    isLoading.value = false;
  }
};

const resetProviderForm = () => {
  editingProviderId.value = null;
  assignProviderForm(emptyProviderForm());
};

const editProvider = (provider: UserModelProvider) => {
  editingProviderId.value = provider.id;
  assignProviderForm({
    name: provider.name,
    provider_type: provider.provider_type,
    base_url: provider.base_url,
    api_key: '',
    is_enabled: provider.is_enabled,
  });
};

const saveProviderForm = async () => {
  const payload: ProviderCreate = {
    name: providerForm.name.trim(),
    provider_type: providerForm.provider_type,
    base_url: providerForm.base_url.trim(),
    api_key: providerForm.api_key.trim() || null,
    is_enabled: providerForm.is_enabled,
  };
  if (!payload.name || !payload.base_url) {
    setFeedback('error', '请填写供应商名称和 API URL。');
    return;
  }

  isSavingProvider.value = true;
  try {
    const saved = editingProviderId.value
      ? await updateProvider(editingProviderId.value, {
          name: payload.name,
          provider_type: payload.provider_type,
          base_url: payload.base_url,
          ...(providerForm.api_key.trim() ? { api_key: payload.api_key } : {}),
          is_enabled: payload.is_enabled,
        })
      : await createProvider(payload);

    const index = providers.value.findIndex(provider => provider.id === saved.id);
    if (index >= 0) {
      providers.value[index] = saved;
    } else {
      providers.value.push(saved);
    }
    if (!modelForm.provider_id) {
      modelForm.provider_id = saved.id;
    }
    editingProviderId.value = saved.id;
    providerForm.api_key = '';
    setFeedback('success', '供应商已保存。');
    emit('saved');
  } catch (error) {
    const message = error instanceof Error ? error.message : '未知错误';
    setFeedback('error', `供应商保存失败：${message}`);
  } finally {
    isSavingProvider.value = false;
  }
};

const resetModelForm = () => {
  editingModelId.value = null;
  assignModelForm(emptyModelForm());
};

const editModel = (model: UserAIModel) => {
  editingModelId.value = model.id;
  assignModelForm({
    provider_id: model.provider_id,
    display_name: model.display_name,
    model_name: model.model_name,
    capabilities: {
      chat: Boolean(model.capabilities.chat),
      embedding: Boolean(model.capabilities.embedding),
    },
    is_default_chat: model.is_default_chat,
    is_default_embedding: model.is_default_embedding,
    is_enabled: model.is_enabled,
  });
};

const saveModelForm = async () => {
  if (!modelForm.provider_id || !modelForm.display_name.trim() || !modelForm.model_name.trim()) {
    setFeedback('error', '请先选择供应商，并填写模型显示名称和模型名。');
    return;
  }

  const payload: UserAIModelCreate = {
    provider_id: modelForm.provider_id,
    display_name: modelForm.display_name.trim(),
    model_name: modelForm.model_name.trim(),
    capabilities: { ...modelForm.capabilities },
    context_window: null,
    is_default_chat: modelForm.is_default_chat,
    is_default_embedding: modelForm.is_default_embedding,
    is_enabled: modelForm.is_enabled,
    sort_order: 0,
  };

  isSavingModel.value = true;
  try {
    const saved = editingModelId.value
      ? await updateUserModel(editingModelId.value, payload)
      : await createUserModel(payload);
    const index = models.value.findIndex(model => model.id === saved.id);
    if (index >= 0) {
      models.value[index] = saved;
    } else {
      models.value.push(saved);
    }
    if (saved.is_default_chat || saved.is_default_embedding) {
      await loadBundle();
    }
    editingModelId.value = saved.id;
    setFeedback('success', '模型已保存。');
    emit('saved');
  } catch (error) {
    const message = error instanceof Error ? error.message : '未知错误';
    setFeedback('error', `模型保存失败：${message}`);
  } finally {
    isSavingModel.value = false;
  }
};

const saveRoutes = async () => {
  const routes = Object.entries(routeSelections)
    .filter(([, modelId]) => modelId)
    .map(([stage, modelId]) => ({ stage, model_id: Number(modelId) }));

  isSavingRoutes.value = true;
  try {
    const savedRoutes = await saveStageRoutes({ routes });
    for (const key of allStageKeys.value) {
      routeSelections[key] = '';
    }
    for (const route of savedRoutes) {
      routeSelections[route.stage] = String(route.model_id);
    }
    setFeedback('success', '阶段路由已保存。');
    emit('saved');
  } catch (error) {
    const message = error instanceof Error ? error.message : '未知错误';
    setFeedback('error', `阶段路由保存失败：${message}`);
  } finally {
    isSavingRoutes.value = false;
  }
};

const providerName = (providerId: number): string => (
  providers.value.find(provider => provider.id === providerId)?.name || `供应商 ${providerId}`
);

const modelsForCapability = (capability: Capability): UserAIModel[] => (
  models.value.filter(model => model.is_enabled && Boolean(model.capabilities[capability]))
);

onMounted(() => {
  void loadBundle();
});
</script>

<style scoped>
.model-routing {
  display: grid;
  gap: var(--md-spacing-4);
  margin-bottom: var(--md-spacing-5);
}

.model-routing__header,
.model-routing__panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--md-spacing-3);
}

.model-routing__title,
.model-routing__panel-head h4,
.model-routing__stage-group h5 {
  margin: 0;
  color: var(--md-on-surface);
}

.model-routing__subtitle {
  margin: var(--md-spacing-1) 0 0;
  color: var(--md-on-surface-variant);
}

.model-routing__panel {
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-lg);
  padding: var(--md-spacing-4);
  background: var(--md-surface-container-low);
}

.model-routing__list,
.model-routing__form,
.model-routing__stage-list,
.model-routing__stage-groups {
  display: grid;
  gap: var(--md-spacing-3);
}

.model-routing__list {
  margin: var(--md-spacing-3) 0;
}

.model-routing__item {
  width: 100%;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-md);
  background: var(--md-surface);
  color: var(--md-on-surface);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--md-spacing-3);
  padding: var(--md-spacing-3);
  text-align: left;
  cursor: pointer;
}

.model-routing__item.active,
.model-routing__item:hover {
  border-color: var(--md-primary);
  background: var(--md-primary-container);
  color: var(--md-on-primary-container);
}

.model-routing__item strong,
.model-routing__stage-row strong {
  display: block;
  font-size: var(--md-body-medium);
}

.model-routing__item small,
.model-routing__stage-row small {
  display: block;
  margin-top: 2px;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.model-routing__status,
.model-routing__badges em {
  border-radius: var(--md-radius-full);
  padding: 4px 8px;
  font-size: var(--md-label-small);
  font-style: normal;
  white-space: nowrap;
}

.model-routing__status.is-on,
.model-routing__badges em {
  background: var(--md-success-container);
  color: var(--md-on-success-container);
}

.model-routing__status.is-off {
  background: var(--md-error-container);
  color: var(--md-on-error-container);
}

.model-routing__badges {
  display: inline-flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--md-spacing-1);
}

.model-routing__check,
.model-routing__checks {
  display: flex;
  align-items: center;
  gap: var(--md-spacing-2);
  color: var(--md-on-surface);
  font-size: var(--md-body-medium);
}

.model-routing__checks {
  flex-wrap: wrap;
}

.model-routing__check input {
  width: 16px;
  height: 16px;
}

.model-routing__link {
  border: none;
  background: transparent;
  color: var(--md-primary);
  cursor: pointer;
  font-weight: 600;
  padding: 0;
}

.model-routing__empty {
  margin: 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.model-routing__stages {
  overflow: hidden;
}

.model-routing__stage-groups {
  margin-top: var(--md-spacing-4);
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

.model-routing__feedback.is-error {
  background-color: var(--md-error-container);
  color: var(--md-on-error-container);
}

@media (min-width: 960px) {
  .model-routing__stage-row {
    grid-template-columns: minmax(220px, 0.8fr) minmax(240px, 1fr);
  }
}
</style>
