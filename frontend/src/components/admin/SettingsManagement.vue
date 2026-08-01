<!-- AIMETA P=设置管理_系统设置界面|R=系统配置表单|NR=不含用户设置|E=component:SettingsManagement|X=ui|A=设置组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <section class="admin-panel admin-settings">
    <div class="admin-panel__body">
      <div class="admin-ops">
        <div class="admin-ops__summary">
          <div class="admin-ops__copy">
            <h2>系统配置中心</h2>
            <p>常用配置通过快捷卡片维护，复杂键值在表格中检索和编辑，避免误改关键项。</p>
          </div>
          <n-space class="admin-ops__toolbar" :size="8">
            <n-tag type="success" :bordered="false">配置总数 {{ configs.length }}</n-tag>
            <n-tag type="warning" :bordered="false">托管项 {{ managedConfigs.length }}</n-tag>
            <n-tag :bordered="false">普通项 {{ customConfigsCount }}</n-tag>
          </n-space>
        </div>

        <div class="admin-ops__metrics">
          <article class="admin-ops__metric">
            <p>配置总数</p>
            <strong>{{ configs.length }}</strong>
            <span>当前系统键值项</span>
          </article>
          <article class="admin-ops__metric">
            <p>托管配置</p>
            <strong>{{ managedConfigs.length }}</strong>
            <span>建议通过快捷卡片维护</span>
          </article>
          <article class="admin-ops__metric">
            <p>普通配置</p>
            <strong>{{ customConfigsCount }}</strong>
            <span>可在表格中编辑</span>
          </article>
          <article class="admin-ops__metric">
            <p>版本状态</p>
            <strong>{{ versionSyncText }}</strong>
            <span>远程版本检查结果</span>
          </article>
        </div>

        <div class="admin-ops__grid">
          <article class="admin-panel-card admin-panel-card--wide">
            <header>
              <div>
                <h3>配置健康状态</h3>
                <p>快速确认关键配置是否处于可用状态。</p>
              </div>
            </header>
            <div class="health-grid settings-health-grid">
              <div class="health-item">
                <div class="health-label">章节候选版本数</div>
                <div class="health-value">{{ chapterVersionCount }}</div>
                <n-tag :type="chapterVersionHealthy ? 'success' : 'error'" :bordered="false">
                  {{ chapterVersionHealthy ? '有效' : '异常' }}
                </n-tag>
              </div>
              <div class="health-item">
                <div class="health-label">章节目标字数</div>
                <div class="health-value">{{ chapterWordLimit }}</div>
                <n-tag :type="chapterWordLimitHealthy ? 'success' : 'error'" :bordered="false">
                  {{ chapterWordLimitHealthy ? '有效' : '过低' }}
                </n-tag>
              </div>
              <div class="health-item">
                <div class="health-label">版本信息源地址</div>
                <div
                  class="health-value health-value-url"
                  :title="normalizedVersionInfoUrl || '未配置'"
                >
                  {{ normalizedVersionInfoUrl || '未配置' }}
                </div>
                <n-tag :type="versionSourceHealthy ? 'success' : 'warning'" :bordered="false">
                  {{ versionSourceHealthy ? '可解析 URL' : '待配置' }}
                </n-tag>
              </div>
              <div class="health-item">
                <div class="health-label">远程版本状态</div>
                <div class="health-value">{{ remoteVersion || '未检测' }}</div>
                <n-tag :type="versionSyncTagType" :bordered="false">
                  {{ versionSyncText }}
                </n-tag>
              </div>
            </div>
          </article>
        </div>

        <div class="top-settings-grid">
          <n-card :bordered="false" class="top-settings-card">
            <template #header>
              <div class="card-header">
                <div>
                  <span class="card-title">章节生成版本数</span>
                  <p class="card-subtitle">控制每章候选草稿数量，影响生成时长与候选对比空间。</p>
                </div>
                <n-tag :bordered="false" type="info">托管项</n-tag>
              </div>
            </template>
            <n-spin :show="configLoading || chapterVersionSaving">
              <n-alert
                v-if="chapterVersionError"
                type="error"
                closable
                @close="chapterVersionError = null"
              >
                {{ chapterVersionError }}
              </n-alert>
              <n-form label-placement="top" class="version-form">
                <n-form-item label="每章生成候选版本数量（仅支持 1 或 2）">
                  <n-input-number
                    v-model:value="chapterVersionCount"
                    :min="1"
                    :max="2"
                    :step="1"
                    :precision="0"
                    placeholder="请输入 1 或 2"
                  />
                </n-form-item>
                <div class="form-hint">
                  优先级：系统配置 <code>writer.chapter_versions</code> &gt; 环境变量
                  <code>WRITER_CHAPTER_VERSION_COUNT</code>
                </div>
                <n-space justify="end">
                  <n-button
                    type="primary"
                    :loading="chapterVersionSaving"
                    @click="saveChapterVersionCount"
                  >
                    保存设置
                  </n-button>
                </n-space>
              </n-form>
            </n-spin>
          </n-card>

          <n-card :bordered="false" class="top-settings-card">
            <template #header>
              <div class="card-header">
                <div>
                  <span class="card-title">章节字数限制</span>
                  <p class="card-subtitle">控制当前章节生成提示里的目标字数，影响正文篇幅。</p>
                </div>
                <n-tag :bordered="false" type="info">托管项</n-tag>
              </div>
            </template>
            <n-spin :show="configLoading || chapterWordLimitSaving">
              <n-alert
                v-if="chapterWordLimitError"
                type="error"
                closable
                @close="chapterWordLimitError = null"
              >
                {{ chapterWordLimitError }}
              </n-alert>
              <n-form label-placement="top" class="version-form">
                <n-form-item label="每章目标字数（建议不低于 2200）">
                  <n-input-number
                    v-model:value="chapterWordLimit"
                    :min="2200"
                    :step="100"
                    :precision="0"
                    placeholder="请输入目标字数"
                  />
                </n-form-item>
                <div class="form-hint">
                  优先级：系统配置 <code>writer.chapter_word_limit</code> &gt; 环境变量
                  <code>WRITER_CHAPTER_WORD_LIMIT</code>
                </div>
                <n-space justify="end">
                  <n-button
                    type="primary"
                    :loading="chapterWordLimitSaving"
                    @click="saveChapterWordLimit"
                  >
                    保存设置
                  </n-button>
                </n-space>
              </n-form>
            </n-spin>
          </n-card>

          <n-card :bordered="false" class="top-settings-card">
            <template #header>
              <div class="card-header">
                <div>
                  <span class="card-title">版本检查源</span>
                  <p class="card-subtitle">配置远程版本 JSON，支持一键检测本地与远程版本差异。</p>
                </div>
                <n-tag :bordered="false" type="info">托管项</n-tag>
              </div>
            </template>
            <n-spin :show="configLoading || versionSourceSaving">
              <n-alert
                v-if="versionSourceError"
                type="error"
                closable
                @close="versionSourceError = null"
              >
                {{ versionSourceError }}
              </n-alert>
              <n-form label-placement="top" class="version-form">
                <n-form-item label="版本信息 JSON 地址（必填）">
                  <n-input
                    v-model:value="versionInfoUrl"
                    placeholder="https://raw.githubusercontent.com/.../version-info.json"
                  />
                </n-form-item>
                <div class="form-hint">
                  优先级：系统配置 <code>updates.version_info_url</code> &gt; 环境变量
                  <code>VERSION_INFO_URL</code>
                </div>
                <div class="version-compare-panel">
                  <div class="compare-row">
                    <span>本地版本：</span>
                    <code>{{ localVersion }}</code>
                  </div>
                  <div class="compare-row">
                    <span>远程版本：</span>
                    <code v-if="remoteVersion">{{ remoteVersion }}</code>
                    <span v-else class="compare-empty">
                      {{ versionCheckLoading ? '正在解析 JSON...' : '未解析到版本号' }}
                    </span>
                  </div>
                  <div v-if="remoteVersionSource" class="compare-meta">
                    来源：<code>{{ remoteVersionSource }}</code>
                  </div>
                  <div v-if="remoteBuildTimeBeijing" class="compare-meta">
                    构建时间：{{ remoteBuildTimeBeijing }}
                  </div>
                  <div v-if="versionCheckError" class="compare-result compare-error">
                    {{ versionCheckError }}
                  </div>
                  <div
                    v-else-if="remoteVersion"
                    :class="['compare-result', hasNewVersion ? 'compare-new' : 'compare-same']"
                  >
                    {{ hasNewVersion ? '检测到版本差异，可能有新版本可用' : '远程与本地版本一致' }}
                  </div>
                </div>
                <n-space justify="end">
                  <n-button :loading="versionCheckLoading" @click="handleCheckVersionSource">
                    检查版本
                  </n-button>
                  <n-button
                    type="primary"
                    :loading="versionSourceSaving"
                    @click="saveVersionSources"
                  >
                    保存地址
                  </n-button>
                </n-space>
              </n-form>
            </n-spin>
          </n-card>
        </div>

        <section class="admin-panel settings-table-panel" aria-labelledby="system-config-title">
          <div class="admin-panel__header">
            <div>
              <h3 id="system-config-title" class="admin-panel__title">系统配置</h3>
              <p class="admin-panel__subtitle">支持按 Key、值、描述检索；托管项已在表格中高亮。</p>
            </div>
            <n-button type="primary" size="small" @click="openCreateModal"> 新增配置 </n-button>
          </div>

          <div class="admin-panel__body">
            <n-spin :show="configLoading">
              <n-alert v-if="configError" type="error" closable @close="configError = null">
                {{ configError }}
              </n-alert>
              <n-alert type="warning" class="risk-alert">
                删除配置会立即影响系统行为。托管项建议通过上方快捷卡片调整，不建议在表格中直接删除。
              </n-alert>

              <div class="table-toolbar">
                <n-input
                  v-model:value="configKeyword"
                  clearable
                  class="toolbar-search"
                  placeholder="搜索 Key / 值 / 描述"
                />
                <n-switch v-model:value="managedOnly">
                  <template #checked>仅托管项</template>
                  <template #unchecked>仅托管项</template>
                </n-switch>
                <n-switch v-model:value="managedFirst">
                  <template #checked>托管优先排序</template>
                  <template #unchecked>托管优先排序</template>
                </n-switch>
              </div>

              <n-empty
                v-if="!configLoading && !filteredConfigs.length"
                :description="configKeyword || managedOnly ? '没有匹配的配置项' : '暂无配置项'"
              />

              <div v-else-if="isMobile" class="settings-config-mobile-list" role="list">
                <article
                  v-for="config in filteredConfigs"
                  :key="config.key"
                  class="settings-config-mobile-card"
                  :class="{ 'is-managed': isManagedConfigKey(config.key) }"
                  role="listitem"
                >
                  <div class="settings-config-mobile-card__head">
                    <code class="key-code">{{ config.key }}</code>
                    <n-tag
                      v-if="isManagedConfigKey(config.key)"
                      type="info"
                      size="small"
                      :bordered="false"
                    >
                      托管
                    </n-tag>
                    <n-tag v-else size="small" :bordered="false">
                      {{ getConfigDomain(config.key) }}
                    </n-tag>
                  </div>
                  <dl class="settings-config-mobile-card__meta">
                    <div>
                      <dt>值</dt>
                      <dd :title="config.value">{{ config.value || '—' }}</dd>
                    </div>
                    <div>
                      <dt>描述</dt>
                      <dd>{{ config.description || '—' }}</dd>
                    </div>
                  </dl>
                  <div class="settings-config-mobile-card__actions">
                    <n-button size="small" type="primary" tertiary @click="openEditModal(config)">
                      编辑
                    </n-button>
                    <n-popconfirm
                      positive-text="删除"
                      negative-text="取消"
                      type="error"
                      placement="left"
                      @positive-click="deleteConfig(config.key)"
                    >
                      <template #default>
                        {{
                          isManagedConfigKey(config.key)
                            ? '该项属于托管配置，建议优先使用上方快捷设置。确认删除？'
                            : '确认删除该配置项？'
                        }}
                      </template>
                      <template #trigger>
                        <n-button size="small" type="error" quaternary> 删除 </n-button>
                      </template>
                    </n-popconfirm>
                  </div>
                </article>
              </div>

              <div v-else class="settings-table-shell">
                <MofengTable
                  :columns="columns"
                  :data="filteredConfigs"
                  :loading="configLoading"
                  :row-key="rowKey"
                  :row-class-name="tableRowClassName"
                  class="config-table"
                />
              </div>
            </n-spin>
          </div>
        </section>
      </div>
    </div>
  </section>

  <n-modal
    v-model:show="configModalVisible"
    preset="card"
    :title="modalTitle"
    class="config-modal"
    :style="{ width: '520px', maxWidth: '92vw' }"
  >
    <n-form label-placement="top" :model="configForm">
      <n-form-item label="Key">
        <n-input
          v-model:value="configForm.key"
          :disabled="!isCreateMode"
          placeholder="请输入唯一 Key"
        />
      </n-form-item>
      <n-form-item label="值">
        <n-input v-model:value="configForm.value" placeholder="配置的具体值" />
      </n-form-item>
      <n-form-item label="描述">
        <n-input v-model:value="configForm.description" placeholder="配置项的用途说明，可选" />
      </n-form-item>
    </n-form>
    <template #footer>
      <n-space justify="end">
        <n-button quaternary @click="closeConfigModal">取消</n-button>
        <n-button type="primary" :loading="configSaving" @click="submitConfig"> 保存 </n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref, watch } from 'vue'
import { NAlert } from 'naive-ui/es/alert'
import { NButton } from 'naive-ui/es/button'
import { NCard } from 'naive-ui/es/card'
import MofengTable from '@/components/shared/MofengTable.vue'
import { NEmpty } from 'naive-ui/es/empty'
import { NForm, NFormItem } from 'naive-ui/es/form'
import { NInput } from 'naive-ui/es/input'
import { NInputNumber } from 'naive-ui/es/input-number'
import { NModal } from 'naive-ui/es/modal'
import { NPopconfirm } from 'naive-ui/es/popconfirm'
import { NSpace } from 'naive-ui/es/space'
import { NSpin } from 'naive-ui/es/spin'
import { NSwitch } from 'naive-ui/es/switch'
import { NTag } from 'naive-ui/es/tag'
import type { DataTableColumns } from 'naive-ui'

import type {
  SystemConfig,
  SystemConfigUpdatePayload,
  SystemConfigUpsertPayload,
} from '@/api/admin'
import { normalizeComparableVersion } from '@/utils/version'
import { useAlert } from '@/composables/useAlert'
import { useResponsiveViewport } from '@/composables/useResponsiveViewport'
import { mobileMax } from '@/constants/responsive'
import {
  useDeleteSystemConfigMutation,
  usePatchSystemConfigMutation,
  useRemoteVersionQuery,
  useSystemConfigsQuery,
  useUpsertSystemConfigMutation,
} from '@/queries/admin'

const { showAlert } = useAlert()
const configsQuery = useSystemConfigsQuery()
const upsertSystemConfigMutation = useUpsertSystemConfigMutation()
const patchSystemConfigMutation = usePatchSystemConfigMutation()
const deleteSystemConfigMutation = useDeleteSystemConfigMutation()
const remoteVersionQuery = useRemoteVersionQuery(false)

const WRITER_VERSION_CONFIG_KEY = 'writer.chapter_versions'
const LEGACY_WRITER_VERSION_CONFIG_KEY = 'writer.version_count'
const WRITER_WORD_LIMIT_CONFIG_KEY = 'writer.chapter_word_limit'
const VERSION_INFO_URL_CONFIG_KEY = 'updates.version_info_url'
const LEGACY_VERSION_INFO_URL_CONFIG_KEY = 'updates.github_json_url'
const MIN_CHAPTER_VERSION_COUNT = 1
const MAX_CHAPTER_VERSION_COUNT = 2
const MIN_CHAPTER_WORD_LIMIT = 2200
const DEFAULT_CHAPTER_WORD_LIMIT = 3000
const MANAGED_CONFIG_KEYS = new Set<string>([
  WRITER_VERSION_CONFIG_KEY,
  LEGACY_WRITER_VERSION_CONFIG_KEY,
  WRITER_WORD_LIMIT_CONFIG_KEY,
  VERSION_INFO_URL_CONFIG_KEY,
  LEGACY_VERSION_INFO_URL_CONFIG_KEY,
])

const chapterVersionCount = ref<number>(MIN_CHAPTER_VERSION_COUNT)
const chapterVersionSaving = ref(false)
const chapterVersionError = ref<string | null>(null)
const chapterWordLimit = ref<number>(DEFAULT_CHAPTER_WORD_LIMIT)
const chapterWordLimitSaving = ref(false)
const chapterWordLimitError = ref<string | null>(null)
const versionInfoUrl = ref('')
const versionSourceSaving = ref(false)
const versionSourceError = ref<string | null>(null)
const localVersion = (import.meta.env.VITE_APP_VERSION as string | undefined)?.trim() || 'dev'
const remoteVersion = ref<string | null>(null)
const remoteVersionSource = ref<string | null>(null)
const remoteBuildTimeBeijing = ref<string | null>(null)
const versionCheckLoading = ref(false)
const versionCheckError = ref<string | null>(null)

const configs = computed<SystemConfig[]>(() => configsQuery.data.value ?? [])
const configLoading = computed(() => configsQuery.isLoading.value || configsQuery.isFetching.value)
const configSaving = computed(
  () => upsertSystemConfigMutation.isPending.value || patchSystemConfigMutation.isPending.value,
)
const isConfigErrorDismissed = ref(false)
const configError = computed({
  get: () => {
    if (isConfigErrorDismissed.value) return null
    const queryError = configsQuery.error.value
    return queryError instanceof Error ? queryError.message : queryError ? String(queryError) : null
  },
  set: () => {
    isConfigErrorDismissed.value = true
  },
})

const configModalVisible = ref(false)
const isCreateMode = ref(true)
const configKeyword = ref('')
const managedOnly = ref(false)
const managedFirst = ref(true)
const viewport = useResponsiveViewport()
const configForm = reactive<SystemConfig>({
  key: '',
  value: '',
  description: '',
})

const rowKey = (row: SystemConfig) => row.key

const modalTitle = computed(() => (isCreateMode.value ? '新增配置项' : '编辑配置项'))
const isMobile = computed(() => viewport.width.value <= mobileMax)
const managedConfigs = computed(() => configs.value.filter((item) => isManagedConfigKey(item.key)))
const customConfigsCount = computed(() =>
  Math.max(0, configs.value.length - managedConfigs.value.length),
)
const normalizedVersionInfoUrl = computed(() => normalizeConfigText(versionInfoUrl.value))
const chapterVersionHealthy = computed(
  () =>
    chapterVersionCount.value >= MIN_CHAPTER_VERSION_COUNT &&
    chapterVersionCount.value <= MAX_CHAPTER_VERSION_COUNT,
)
const chapterWordLimitHealthy = computed(() => chapterWordLimit.value >= MIN_CHAPTER_WORD_LIMIT)
const versionSourceHealthy = computed(
  () => normalizedVersionInfoUrl.value.length > 0 && isHttpUrl(normalizedVersionInfoUrl.value),
)
const versionSyncTagType = computed<'default' | 'warning' | 'success' | 'error'>(() => {
  if (versionCheckLoading.value) {
    return 'default'
  }
  if (versionCheckError.value) {
    return 'error'
  }
  if (!remoteVersion.value) {
    return 'warning'
  }
  return hasNewVersion.value ? 'warning' : 'success'
})
const versionSyncText = computed(() => {
  if (versionCheckLoading.value) {
    return '检测中'
  }
  if (versionCheckError.value) {
    return '检测失败'
  }
  if (!remoteVersion.value) {
    return '未解析'
  }
  return hasNewVersion.value ? '存在差异' : '与本地一致'
})
const filteredConfigs = computed(() => {
  const keyword = normalizeConfigText(configKeyword.value).toLowerCase()
  return configs.value
    .filter((item) => {
      if (managedOnly.value && !isManagedConfigKey(item.key)) {
        return false
      }
      if (!keyword) {
        return true
      }
      const key = item.key.toLowerCase()
      const value = normalizeConfigText(item.value).toLowerCase()
      const description = normalizeConfigText(item.description).toLowerCase()
      return key.includes(keyword) || value.includes(keyword) || description.includes(keyword)
    })
    .sort((a, b) => {
      if (managedFirst.value && isManagedConfigKey(a.key) !== isManagedConfigKey(b.key)) {
        return isManagedConfigKey(a.key) ? -1 : 1
      }
      return a.key.localeCompare(b.key)
    })
})
const hasNewVersion = computed(() => {
  if (!remoteVersion.value) {
    return false
  }
  return (
    normalizeComparableVersion(remoteVersion.value) !== normalizeComparableVersion(localVersion)
  )
})

const normalizeChapterVersionCount = (value: unknown): number => {
  const parsed = Number.parseInt(String(value ?? '').trim(), 10)
  if (!Number.isFinite(parsed)) {
    return MIN_CHAPTER_VERSION_COUNT
  }
  return Math.max(MIN_CHAPTER_VERSION_COUNT, Math.min(MAX_CHAPTER_VERSION_COUNT, parsed))
}

const normalizeChapterWordLimit = (value: unknown): number => {
  const parsed = Number.parseInt(String(value ?? '').trim(), 10)
  if (!Number.isFinite(parsed)) {
    return DEFAULT_CHAPTER_WORD_LIMIT
  }
  return Math.max(MIN_CHAPTER_WORD_LIMIT, parsed)
}

const normalizeConfigText = (value: unknown): string => String(value ?? '').trim()
const isManagedConfigKey = (key: string): boolean => MANAGED_CONFIG_KEYS.has(key)
const getConfigDomain = (key: string): string => {
  const domain = normalizeConfigText(key).split('.')[0]
  return domain || 'general'
}

const isHttpUrl = (value: string): boolean => {
  try {
    const parsed = new URL(value)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:'
  } catch {
    return false
  }
}

interface RemoteVersionResponse {
  version?: string | null
  source?: string | null
  errors?: string[]
  build_time_beijing?: string | null
}

const resetVersionCheckResult = () => {
  remoteVersion.value = null
  remoteVersionSource.value = null
  remoteBuildTimeBeijing.value = null
  versionCheckError.value = null
}

const checkVersionSource = async (options: { silentIfInvalid?: boolean } = {}) => {
  const { silentIfInvalid = false } = options
  const normalizedVersionInfoUrl = normalizeConfigText(versionInfoUrl.value)
  resetVersionCheckResult()

  if (!normalizedVersionInfoUrl) {
    if (!silentIfInvalid) {
      versionCheckError.value = '请先填写版本信息 JSON 地址'
    }
    return
  }

  if (!isHttpUrl(normalizedVersionInfoUrl)) {
    if (!silentIfInvalid) {
      versionCheckError.value = '版本信息 JSON 地址必须是 http/https URL'
    }
    return
  }

  versionCheckLoading.value = true
  try {
    const result = await remoteVersionQuery.refetch()
    if (result.error) {
      throw result.error
    }
    const payload = (result.data ?? {}) as RemoteVersionResponse
    const parsedVersion =
      typeof payload?.version === 'string' ? normalizeConfigText(payload.version) : ''
    remoteVersion.value = parsedVersion || null
    remoteVersionSource.value =
      typeof payload?.source === 'string' ? normalizeConfigText(payload.source) || null : null
    remoteBuildTimeBeijing.value =
      typeof payload?.build_time_beijing === 'string'
        ? normalizeConfigText(payload.build_time_beijing) || null
        : null

    if (!remoteVersion.value) {
      const errors = Array.isArray(payload?.errors)
        ? payload.errors.filter(
            (item): item is string => typeof item === 'string' && item.trim().length > 0,
          )
        : []
      versionCheckError.value =
        errors.length > 0
          ? `已请求版本源，但未解析到版本号：${errors.join('；')}`
          : '已请求版本源，但未解析到版本号'
    }
  } catch (err) {
    versionCheckError.value = err instanceof Error ? `版本解析失败：${err.message}` : '版本解析失败'
  } finally {
    versionCheckLoading.value = false
  }
}

const handleCheckVersionSource = () => {
  void checkVersionSource()
}

const syncChapterVersionCountFromConfigs = () => {
  const current = configs.value.find((item) => item.key === WRITER_VERSION_CONFIG_KEY)
  const legacy = configs.value.find((item) => item.key === LEGACY_WRITER_VERSION_CONFIG_KEY)
  const rawValue = current?.value ?? legacy?.value ?? String(MIN_CHAPTER_VERSION_COUNT)
  chapterVersionCount.value = normalizeChapterVersionCount(rawValue)
}

const syncChapterWordLimitFromConfigs = () => {
  const current = configs.value.find((item) => item.key === WRITER_WORD_LIMIT_CONFIG_KEY)
  const rawValue = current?.value ?? String(DEFAULT_CHAPTER_WORD_LIMIT)
  chapterWordLimit.value = normalizeChapterWordLimit(rawValue)
}

const syncVersionSourceFromConfigs = () => {
  const versionInfoConfig =
    configs.value.find((item) => item.key === VERSION_INFO_URL_CONFIG_KEY) ||
    configs.value.find((item) => item.key === LEGACY_VERSION_INFO_URL_CONFIG_KEY)
  versionInfoUrl.value = normalizeConfigText(versionInfoConfig?.value)
}

const syncDerivedFormsFromConfigs = () => {
  syncChapterVersionCountFromConfigs()
  syncChapterWordLimitFromConfigs()
  syncVersionSourceFromConfigs()
}

const fetchConfigs = async () => {
  await configsQuery.refetch()
}

const saveChapterVersionCount = async () => {
  chapterVersionError.value = null
  chapterVersionSaving.value = true
  try {
    const normalized = normalizeChapterVersionCount(chapterVersionCount.value)
    chapterVersionCount.value = normalized
    await upsertSystemConfigMutation.mutateAsync({
      key: WRITER_VERSION_CONFIG_KEY,
      data: {
        value: String(normalized),
        description: '每次生成章节的候选版本数量（支持 1~2）。',
      },
    })
    await fetchConfigs()
    syncDerivedFormsFromConfigs()
    showAlert('章节生成版本数已更新', 'success')
  } catch (err) {
    chapterVersionError.value = err instanceof Error ? err.message : '保存章节版本数失败'
    showAlert(chapterVersionError.value, 'error')
  } finally {
    chapterVersionSaving.value = false
  }
}

const saveChapterWordLimit = async () => {
  chapterWordLimitError.value = null
  chapterWordLimitSaving.value = true
  try {
    const normalized = normalizeChapterWordLimit(chapterWordLimit.value)
    chapterWordLimit.value = normalized
    await upsertSystemConfigMutation.mutateAsync({
      key: WRITER_WORD_LIMIT_CONFIG_KEY,
      data: {
        value: String(normalized),
        description: '章节正文生成目标字数，建议不低于 2200。',
      },
    })
    await fetchConfigs()
    syncDerivedFormsFromConfigs()
    showAlert('章节字数限制已更新', 'success')
  } catch (err) {
    chapterWordLimitError.value = err instanceof Error ? err.message : '保存章节字数限制失败'
    showAlert(chapterWordLimitError.value, 'error')
  } finally {
    chapterWordLimitSaving.value = false
  }
}

const saveVersionSources = async () => {
  versionSourceError.value = null
  const normalizedVersionInfoUrl = normalizeConfigText(versionInfoUrl.value)

  if (!normalizedVersionInfoUrl) {
    versionSourceError.value = '版本信息 JSON 地址不能为空'
    showAlert(versionSourceError.value, 'error')
    return
  }

  if (!isHttpUrl(normalizedVersionInfoUrl)) {
    versionSourceError.value = '版本信息 JSON 地址必须是 http/https URL'
    showAlert(versionSourceError.value, 'error')
    return
  }

  versionSourceSaving.value = true
  try {
    const infoConfigPayload: SystemConfigUpsertPayload = {
      value: normalizedVersionInfoUrl,
      description: '远程版本信息 JSON 地址，供 /api/updates/remote-version 优先读取。',
    }
    await upsertSystemConfigMutation.mutateAsync({
      key: VERSION_INFO_URL_CONFIG_KEY,
      data: infoConfigPayload,
    })

    await fetchConfigs()
    syncVersionSourceFromConfigs()
    await checkVersionSource()
    if (remoteVersion.value) {
      const compareText = hasNewVersion.value
        ? `检测到远程版本 ${remoteVersion.value}，与本地 ${localVersion} 不一致`
        : `远程版本 ${remoteVersion.value} 与本地一致`
      showAlert(`版本检查地址已保存。${compareText}`, 'success')
    } else {
      showAlert('版本检查地址已保存，但未解析到远程版本号', 'info')
    }
  } catch (err) {
    versionSourceError.value = err instanceof Error ? err.message : '保存版本地址失败'
    showAlert(versionSourceError.value, 'error')
  } finally {
    versionSourceSaving.value = false
  }
}

const openCreateModal = () => {
  isCreateMode.value = true
  configForm.key = ''
  configForm.value = ''
  configForm.description = ''
  configModalVisible.value = true
}

const openEditModal = (config: SystemConfig) => {
  isCreateMode.value = false
  configForm.key = config.key
  configForm.value = config.value
  configForm.description = config.description || ''
  configModalVisible.value = true
}

const closeConfigModal = () => {
  configModalVisible.value = false
}

const submitConfig = async () => {
  const normalizedKey = configForm.key.trim()
  const normalizedValue = configForm.value.trim()

  if (!normalizedKey || !normalizedValue) {
    showAlert('Key 与 Value 均为必填项', 'error')
    return
  }

  if (
    normalizedKey === WRITER_VERSION_CONFIG_KEY ||
    normalizedKey === LEGACY_WRITER_VERSION_CONFIG_KEY
  ) {
    const parsed = Number.parseInt(normalizedValue, 10)
    if (
      !Number.isFinite(parsed) ||
      parsed < MIN_CHAPTER_VERSION_COUNT ||
      parsed > MAX_CHAPTER_VERSION_COUNT
    ) {
      showAlert('章节版本数仅支持设置为 1 或 2', 'error')
      return
    }
  }

  if (normalizedKey === WRITER_WORD_LIMIT_CONFIG_KEY) {
    const parsed = Number.parseInt(normalizedValue, 10)
    if (!Number.isFinite(parsed) || parsed < MIN_CHAPTER_WORD_LIMIT) {
      showAlert('章节字数限制不能低于 2200', 'error')
      return
    }
  }

  if (
    normalizedKey === VERSION_INFO_URL_CONFIG_KEY ||
    normalizedKey === LEGACY_VERSION_INFO_URL_CONFIG_KEY
  ) {
    if (!isHttpUrl(normalizedValue)) {
      showAlert('版本地址必须是 http/https URL', 'error')
      return
    }
  }

  try {
    if (isCreateMode.value) {
      await upsertSystemConfigMutation.mutateAsync({
        key: normalizedKey,
        data: {
          value: normalizedValue,
          description: configForm.description || undefined,
        },
      })
    } else {
      await patchSystemConfigMutation.mutateAsync({
        key: configForm.key,
        data: {
          value: normalizedValue,
          description: configForm.description || undefined,
        } as SystemConfigUpdatePayload,
      })
    }
    await fetchConfigs()
    syncDerivedFormsFromConfigs()
    void checkVersionSource({ silentIfInvalid: true })
    showAlert('配置已保存', 'success')
    closeConfigModal()
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '保存失败', 'error')
  }
}

const deleteConfig = async (key: string) => {
  try {
    await deleteSystemConfigMutation.mutateAsync(key)
    await fetchConfigs()
    syncDerivedFormsFromConfigs()
    void checkVersionSource({ silentIfInvalid: true })
    showAlert('配置已删除', 'success')
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '删除失败', 'error')
  }
}

const tableRowClassName = (row: SystemConfig) => (isManagedConfigKey(row.key) ? 'row-managed' : '')

const columns: DataTableColumns<SystemConfig> = [
  {
    title: 'Key',
    key: 'key',
    width: 320,
    render(row) {
      return h(
        NSpace,
        { align: 'center', size: 6, wrap: true },
        {
          default: () => [
            h('code', { class: 'key-code' }, row.key),
            isManagedConfigKey(row.key)
              ? h(NTag, { type: 'info', size: 'small', bordered: false }, { default: () => '托管' })
              : h(
                  NTag,
                  { size: 'small', bordered: false },
                  { default: () => getConfigDomain(row.key) },
                ),
          ],
        },
      )
    },
  },
  {
    title: '值',
    key: 'value',
    render(row) {
      return h(
        'span',
        {
          class: 'value-text',
          title: row.value,
        },
        row.value,
      )
    },
  },
  {
    title: '描述',
    key: 'description',
    ellipsis: { tooltip: true },
    render(row) {
      return row.description || '—'
    },
  },
  {
    title: '操作',
    key: 'actions',
    align: 'center',
    width: 160,
    render(row) {
      return h(
        NSpace,
        { justify: 'center', size: 'small' },
        {
          default: () => [
            h(
              NButton,
              {
                size: 'small',
                type: 'primary',
                tertiary: true,
                onClick: () => openEditModal(row),
              },
              { default: () => '编辑' },
            ),
            h(
              NPopconfirm,
              {
                'positive-text': '删除',
                'negative-text': '取消',
                type: 'error',
                placement: 'left',
                onPositiveClick: () => deleteConfig(row.key),
              },
              {
                default: () =>
                  isManagedConfigKey(row.key)
                    ? '该项属于托管配置，建议优先使用上方快捷设置。确认删除？'
                    : '确认删除该配置项？',
                trigger: () =>
                  h(
                    NButton,
                    { size: 'small', type: 'error', quaternary: true },
                    { default: () => '删除' },
                  ),
              },
            ),
          ],
        },
      )
    },
  },
]

watch(
  () => configsQuery.error.value,
  () => {
    isConfigErrorDismissed.value = false
  },
)

watch(
  configs,
  (nextConfigs, previousConfigs) => {
    syncDerivedFormsFromConfigs()
    if (nextConfigs.length && nextConfigs !== previousConfigs) {
      void checkVersionSource({ silentIfInvalid: true })
    }
  },
  { immediate: true },
)

onMounted(() => {
  fetchConfigs()
})
</script>

<style scoped>
.admin-settings {
  width: 100%;
}

.health-grid {
  display: grid;
  gap: 10px;
  min-width: 0;
}

.health-item {
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-sm);
  padding: 10px 12px;
  background-color: var(--md-surface);
  min-width: 0;
  overflow: hidden;
}

.health-label {
  color: var(--md-on-surface-variant);
  font-size: 0.825rem;
}

.health-value {
  margin: 4px 0 8px;
  color: var(--md-on-surface);
  font-size: 0.925rem;
  font-weight: 600;
  min-width: 0;
}

.health-value-url {
  display: block;
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.settings-health-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-top: var(--md-spacing-4);
}

.top-settings-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.top-settings-card {
  height: 100%;
  background-color: var(--md-surface-container);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-lg);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.card-title {
  font-family: var(--md-font-serif);
  font-size: 1.25rem;
  font-weight: 600;
  letter-spacing: 0.03em;
  color: var(--md-on-surface);
}

.card-subtitle {
  margin: 6px 0 0;
  color: var(--md-on-surface-variant);
  font-size: 0.875rem;
  line-height: 1.5;
}

.version-form {
  max-width: 540px;
}

.form-hint {
  margin: 2px 0 12px;
  color: var(--md-on-surface-variant);
  font-size: 0.875rem;
}

.version-compare-panel {
  margin: 4px 0 12px;
  padding: 10px 12px;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-sm);
  background-color: var(--md-surface-container-low);
}

.compare-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.875rem;
  color: var(--md-on-surface);
  line-height: 1.6;
}

.compare-empty {
  color: var(--md-on-surface-variant);
}

.compare-meta {
  margin-top: 4px;
  font-size: 0.8125rem;
  color: var(--md-on-surface-variant);
}

.compare-result {
  margin-top: 8px;
  font-size: 0.875rem;
  font-weight: 500;
}

.compare-new {
  color: var(--md-warning-text);
}

.compare-same {
  color: var(--md-success-text);
}

.compare-error {
  color: var(--md-error-text);
}

.table-toolbar {
  margin-bottom: 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.risk-alert {
  margin-bottom: 12px;
}

.toolbar-search {
  min-width: 280px;
  flex: 1;
}

.key-code {
  background-color: var(--md-primary-container);
  color: var(--md-on-primary-container);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-xs);
  padding: 2px 6px;
  font-size: 0.8125rem;
  word-break: break-all;
}

.settings-table-shell {
  margin-top: var(--md-spacing-4);
}

.value-text {
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: min(52vw, 560px);
  color: var(--md-on-surface);
}

.config-table :deep(.row-managed td) {
  background-color: color-mix(in srgb, var(--md-primary) 7%, var(--md-surface));
}

.settings-config-mobile-list {
  display: grid;
  gap: 12px;
}

.settings-config-mobile-card {
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-lg);
  padding: 12px;
  background-color: var(--md-surface);
}

.settings-config-mobile-card.is-managed {
  background-color: color-mix(in srgb, var(--md-primary) 7%, var(--md-surface));
}

.settings-config-mobile-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.settings-config-mobile-card__meta {
  margin: 0;
  display: grid;
  gap: 8px;
}

.settings-config-mobile-card__meta dt {
  color: var(--md-on-surface-variant);
  font-size: 0.75rem;
}

.settings-config-mobile-card__meta dd {
  margin: 2px 0 0;
  color: var(--md-on-surface);
  font-size: 0.875rem;
  line-height: 1.45;
  word-break: break-word;
  white-space: pre-wrap;
}

.settings-config-mobile-card__actions {
  margin-top: 10px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.settings-config-mobile-card__actions :deep(.n-button) {
  min-height: 44px;
}

.config-modal {
  max-width: min(640px, 92vw);
}

@media (max-width: 1199px) {
  .settings-health-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 833px) {
  .settings-health-grid {
    grid-template-columns: 1fr;
  }

  .top-settings-grid {
    grid-template-columns: 1fr;
  }

  .card-title {
    font-size: 1.125rem;
  }

  .toolbar-search {
    min-width: 100%;
  }
}

/* 黑色主题及白色主题下表单文字可见度增强 */
:deep(.n-form-item-label) {
  color: var(--md-on-surface) !important;
  font-weight: 600 !important;
  transition: color var(--md-duration-medium) var(--md-easing-standard) !important;
}
</style>
