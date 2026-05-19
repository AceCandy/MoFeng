<!-- AIMETA P=蓝图展示_蓝图详细信息|R=蓝图详情展示|NR=不含编辑功能|E=component:BlueprintDisplay|X=internal|A=展示组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="blueprint-display fade-in">
    <h2 class="blueprint-display__heading">你的故事蓝图已生成！</h2>

    <!-- AI消息 -->
    <div v-if="aiMessage" class="blueprint-display__ai-msg">
      <p>{{ aiMessage }}</p>
    </div>

    <div class="blueprint-display__content" v-html="formattedBlueprint"></div>

    <!-- 保存状态 -->
    <div v-if="isSaving" class="blueprint-display__saving">
      <div class="blueprint-display__saving-spinner"></div>
      <h3 class="blueprint-display__saving-title">正在保存蓝图...</h3>
      <p class="blueprint-display__saving-desc">即将跳转到写作工作台，开始您的创作之旅</p>
    </div>

    <div v-else class="blueprint-display__actions">
      <button
        @click="confirmRegenerate"
        class="md-btn md-btn-outlined md-ripple"
      >
        <span class="flex items-center justify-center">
          <svg class="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
          </svg>
          重新生成
        </span>
      </button>
      <button
        @click="confirmBlueprint"
        :disabled="isSaving"
        class="md-btn md-btn-filled md-ripple"
      >
        <span class="flex items-center justify-center">
          <svg class="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path>
          </svg>
          确认并开始创作
        </span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import DOMPurify from 'dompurify'
import { globalAlert } from '@/composables/useAlert'
import type { Blueprint } from '@/api/novel'

interface DisplayField {
  label: string;
  value: any;
  priority: number;
}

type ExtractedFields = Record<string, DisplayField>;

interface Props {
  blueprint: Blueprint | null
  aiMessage?: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  confirm: []
  regenerate: []
}>()

const isSaving = ref(false)

const sanitizeBlueprintHtml = (html: string) => {
  return DOMPurify.sanitize(html, {
    USE_PROFILES: { html: true, svg: true, svgFilters: true },
  })
}

const confirmRegenerate = async () => {
  const confirmed = await globalAlert.showConfirm('重新生成会覆盖当前蓝图，确定继续吗？', '重新生成确认')
  if (confirmed) {
    emit('regenerate')
  }
}

const confirmBlueprint = async () => {
  isSaving.value = true
  try {
    await emit('confirm')
  } finally {
    isSaving.value = false
  }
}

const formattedBlueprint = computed(() => {
  if (!props.blueprint) {
    return sanitizeBlueprintHtml('<p class="bp__error">抱歉，生成大纲失败，未能获取到最终数据。</p>')
  }

  const blueprint = props.blueprint

  const safe = (value: any, fallback = '待补充') => value || fallback

  const createSection = (title: string, content: string, icon: string) => `
    <div class="bp__section">
      <div class="bp__section-header">
        <div class="bp__section-icon">
          ${icon}
        </div>
        <h3 class="bp__section-title">${title}</h3>
      </div>
      <div class="bp__section-body">
        ${content}
      </div>
    </div>
  `

  // Icons
  const icons = {
    summary: '<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>',
    story: '<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path></svg>',
    world: '<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM4.332 8.027a6.012 6.012 0 011.912-2.706C6.512 5.73 6.974 6 7.5 6A1.5 1.5 0 019 7.5V8a2 2 0 004 0 2 2 0 011.523-1.943A5.977 5.977 0 0116 10c0 .34-.028.675-.083 1H15a2 2 0 00-2 2v2.197A5.973 5.973 0 0110 16v-2a2 2 0 00-2-2 2 2 0 01-2-2 2 2 0 00-1.668-1.973z" clip-rule="evenodd"></path></svg>',
    characters: '<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path d="M9 6a3 3 0 11-6 0 3 3 0 016 0zM17 6a3 3 0 11-6 0 3 3 0 016 0zM12.93 17c.046-.327.07-.66.07-1a6.97 6.97 0 00-1.5-4.33A5 5 0 0119 16v1h-6.07zM6 11a5 5 0 015 5v1H1v-1a5 5 0 015-5z"></path></svg>',
    relationships: '<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clip-rule="evenodd"></path></svg>',
    chapters: '<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path d="M4 4a2 2 0 00-2 2v1h16V6a2 2 0 00-2-2H4zM18 9H2v5a2 2 0 002 2h12a2 2 0 002-2V9zM4 13a1 1 0 011-1h1a1 1 0 110 2H5a1 1 0 01-1-1zm5-1a1 1 0 100 2h1a1 1 0 100-2H9z"></path></svg>'
  }

  // Format characters with enhanced styling - 动态兼容所有字段
  const formatCharacters = (characters: any[]) => {
    if (!characters || characters.length === 0) return '<p class="bp__empty">暂无角色信息</p>'

    return characters.map(char => {
      if (typeof char === 'object' && char.name) {
        const name = char.name

        const fieldMappings = {
          identity: {
            keys: ['identity_background', 'identity', 'background', '身份背景', '身份'],
            label: '身份背景',
            priority: 1
          },
          personality: {
            keys: ['personality_traits', 'personality', 'traits', 'character', '性格特质', '性格'],
            label: '性格特质',
            priority: 2
          },
          goal: {
            keys: ['core_goal', 'goal', 'objectives', 'aims', '核心目标', '目标'],
            label: '核心目标',
            priority: 3
          },
          abilities: {
            keys: ['abilities_skills', 'abilities', 'skills', 'powers', '能力技能', '能力', '技能'],
            label: '能力技能',
            priority: 4
          },
          relationship: {
            keys: ['relationship_with_protagonist', 'relationship_to_protagonist', 'relationship', 'relation', '与主角关系', '关系'],
            label: '与主角关系',
            priority: 5
          },
          role: {
            keys: ['role', 'character_role', 'story_role', '角色定位', '角色'],
            label: '角色定位',
            priority: 0
          }
        }

        const extractedFields: ExtractedFields = {}
        const usedKeys = new Set(['name'])

        Object.entries(fieldMappings).forEach(([fieldType, mapping]) => {
          for (const key of mapping.keys) {
            if (char[key] && !usedKeys.has(key)) {
              extractedFields[fieldType] = {
                value: char[key],
                label: mapping.label,
                priority: mapping.priority
              }
              usedKeys.add(key)
              break
            }
          }
        })

        Object.entries(char).forEach(([key, value]) => {
          if (!usedKeys.has(key) && value && typeof value === 'string' && value.trim()) {
            const friendlyLabel = key
              .replace(/_/g, ' ')
              .replace(/([A-Z])/g, ' $1')
              .replace(/^./, str => str.toUpperCase())

            extractedFields[`unknown_${key}`] = {
              value: value,
              label: friendlyLabel,
              priority: 99
            }
            usedKeys.add(key)
          }
        })

        const sortedFields = Object.entries(extractedFields).sort(([,a], [,b]) => a.priority - b.priority)

        let fieldsHTML = ''
        sortedFields.forEach(([fieldType, field]) => {
          if (fieldType === 'role') return
          fieldsHTML += `
            <div class="bp__char-field">
              <span class="bp__char-field-label">${field.label}：</span>
              <span>${field.value}</span>
            </div>
          `
        })

        const roleField = extractedFields.role

        return `
          <div class="bp__char-card">
            <div class="bp__char-card-header">
              <h4 class="bp__char-name">${name}</h4>
              ${roleField ? `<span class="bp__char-role">${roleField.value}</span>` : ''}
            </div>
            <div class="bp__char-fields">
              ${fieldsHTML}
            </div>
          </div>
        `
      }
      else if (typeof char === 'object' && char.description) {
        const desc = char.description
        const identity = desc.identity || ''
        const personality = desc.personality || ''
        const relationship = desc.relationship_to_protagonist || ''

        return `
          <div class="bp__char-card">
            <h4 class="bp__char-name">${char.name}</h4>
            <div class="bp__char-fields">
              ${identity ? `<div class="bp__char-field"><span class="bp__char-field-label">身份：</span><span>${identity}</span></div>` : ''}
              ${personality ? `<div class="bp__char-field"><span class="bp__char-field-label">性格：</span><span>${personality}</span></div>` : ''}
              ${relationship ? `<div class="bp__char-field"><span class="bp__char-field-label">关系：</span><span>${relationship}</span></div>` : ''}
            </div>
          </div>
        `
      }
      else {
        return `
          <div class="bp__char-card">
            <h4 class="bp__char-name">${char.name || '未知角色'}</h4>
            <p class="bp__char-desc">${char.description || '无描述'}</p>
          </div>
        `
      }
    }).join('')
  }

  // Format world setting with enhanced styling
  const formatWorldSetting = (worldSetting: any) => {
    if (!worldSetting || typeof worldSetting !== 'object') return '<p class="bp__empty">暂无世界设定信息</p>'

    let html = ''

    if (worldSetting.core_rules) {
      html += `
        <div class="bp__world-rules">
          <h4 class="bp__world-rules-title">
            <svg class="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"></path></svg>
            核心设定
          </h4>
          <p>${worldSetting.core_rules}</p>
        </div>
      `
    }

    if (worldSetting.key_locations && worldSetting.key_locations.length > 0) {
      html += `
        <div class="bp__world-group">
          <h4 class="bp__world-group-title">
            <svg class="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clip-rule="evenodd"></path></svg>
            关键地点
          </h4>
          <div class="bp__world-items">
            ${worldSetting.key_locations.map((loc: any) => `
              <div class="bp__world-item">
                <h5 class="bp__world-item-name">${loc.name}</h5>
                <p class="bp__world-item-desc">${loc.description}</p>
              </div>
            `).join('')}
          </div>
        </div>
      `
    }

    if (worldSetting.factions && worldSetting.factions.length > 0) {
      html += `
        <div class="bp__world-group">
          <h4 class="bp__world-group-title">
            <svg class="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20"><path d="M9 6a3 3 0 11-6 0 3 3 0 016 0zM17 6a3 3 0 11-6 0 3 3 0 016 0zM12.93 17c.046-.327.07-.66.07-1a6.97 6.97 0 00-1.5-4.33A5 5 0 0119 16v1h-6.07zM6 11a5 5 0 015 5v1H1v-1a5 5 0 015-5z"></path></svg>
            主要势力
          </h4>
          <div class="bp__world-items">
            ${worldSetting.factions.map((fac: any) => `
              <div class="bp__world-item">
                <h5 class="bp__world-item-name">${fac.name}</h5>
                <p class="bp__world-item-desc">${fac.description}</p>
              </div>
            `).join('')}
          </div>
        </div>
      `
    }

    return html || '<p class="bp__empty">暂无世界设定详细信息</p>'
  }

  // Format relationships with enhanced styling
  const formatRelationships = (relationships: any[]) => {
    if (!relationships || relationships.length === 0) return '<p class="bp__empty">暂无关系设定</p>'

    return `
      <div class="bp__rel-list">
        ${relationships.map(rel => {
          const fromChar = rel.character_from || rel.source || '角色A'
          const toChar = rel.character_to || rel.target || '角色B'
          const description = rel.description || '暂无描述'

          return `
            <div class="bp__rel-card">
              <div class="bp__rel-pair">
                <span class="bp__rel-name">${fromChar}</span>
                <svg class="w-5 h-5" style="color: var(--md-on-surface-variant)" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M12.293 5.293a1 1 0 011.414 0l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-2.293-2.293a1 1 0 010-1.414z" clip-rule="evenodd"></path>
                </svg>
                <span class="bp__rel-name">${toChar}</span>
              </div>
              <div class="bp__rel-desc">
                <span class="bp__rel-desc-label">关系描述：</span>${description}
              </div>
            </div>
          `
        }).join('')}
      </div>
    `
  }

  // Header with title and badges
  const headerHTML = `
    <div class="bp__header">
      <h1 class="bp__header-title">${safe(blueprint.title, '未知标题')}</h1>
      <div class="bp__header-badges">
        <span class="bp__badge">${safe(blueprint.genre, '未指定')}</span>
        <span class="bp__badge">${safe(blueprint.style, '未指定')}</span>
        <span class="bp__badge">${safe(blueprint.tone, '未指定')}</span>
        <span class="bp__badge">${safe(blueprint.target_audience, '未指定')}</span>
      </div>
    </div>
  `

  // Summary section
  const summaryHTML = createSection(
    '故事梗概',
    `
    <div class="bp__summary-highlight">
      <h4 class="bp__summary-label">一句话总结</h4>
      <p class="bp__summary-quote">"${safe(blueprint.one_sentence_summary)}"</p>
    </div>
    <div>
      <h4 class="bp__summary-label">完整简介</h4>
      <p>${safe(blueprint.full_synopsis)}</p>
    </div>
    `,
    icons.summary
  )

  // Chapters section
  const chaptersHTML = `
    <div class="bp__chapters">
      ${(blueprint.chapter_outline || []).map((ch) => `
        <div class="bp__chapter-item">
          <div class="bp__chapter-num">${ch.chapter_number}</div>
          <div class="bp__chapter-body">
            <h4 class="bp__chapter-title">第 ${ch.chapter_number} 章: ${ch.title}</h4>
            <p class="bp__chapter-summary">${ch.summary}</p>
          </div>
        </div>
      `).join('')}
    </div>
  `

  return sanitizeBlueprintHtml(`
    ${headerHTML}
    ${summaryHTML}
    ${createSection('世界设定', formatWorldSetting(blueprint.world_setting), icons.world)}
    ${createSection('主要角色', formatCharacters(blueprint.characters || []), icons.characters)}
    ${createSection('角色关系', formatRelationships(blueprint.relationships || []), icons.relationships)}
    ${createSection('章节大纲', chaptersHTML, icons.chapters)}
  `)
})
</script>

<style scoped>
.blueprint-display {
  padding: var(--md-spacing-8);
  background-color: var(--md-surface);
  border-radius: var(--md-radius-xl);
  border: 1px solid var(--md-outline-variant);
  box-shadow: var(--md-elevation-2);
}

.blueprint-display__heading {
  font-size: var(--md-headline-small);
  font-weight: 700;
  text-align: center;
  color: var(--md-on-surface);
  margin-bottom: var(--md-spacing-6);
}

.blueprint-display__ai-msg {
  margin-bottom: var(--md-spacing-6);
  padding: var(--md-spacing-4);
  background-color: var(--md-surface-container-low);
  border-radius: var(--md-radius-sm);
  border: 1px solid var(--md-outline-variant);
  color: var(--md-on-surface);
}

.blueprint-display__content {
  padding: var(--md-spacing-6);
  background-color: var(--md-surface-container-lowest);
  border-radius: var(--md-radius-md);
  border: 1px solid var(--md-outline-variant);
  margin-bottom: var(--md-spacing-6);
}

.blueprint-display__saving {
  text-align: center;
  padding: var(--md-spacing-8) 0;
}

.blueprint-display__saving-spinner {
  width: 3rem;
  height: 3rem;
  border: 3px solid var(--md-outline-variant);
  border-top-color: var(--md-primary);
  border-radius: var(--md-radius-full);
  margin: 0 auto var(--md-spacing-4);
  animation: bp-spin 1s linear infinite;
}

.blueprint-display__saving-title {
  font-size: var(--md-title-medium);
  font-weight: 600;
  color: var(--md-on-surface);
  margin-bottom: var(--md-spacing-2);
}

.blueprint-display__saving-desc {
  color: var(--md-on-surface-variant);
}

.blueprint-display__actions {
  display: flex;
  justify-content: center;
  gap: var(--md-spacing-4);
  flex-wrap: wrap;
}

@keyframes bp-spin {
  to { transform: rotate(360deg); }
}

@media (prefers-reduced-motion: reduce) {
  .blueprint-display__saving-spinner {
    animation: none;
    opacity: 0.6;
  }
}
</style>

<style>
.blueprint-display__content .bp__error {
  text-align: center;
  color: var(--md-error);
}

.blueprint-display__content .bp__empty {
  color: var(--md-on-surface-variant);
  font-style: italic;
}

.blueprint-display__content .bp__section {
  margin-bottom: var(--md-spacing-6);
  background-color: var(--md-surface);
  border-radius: var(--md-radius-md);
  border: 1px solid var(--md-outline-variant);
  padding: var(--md-spacing-5);
}

.blueprint-display__content .bp__section-header {
  display: flex;
  align-items: center;
  margin-bottom: var(--md-spacing-4);
}

.blueprint-display__content .bp__section-icon {
  width: 2rem;
  height: 2rem;
  background-color: var(--md-primary-container);
  color: var(--md-on-primary-container);
  border-radius: var(--md-radius-xs);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: var(--md-spacing-3);
}

.blueprint-display__content .bp__section-title {
  font-size: var(--md-title-medium);
  font-weight: 700;
  color: var(--md-on-surface);
}

.blueprint-display__content .bp__section-body {
  color: var(--md-on-surface-variant);
  line-height: 1.7;
}

.blueprint-display__content .bp__header {
  text-align: center;
  margin-bottom: var(--md-spacing-8);
  padding: var(--md-spacing-6);
  background-color: var(--md-primary);
  border-radius: var(--md-radius-md);
  color: var(--md-on-primary);
}

.blueprint-display__content .bp__header-title {
  font-size: var(--md-headline-medium);
  font-weight: 700;
  margin-bottom: var(--md-spacing-4);
}

.blueprint-display__content .bp__header-badges {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--md-spacing-2);
}

.blueprint-display__content .bp__badge {
  background-color: color-mix(in oklch, var(--md-on-primary) 15%, transparent);
  padding: var(--md-spacing-1) var(--md-spacing-3);
  border-radius: var(--md-radius-full);
  font-size: var(--md-label-medium);
  font-weight: 500;
}

.blueprint-display__content .bp__summary-highlight {
  background-color: var(--md-surface-container-low);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-sm);
  padding: var(--md-spacing-4);
  margin-bottom: var(--md-spacing-4);
}

.blueprint-display__content .bp__summary-label {
  font-weight: 600;
  color: var(--md-on-surface);
  margin-bottom: var(--md-spacing-2);
}

.blueprint-display__content .bp__summary-quote {
  font-size: var(--md-body-large);
  font-style: italic;
  color: var(--md-primary);
}

.blueprint-display__content .bp__char-card {
  background-color: var(--md-surface-container-low);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-sm);
  padding: var(--md-spacing-4);
  margin-bottom: var(--md-spacing-3);
}

.blueprint-display__content .bp__char-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--md-spacing-3);
}

.blueprint-display__content .bp__char-name {
  font-size: var(--md-title-small);
  font-weight: 700;
  color: var(--md-on-surface);
}

.blueprint-display__content .bp__char-role {
  background-color: var(--md-primary-container);
  color: var(--md-on-primary-container);
  padding: 2px var(--md-spacing-2);
  border-radius: var(--md-radius-full);
  font-size: var(--md-label-small);
  font-weight: 500;
}

.blueprint-display__content .bp__char-fields {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-2);
  font-size: var(--md-body-small);
}

.blueprint-display__content .bp__char-field {
  background-color: var(--md-surface);
  border-radius: var(--md-radius-xs);
  padding: var(--md-spacing-2) var(--md-spacing-3);
}

.blueprint-display__content .bp__char-field-label {
  font-weight: 600;
  color: var(--md-on-surface);
  display: block;
  margin-bottom: 2px;
}

.blueprint-display__content .bp__char-desc {
  font-size: var(--md-body-small);
  color: var(--md-on-surface-variant);
  margin-top: var(--md-spacing-1);
}

.blueprint-display__content .bp__world-rules {
  background-color: var(--md-surface-container-low);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-sm);
  padding: var(--md-spacing-4);
  margin-bottom: var(--md-spacing-4);
}

.blueprint-display__content .bp__world-rules-title {
  font-weight: 600;
  color: var(--md-on-surface);
  margin-bottom: var(--md-spacing-2);
  display: flex;
  align-items: center;
}

.blueprint-display__content .bp__world-group {
  margin-bottom: var(--md-spacing-4);
}

.blueprint-display__content .bp__world-group-title {
  font-weight: 600;
  color: var(--md-on-surface);
  margin-bottom: var(--md-spacing-3);
  display: flex;
  align-items: center;
}

.blueprint-display__content .bp__world-items {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-2);
}

.blueprint-display__content .bp__world-item {
  background-color: var(--md-surface-container-low);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-xs);
  padding: var(--md-spacing-3);
}

.blueprint-display__content .bp__world-item-name {
  font-weight: 600;
  color: var(--md-on-surface);
}

.blueprint-display__content .bp__world-item-desc {
  font-size: var(--md-body-small);
  color: var(--md-on-surface-variant);
  margin-top: 2px;
}

.blueprint-display__content .bp__rel-list {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-3);
}

.blueprint-display__content .bp__rel-card {
  background-color: var(--md-surface-container-low);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-sm);
  padding: var(--md-spacing-4);
}

.blueprint-display__content .bp__rel-pair {
  display: flex;
  align-items: center;
  gap: var(--md-spacing-3);
  margin-bottom: var(--md-spacing-2);
}

.blueprint-display__content .bp__rel-name {
  font-weight: 500;
  color: var(--md-on-surface);
  background-color: var(--md-surface);
  padding: 2px var(--md-spacing-3);
  border-radius: var(--md-radius-full);
  font-size: var(--md-body-small);
  border: 1px solid var(--md-outline-variant);
}

.blueprint-display__content .bp__rel-desc {
  font-size: var(--md-body-small);
  color: var(--md-on-surface-variant);
  background-color: var(--md-surface);
  border-radius: var(--md-radius-xs);
  padding: var(--md-spacing-2) var(--md-spacing-3);
}

.blueprint-display__content .bp__rel-desc-label {
  font-weight: 600;
}

.blueprint-display__content .bp__chapters {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-3);
}

.blueprint-display__content .bp__chapter-item {
  display: flex;
  align-items: flex-start;
  gap: var(--md-spacing-3);
  background-color: var(--md-surface-container-low);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-sm);
  padding: var(--md-spacing-4);
}

.blueprint-display__content .bp__chapter-num {
  flex-shrink: 0;
  width: 2.25rem;
  height: 2.25rem;
  background-color: var(--md-primary-container);
  color: var(--md-on-primary-container);
  border-radius: var(--md-radius-xs);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: var(--md-label-medium);
}

.blueprint-display__content .bp__chapter-title {
  font-size: var(--md-title-small);
  font-weight: 700;
  color: var(--md-on-surface);
  margin-bottom: var(--md-spacing-1);
}

.blueprint-display__content .bp__chapter-summary {
  color: var(--md-on-surface-variant);
  line-height: 1.6;
}
</style>
