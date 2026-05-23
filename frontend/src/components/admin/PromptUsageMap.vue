<!-- AIMETA P=提示词关系图_阶段到Prompt映射|R=提示词使用可视化|NR=不含编辑|E=component:PromptUsageMap|X=ui|A=关系总览|D=vue|S=dom,cache|RD=./README.ai -->
<template>
  <section class="prompt-usage" aria-label="提示词阶段关系">
    <header class="prompt-usage__toolbar">
      <div>
        <p class="prompt-usage__eyebrow">Prompt Usage Map</p>
        <h3>阶段与提示词关系</h3>
        <p>按实际调用点整理 AI 阶段、Prompt 名称、用途和当前数据库状态。</p>
      </div>
      <div class="prompt-usage__actions">
        <button type="button" class="prompt-usage__button" @click="refetchPrompts">
          刷新
        </button>
        <button type="button" class="prompt-usage__button is-primary" @click="emit('openPromptEditor')">
          编辑模板
        </button>
      </div>
    </header>

    <div class="prompt-usage__summary" aria-label="提示词关系统计">
      <div class="prompt-usage__stat">
        <span>调用点</span>
        <strong>{{ PROMPT_USAGE_ITEMS.length }}</strong>
      </div>
      <div class="prompt-usage__stat">
        <span>数据库模板</span>
        <strong>{{ prompts.length }}</strong>
      </div>
      <div class="prompt-usage__stat">
        <span>缺失模板</span>
        <strong>{{ missingPromptNames.length }}</strong>
      </div>
      <div class="prompt-usage__stat">
        <span>内置提示</span>
        <strong>{{ inlineUsageCount }}</strong>
      </div>
    </div>

    <div class="prompt-usage__filters">
      <label class="prompt-usage__search">
        <span>搜索阶段、功能或 Prompt</span>
        <input v-model="searchText" type="search" placeholder="例如 world_blueprint / screenwriting" />
      </label>
      <label class="prompt-usage__toggle">
        <input v-model="showMissingOnly" type="checkbox" />
        <span>只看缺失模板</span>
      </label>
    </div>

    <div v-if="queryError" class="prompt-usage__notice is-error">
      {{ queryError }}
    </div>

    <div v-if="loading" class="prompt-usage__loading">正在校对提示词关系...</div>

    <div v-else class="prompt-usage__groups">
      <section
        v-for="group in groupedUsageItems"
        :key="group.category"
        class="prompt-usage__group"
      >
        <div class="prompt-usage__group-title">
          <h4>{{ group.category }}</h4>
          <span>{{ group.items.length }} 个调用点</span>
        </div>

        <article
          v-for="item in group.items"
          :key="item.id"
          class="prompt-usage__row"
          :class="{ 'has-missing': hasMissingPrompt(item), 'is-inline': item.status === 'inline' }"
        >
          <div class="prompt-usage__stage">
            <span class="prompt-usage__seal">{{ item.stage.slice(0, 1).toUpperCase() }}</span>
            <div>
              <h5>{{ item.feature }}</h5>
              <code>{{ item.stage }}</code>
            </div>
          </div>

          <div class="prompt-usage__prompts">
            <template v-if="item.promptNames.length">
              <span
                v-for="promptName in item.promptNames"
                :key="promptName"
                class="prompt-usage__prompt-chip"
                :class="{ 'is-missing': !promptMap.has(promptName) }"
                :title="promptMap.has(promptName) ? '数据库中存在' : '数据库中缺失'"
              >
                {{ promptName }}
              </span>
            </template>
            <span v-else class="prompt-usage__inline-chip">内置提示词</span>
            <span
              v-for="fallbackName in item.fallbackPromptNames || []"
              :key="fallbackName"
              class="prompt-usage__fallback-chip"
            >
              {{ fallbackName }}
            </span>
          </div>

          <p class="prompt-usage__purpose">{{ item.purpose }}</p>
          <code class="prompt-usage__entry">{{ item.entry }}</code>
        </article>
      </section>

      <div v-if="groupedUsageItems.length === 0" class="prompt-usage__empty">
        没有符合筛选条件的提示词关系。
      </div>
    </div>

    <aside v-if="unusedPrompts.length" class="prompt-usage__unused">
      <h4>数据库中暂未映射到调用点的模板</h4>
      <div class="prompt-usage__unused-list">
        <span v-for="prompt in unusedPrompts" :key="prompt.id">{{ prompt.name }}</span>
      </div>
    </aside>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

import { PROMPT_USAGE_ITEMS, type PromptUsageItem } from '@/constants/promptUsage'
import { useAdminPromptsQuery } from '@/queries/admin'

const emit = defineEmits<{
  (event: 'openPromptEditor'): void
}>()

const promptsQuery = useAdminPromptsQuery()
const searchText = ref('')
const showMissingOnly = ref(false)

const prompts = computed(() => promptsQuery.data.value ?? [])
const loading = computed(() => promptsQuery.isLoading.value || promptsQuery.isFetching.value)
const queryError = computed(() => {
  const error = promptsQuery.error.value
  return error instanceof Error ? error.message : error ? String(error) : ''
})

const promptMap = computed(() => new Map(prompts.value.map((prompt) => [prompt.name, prompt])))
const mappedPromptNames = computed(() => new Set(PROMPT_USAGE_ITEMS.flatMap((item) => item.promptNames)))
const inlineUsageCount = computed(() => PROMPT_USAGE_ITEMS.filter((item) => item.status === 'inline').length)

const missingPromptNames = computed(() => {
  const names = PROMPT_USAGE_ITEMS.flatMap((item) => item.promptNames)
  return Array.from(new Set(names.filter((name) => !promptMap.value.has(name)))).sort()
})

const unusedPrompts = computed(() =>
  prompts.value
    .filter((prompt) => !mappedPromptNames.value.has(prompt.name))
    .sort((left, right) => left.name.localeCompare(right.name)),
)

const hasMissingPrompt = (item: PromptUsageItem) => {
  return item.promptNames.some((name) => !promptMap.value.has(name))
}

const filteredUsageItems = computed(() => {
  const keyword = searchText.value.trim().toLowerCase()
  return PROMPT_USAGE_ITEMS.filter((item) => {
    if (showMissingOnly.value && !hasMissingPrompt(item)) {
      return false
    }
    if (!keyword) {
      return true
    }
    const haystack = [
      item.category,
      item.feature,
      item.stage,
      item.entry,
      item.purpose,
      ...item.promptNames,
      ...(item.fallbackPromptNames || []),
    ]
      .join(' ')
      .toLowerCase()
    return haystack.includes(keyword)
  })
})

const groupedUsageItems = computed(() => {
  const groups = new Map<string, PromptUsageItem[]>()
  filteredUsageItems.value.forEach((item) => {
    const current = groups.get(item.category) || []
    current.push(item)
    groups.set(item.category, current)
  })
  return Array.from(groups.entries()).map(([category, items]) => ({ category, items }))
})

const refetchPrompts = () => {
  void promptsQuery.refetch()
}
</script>

<style scoped>
.prompt-usage {
  display: flex;
  flex-direction: column;
  gap: 18px;
  color: var(--md-on-surface);
}

.prompt-usage__toolbar {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: flex-start;
}

.prompt-usage__eyebrow {
  margin: 0 0 4px;
  color: var(--md-on-surface-variant);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.prompt-usage__toolbar h3 {
  margin: 0;
  font-size: 22px;
  line-height: 1.35;
}

.prompt-usage__toolbar p {
  margin: 6px 0 0;
  color: var(--md-on-surface-variant);
  font-size: 14px;
}

.prompt-usage__actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.prompt-usage__button {
  min-height: 36px;
  padding: 0 14px;
  border: 1px solid var(--md-outline);
  border-radius: 4px;
  background: var(--md-surface-container-low);
  color: var(--md-on-surface);
  font-weight: 700;
  cursor: pointer;
}

.prompt-usage__button:hover {
  background: var(--md-surface-container);
}

.prompt-usage__button.is-primary {
  border-color: var(--md-primary);
  background: var(--md-primary);
  color: var(--md-on-primary);
}

.prompt-usage__summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.prompt-usage__stat {
  padding: 12px 14px;
  border: 1px solid var(--md-outline-variant);
  border-radius: 6px;
  background: var(--md-surface-container-low);
}

.prompt-usage__stat span {
  display: block;
  color: var(--md-on-surface-variant);
  font-size: 12px;
  font-weight: 700;
}

.prompt-usage__stat strong {
  display: block;
  margin-top: 4px;
  font-size: 24px;
  line-height: 1.1;
}

.prompt-usage__filters {
  display: flex;
  align-items: end;
  gap: 14px;
  flex-wrap: wrap;
  padding: 12px;
  border: 1px solid var(--md-outline-variant);
  border-radius: 6px;
  background: var(--md-surface-container-lowest);
}

.prompt-usage__search {
  flex: 1 1 320px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: var(--md-on-surface-variant);
  font-size: 12px;
  font-weight: 700;
}

.prompt-usage__search input {
  width: 100%;
  height: 38px;
  padding: 0 12px;
  border: 1px solid var(--md-outline);
  border-radius: 4px;
  background: var(--md-surface-container-lowest);
  color: var(--md-on-surface);
}

.prompt-usage__search input:focus {
  outline: 2px solid color-mix(in srgb, var(--md-primary) 32%, transparent);
  outline-offset: 1px;
}

.prompt-usage__toggle {
  min-height: 38px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--md-on-surface-variant);
  font-size: 13px;
  font-weight: 700;
}

.prompt-usage__notice,
.prompt-usage__loading,
.prompt-usage__empty {
  padding: 14px;
  border-radius: 6px;
  background: var(--md-surface-container-low);
  color: var(--md-on-surface-variant);
}

.prompt-usage__notice.is-error {
  border: 1px solid var(--md-error);
  background: var(--md-error-container);
  color: var(--md-error);
}

.prompt-usage__groups {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.prompt-usage__group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.prompt-usage__group-title {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
}

.prompt-usage__group-title h4 {
  margin: 0;
  font-size: 16px;
}

.prompt-usage__group-title span {
  color: var(--md-on-surface-variant);
  font-size: 12px;
}

.prompt-usage__row {
  display: grid;
  grid-template-columns: minmax(210px, 0.9fr) minmax(220px, 1.1fr) minmax(260px, 1.2fr);
  gap: 14px;
  align-items: center;
  padding: 14px;
  border: 1px solid var(--md-outline-variant);
  border-radius: 6px;
  background: var(--md-surface-container-lowest);
}

.prompt-usage__row.has-missing {
  border-color: var(--md-warning);
  background: color-mix(in srgb, var(--md-warning-container) 54%, var(--md-surface-container-lowest));
}

.prompt-usage__row.is-inline {
  background: var(--md-surface-container-low);
}

.prompt-usage__stage {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.prompt-usage__seal {
  flex: 0 0 auto;
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  background: var(--md-primary);
  color: var(--md-on-primary);
  font-size: 13px;
  font-weight: 800;
  box-shadow: 2px 2px 0 rgba(28, 32, 34, 0.14);
}

.prompt-usage__stage h5 {
  margin: 0 0 4px;
  font-size: 14px;
}

.prompt-usage code {
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 12px;
}

.prompt-usage__prompts {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
}

.prompt-usage__prompt-chip,
.prompt-usage__fallback-chip,
.prompt-usage__inline-chip {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 0 9px;
  border-radius: 4px;
  border: 1px solid var(--md-outline-variant);
  background: var(--md-surface-container);
  color: var(--md-on-surface);
  font-size: 12px;
  font-weight: 700;
}

.prompt-usage__prompt-chip.is-missing {
  border-color: var(--md-warning);
  background: var(--md-warning-container);
  color: color-mix(in srgb, var(--md-on-surface) 80%, var(--md-warning));
}

.prompt-usage__fallback-chip {
  color: var(--md-on-surface-variant);
}

.prompt-usage__inline-chip {
  background: var(--md-surface-container-high);
  color: var(--md-on-surface-variant);
}

.prompt-usage__purpose {
  margin: 0;
  color: var(--md-on-surface);
  font-size: 13px;
  line-height: 1.6;
}

.prompt-usage__entry {
  grid-column: 1 / -1;
  color: var(--md-on-surface-variant);
}

.prompt-usage__unused {
  padding: 14px;
  border: 1px solid var(--md-outline-variant);
  border-radius: 6px;
  background: var(--md-surface-container-low);
}

.prompt-usage__unused h4 {
  margin: 0 0 10px;
  font-size: 14px;
}

.prompt-usage__unused-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.prompt-usage__unused-list span {
  padding: 4px 8px;
  border: 1px solid var(--md-outline-variant);
  border-radius: 4px;
  background: var(--md-surface-container-lowest);
  color: var(--md-on-surface-variant);
  font-size: 12px;
}

@media (max-width: 820px) {
  .prompt-usage__toolbar {
    flex-direction: column;
  }

  .prompt-usage__actions {
    justify-content: flex-start;
  }

  .prompt-usage__summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .prompt-usage__row {
    grid-template-columns: 1fr;
  }
}
</style>
