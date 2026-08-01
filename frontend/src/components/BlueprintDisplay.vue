<!-- AIMETA P=蓝图展示_蓝图详细信息|R=蓝图详情展示|NR=不含编辑功能|E=component:BlueprintDisplay|X=internal|A=展示组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="blueprint-display fade-in">
    <p class="blueprint-display__heading">你的故事蓝图已生成！</p>

    <!-- AI消息 -->
    <div v-if="aiMessage" class="blueprint-display__ai-msg">
      <p>{{ aiMessage }}</p>
    </div>

    <!-- 蓝图主要内容区（已定制水墨极细滚动条，解决长内容滚动灾难） -->
    <div class="blueprint-display__content">
      <template v-if="blueprint">
        <!-- 1. 牌匾落款 Header -->
        <header class="bp__header">
          <h1 class="bp__header-title">{{ safe(blueprint.title, '故事蓝图') }}</h1>
          <div class="bp__header-badges">
            <span v-if="blueprint.genre" class="bp__badge">{{ blueprint.genre }}</span>
            <span v-if="blueprint.style" class="bp__badge">{{ blueprint.style }}</span>
            <span v-if="blueprint.tone" class="bp__badge">{{ blueprint.tone }}</span>
            <span v-if="blueprint.target_audience" class="bp__badge">{{ blueprint.target_audience }}</span>
          </div>
        </header>

        <!-- 2. 故事梗概（温润竹纸笺条风格） -->
        <section class="bp__section">
          <div class="bp__section-header">
            <div class="bp__section-icon" aria-hidden="true">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
              </svg>
            </div>
            <h3 class="bp__section-title">故事梗概</h3>
          </div>
          <div class="bp__section-body">
            <div v-if="blueprint.one_sentence_summary" class="bp__summary-highlight">
              <h4 class="bp__summary-label">一句话总结</h4>
              <p class="bp__summary-quote">“{{ blueprint.one_sentence_summary }}”</p>
            </div>
            <div v-if="blueprint.full_synopsis">
              <h4 class="bp__summary-label">完整简介</h4>
              <p class="bp__synopsis-text">{{ blueprint.full_synopsis }}</p>
            </div>
          </div>
        </section>

        <!-- 3. 世界设定（水墨分栏挂轴风格） -->
        <section class="bp__section" v-if="parsedWorldSetting">
          <div class="bp__section-header">
            <div class="bp__section-icon" aria-hidden="true">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 002 2h2m-4-7a9 9 0 11-18 0 9 9 0 0118 0z"></path>
              </svg>
            </div>
            <h3 class="bp__section-title">世界设定</h3>
          </div>
          <div class="bp__section-body">
            <div v-if="parsedWorldSetting.coreRules" class="bp__world-rules">
              <h4 class="bp__world-rules-title">
                <span class="bp__world-indicator">◇</span>核心设定
              </h4>
              <p>{{ parsedWorldSetting.coreRules }}</p>
            </div>

            <div v-if="parsedWorldSetting.keyLocations.length > 0" class="bp__world-group">
              <h4 class="bp__world-group-title">
                <span class="bp__world-indicator">◇</span>关键地点
              </h4>
              <div class="bp__world-items">
                <div v-for="loc in parsedWorldSetting.keyLocations" :key="loc.name" class="bp__world-item">
                  <h5 class="bp__world-item-name">{{ loc.name }}</h5>
                  <p class="bp__world-item-desc">{{ loc.description }}</p>
                </div>
              </div>
            </div>

            <div v-if="parsedWorldSetting.factions.length > 0" class="bp__world-group">
              <h4 class="bp__world-group-title">
                <span class="bp__world-indicator">◇</span>主要势力
              </h4>
              <div class="bp__world-items">
                <div v-for="fac in parsedWorldSetting.factions" :key="fac.name" class="bp__world-item">
                  <h5 class="bp__world-item-name">{{ fac.name }}</h5>
                  <p class="bp__world-item-desc">{{ fac.description }}</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- 4. 主要角色（碑拓小笺卡片风格） -->
        <section class="bp__section">
          <div class="bp__section-header">
            <div class="bp__section-icon" aria-hidden="true">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"></path>
              </svg>
            </div>
            <h3 class="bp__section-title">主要角色</h3>
          </div>
          <div class="bp__section-body">
            <div v-if="parsedCharacters.length === 0" class="bp__empty">暂无角色信息</div>
            <div v-else class="bp__char-list">
              <div v-for="char in parsedCharacters" :key="char.name" class="bp__char-card">
                <div class="bp__char-card-header">
                  <h4 class="bp__char-name">{{ char.name }}</h4>
                  <span v-if="char.role" class="bp__char-role">{{ char.role }}</span>
                </div>
                <div v-if="char.fields.length > 0" class="bp__char-fields">
                  <div v-for="field in char.fields" :key="field.label" class="bp__char-field">
                    <span class="bp__char-field-label">{{ field.label }}</span>
                    <span class="bp__char-field-value">{{ field.value }}</span>
                  </div>
                </div>
                <p v-if="char.description" class="bp__char-desc">{{ char.description }}</p>
              </div>
            </div>
          </div>
        </section>

        <!-- 5. 角色关系（水墨并蒂细墨线连线风格） -->
        <section class="bp__section">
          <div class="bp__section-header">
            <div class="bp__section-icon" aria-hidden="true">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"></path>
              </svg>
            </div>
            <h3 class="bp__section-title">角色关系</h3>
          </div>
          <div class="bp__section-body">
            <div v-if="parsedRelationships.length === 0" class="bp__empty">暂无关系设定</div>
            <div v-else class="bp__rel-list">
              <div v-for="(rel, idx) in parsedRelationships" :key="idx" class="bp__rel-card">
                <div class="bp__rel-pair">
                  <span class="bp__rel-name">{{ rel.from }}</span>
                  <div class="bp__rel-vine" aria-hidden="true">
                    <span class="bp__rel-leaf bp__rel-leaf--left">◆</span>
                    <span class="bp__rel-vine-line"></span>
                    <span class="bp__rel-leaf bp__rel-leaf--right">◆</span>
                  </div>
                  <span class="bp__rel-name">{{ rel.to }}</span>
                </div>
                <div class="bp__rel-desc">
                  <span class="bp__rel-desc-label">关系描述：</span>{{ rel.description }}
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- 6. 章节大纲（木刻古雅挂签大纲挂筹风格） -->
        <section class="bp__section">
          <div class="bp__section-header">
            <div class="bp__section-icon" aria-hidden="true">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"></path>
              </svg>
            </div>
            <h3 class="bp__section-title">章节大纲</h3>
          </div>
          <div class="bp__section-body">
            <div v-if="!blueprint.chapter_outline || blueprint.chapter_outline.length === 0" class="bp__empty">
              暂无章节大纲信息
            </div>
            <div v-else class="bp__chapters">
              <div v-for="ch in blueprint.chapter_outline" :key="ch.chapter_number" class="bp__chapter-item">
                <div class="bp__chapter-num" title="回目筹牌">
                  <span class="bp__chapter-num-text">{{ convertToChineseNumber(ch.chapter_number) }}</span>
                </div>
                <div class="bp__chapter-body">
                  <h4 class="bp__chapter-title">第 {{ ch.chapter_number }} 章: {{ ch.title }}</h4>
                  <p class="bp__chapter-summary">{{ ch.summary }}</p>
                </div>
              </div>
            </div>
          </div>
        </section>
      </template>
      <div v-else class="bp__error-wrap">
        <p class="bp__error">抱歉，生成大纲失败，未能获取到最终数据。</p>
      </div>
    </div>

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
import { globalAlert } from '@/composables/useAlert'
import type { Blueprint } from '@/api/novel'

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

const safe = (value: any, fallback = '待补充') => value || fallback

// 罗马/古典中式数字转换，增强大纲竹签/牙筹之美
const convertToChineseNumber = (num: number): string => {
  const chineseNums = ['零', '壹', '贰', '叁', '肆', '伍', '陆', '柒', '捌', '玖', '拾']
  if (num <= 10) return chineseNums[num]
  if (num < 20) return `拾${chineseNums[num % 10]}`
  if (num % 10 === 0) return `${chineseNums[Math.floor(num / 10)]}拾`
  return `${chineseNums[Math.floor(num / 10)]}拾${chineseNums[num % 10]}`
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

// ----------------------------------------------------
// 【强类型数据解析清洗】：彻底废弃 v-html 字符串拼接渲染
// ----------------------------------------------------

const parsedWorldSetting = computed(() => {
  const ws = props.blueprint?.world_setting
  if (!ws || typeof ws !== 'object') return null
  return {
    coreRules: ws.core_rules || '',
    keyLocations: ws.key_locations || [],
    factions: ws.factions || []
  }
})

const parsedCharacters = computed(() => {
  const list = props.blueprint?.characters || []
  return list.map((char: any) => {
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

      const extractedFields: Record<string, { value: any; label: string; priority: number }> = {}
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

      // 提取未知多余字段
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

      const sortedFields = Object.entries(extractedFields)
        .filter(([fieldType]) => fieldType !== 'role')
        .sort(([, a], [, b]) => a.priority - b.priority)
        .map(([, f]) => ({ label: f.label, value: f.value }))

      const roleField = extractedFields.role?.value || undefined

      return {
        name,
        role: roleField,
        fields: sortedFields
      }
    } else if (typeof char === 'object' && char.description) {
      const desc = char.description
      const fields: Array<{ label: string; value: string }> = []
      if (typeof desc === 'object') {
        if (desc.identity) fields.push({ label: '身份', value: desc.identity })
        if (desc.personality) fields.push({ label: '性格', value: desc.personality })
        if (desc.relationship_to_protagonist) fields.push({ label: '关系', value: desc.relationship_to_protagonist })
      }
      return {
        name: char.name || '未知角色',
        fields,
        description: typeof desc === 'string' ? desc : undefined
      }
    } else {
      return {
        name: char.name || '未知角色',
        description: char.description || '无描述',
        fields: []
      }
    }
  })
})

const parsedRelationships = computed(() => {
  const list = props.blueprint?.relationships || []
  return list.map((rel: any) => {
    const fromChar = rel.character_from || rel.source || '角色A'
    const toChar = rel.character_to || rel.target || '角色B'
    const description = rel.description || '暂无描述'
    return {
      from: fromChar,
      to: toChar,
      description
    }
  })
})
</script>

<style scoped>
.blueprint-display {
  padding: var(--md-spacing-6) var(--md-spacing-8);
  background-color: var(--md-surface);
  border-radius: var(--md-radius-sm) !important; /* 中式木刻微直角 */
  border: 3px double var(--md-outline) !important; /* 古籍双线框线 */
  box-shadow: 4px 4px 0px color-mix(in srgb, var(--md-on-surface) 15%, transparent) !important;
  /* 弹性布局一屏内高度完美收敛，彻底根治大纲超长溢出看不全灾难 */
  height: 100%;
  max-height: calc(var(--app-viewport-unit) - 120px) !important;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
}

.blueprint-display__heading {
  font-family: var(--md-font-serif);
  font-size: var(--md-headline-small);
  font-weight: 700;
  letter-spacing: 0.05em; /* 碑拓骨力：大标题拉开字距 */
  text-align: center;
  color: var(--md-primary-dark);
  margin-bottom: var(--md-spacing-4);
  flex-shrink: 0; /* 标题固定不缩窄 */
}

.blueprint-display__ai-msg {
  margin-bottom: var(--md-spacing-4);
  padding: var(--md-spacing-3) var(--md-spacing-4);
  background-color: var(--md-surface-container-low);
  border-radius: var(--md-radius-xs) !important;
  border: 1px solid var(--md-outline-variant);
  color: var(--md-on-surface);
  flex-shrink: 0; /* 消息框固定不缩窄 */
}

.blueprint-display__content {
  padding: var(--md-spacing-5) var(--md-spacing-6);
  background-color: var(--md-surface); /* 宣纸温润：长文正文只用熟宣，不用近白 */
  border-radius: var(--md-radius-xs) !important;
  border: 1px solid var(--md-outline-variant);
  margin-bottom: var(--md-spacing-4);
  flex: 1; /* 弹性占据剩余高度，容纳超长大纲 */
  overflow-y: auto; /* 允许纵向平滑滚动 */
  min-height: 0; /* flex 内部 overflow 滚动必须 */

  /* 优雅的水墨轻盈极细滚动条，替代暴力隐藏，全面解决不可滚动交互灾难 */
  scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--md-on-surface) 25%, transparent) transparent;
}

.blueprint-display__content::-webkit-scrollbar {
  display: block !important;
  width: 4px;
}

.blueprint-display__content::-webkit-scrollbar-track {
  background: transparent;
}

.blueprint-display__content::-webkit-scrollbar-thumb {
  background-color: color-mix(in srgb, var(--md-on-surface) 20%, transparent) !important; /* 需压过全局透明 thumb */
  border-radius: var(--md-radius-xs);
}

.blueprint-display__content::-webkit-scrollbar-thumb:hover {
  background-color: color-mix(in srgb, var(--md-on-surface) 45%, transparent) !important;
}

.blueprint-display__saving {
  text-align: center;
  padding: var(--md-spacing-6) 0;
  flex-shrink: 0;
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
  flex-shrink: 0; /* 按钮固定不缩窄 */
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

/* ----------------------------------------------------
   「古雅熟宣竹纸笺与木刻拓片小卡片」古风视觉主题重塑
   ---------------------------------------------------- */

.bp__error-wrap {
  text-align: center;
  padding: var(--md-spacing-10) 0;
}

.bp__error {
  color: var(--md-error);
  font-weight: 500;
}

.bp__empty {
  color: var(--md-primary-light);
  font-style: italic;
  text-align: center;
  padding: var(--md-spacing-6) 0;
  opacity: 0.8;
}

/* 牌匾落款 Header */
.bp__header {
  text-align: center;
  margin-bottom: var(--md-spacing-6);
  padding: var(--md-spacing-6) var(--md-spacing-4);
  background-color: var(--md-surface-container-low); /* 温润竹纸底色 */
  border: 1px solid var(--md-outline-variant);
  border-bottom: 3px double var(--md-outline); /* 古籍特有双线分割 */
  border-radius: 4px;
  position: relative;
  box-shadow: 1px 1px 0px color-mix(in srgb, var(--md-on-surface) 5%, transparent);
}

.bp__header::before {
  content: "";
  position: absolute;
  left: 0;
  top: 15%;
  bottom: 15%;
  width: 4px;
  background-color: var(--md-secondary); /* 朱砂细竖批 */
  border-radius: 1px;
}

.bp__header-title {
  font-family: var(--md-font-serif);
  font-size: var(--md-headline-medium);
  font-weight: 700;
  color: var(--md-primary-dark); /* 焦墨字色 */
  margin-bottom: var(--md-spacing-4);
  letter-spacing: 0.08em;
}

.bp__header-badges {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--md-spacing-2);
}

/* 微方折木刻细框墨字标签（朱砂罕用：只留牌匾竖批与筹牌红珠） */
.bp__badge {
  background-color: transparent;
  border: 1px solid var(--md-outline); /* 竹青细边框 */
  color: var(--md-primary-light); /* 松烟墨字 */
  padding: 3px var(--md-spacing-3);
  border-radius: 2px !important; /* 木刻小微直角 */
  font-family: var(--md-font-serif);
  font-size: var(--md-label-medium);
  font-weight: 600;
  box-shadow: 1px 1px 0px color-mix(in srgb, var(--md-on-surface) 10%, transparent);
  letter-spacing: 0.05em;
  display: inline-block;
  line-height: 1.3;
}

/* 双线木刻大板块 */
.bp__section {
  margin-bottom: var(--md-spacing-6);
  background-color: var(--md-surface); /* 熟宣纸色 */
  border-radius: 4px !important; /* 微直角 */
  border: 2px double var(--md-outline) !important; /* 雅致双线黑边框 */
  padding: var(--md-spacing-5) clamp(var(--md-spacing-4), 4vw, var(--md-spacing-6));
  box-shadow: 2px 2px 0px color-mix(in srgb, var(--md-on-surface) 8%, transparent) !important; /* 碑拓偏置硬投影 */
}

.bp__section-header {
  display: flex;
  align-items: center;
  margin-bottom: var(--md-spacing-5);
  border-bottom: 1px solid var(--md-outline-variant); /* 墨晕细横线 */
  padding-bottom: var(--md-spacing-3);
}

.bp__section-icon {
  width: 2.25rem;
  height: 2.25rem;
  background-color: var(--md-surface-container-low);
  color: var(--md-primary-dark);
  border: 1px solid var(--md-outline-variant);
  border-radius: 2px; /* 木刻微直角 */
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: var(--md-spacing-3);
}

.bp__section-title {
  font-family: var(--md-font-serif);
  font-size: var(--md-title-medium);
  font-weight: 700;
  color: var(--md-primary-dark);
  letter-spacing: 0.05em;
}

.bp__section-body {
  color: var(--md-primary-dark);
  line-height: 1.8;
}

/* 梗概：温润竹纸笺条 */
.bp__summary-highlight {
  background-color: var(--md-surface-container-low); /* 温润竹纸色 */
  border: 1.5px solid var(--md-outline);
  border-radius: 2px;
  padding: var(--md-spacing-4);
  margin-bottom: var(--md-spacing-5);
  position: relative;
}

.bp__summary-highlight::before {
  content: "";
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3.5px;
  background-color: var(--md-primary-light); /* 松烟细描 */
}

.bp__summary-label {
  font-family: var(--md-font-serif);
  font-weight: 600;
  color: var(--md-primary-light);
  margin-bottom: var(--md-spacing-2);
  letter-spacing: 0.05em;
  font-size: var(--md-label-large);
}

.bp__summary-quote {
  font-family: var(--md-font-family);
  font-size: 16px;
  line-height: 1.8;
  font-weight: 500;
  color: var(--md-primary-dark); /* 焦墨 */
  font-style: normal;
  text-indent: 1em;
}

.bp__synopsis-text {
  font-family: var(--md-font-family);
  font-size: 15px;
  line-height: 1.85;
  color: var(--md-primary-light);
  text-indent: 2em; /* 首行缩进 */
}

/* 世界设定：分栏挂轴与松烟引示 */
.bp__world-rules {
  background-color: var(--md-surface-container-low);
  border: 1.5px solid var(--md-outline);
  border-radius: 2px;
  padding: var(--md-spacing-5);
  margin-bottom: var(--md-spacing-5);
}

.bp__world-rules p {
  font-size: 15px;
  line-height: 1.8;
  color: var(--md-primary-light);
}

.bp__world-rules-title {
  font-family: var(--md-font-serif);
  font-weight: 700;
  color: var(--md-primary-dark);
  margin-bottom: var(--md-spacing-3);
  display: flex;
  align-items: center;
  font-size: var(--md-title-small);
}

.bp__world-indicator {
  color: var(--md-primary-light); /* 松烟菱花引示 */
  font-weight: bold;
  margin-right: 6px;
  font-size: 10px;
}

.bp__world-group {
  margin-bottom: var(--md-spacing-5);
}

.bp__world-group-title {
  font-family: var(--md-font-serif);
  font-weight: 700;
  color: var(--md-primary-dark);
  margin-bottom: var(--md-spacing-3);
  display: flex;
  align-items: center;
  border-bottom: 1.5px solid var(--md-outline-variant);
  padding-bottom: var(--md-spacing-2);
  font-size: var(--md-title-small);
}

.bp__world-items {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 280px), 1fr));
  gap: var(--md-spacing-4);
}

.bp__world-item {
  background-color: var(--md-surface-container-low);
  border: 1px solid var(--md-outline-variant);
  border-radius: 2px;
  padding: var(--md-spacing-4);
  box-shadow: 1px 1px 0px color-mix(in srgb, var(--md-on-surface) 3%, transparent);
}

.bp__world-item-name {
  font-family: var(--md-font-serif);
  font-weight: 700;
  color: var(--md-primary-dark);
  margin-bottom: var(--md-spacing-1);
  font-size: 15px;
}

.bp__world-item-desc {
  font-family: var(--md-font-family);
  font-size: var(--md-body-small);
  color: var(--md-primary-light);
  line-height: 1.6;
}

/* 角色：碑拓生宣折叠卡 */
.bp__char-list {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-4);
}

.bp__char-card {
  background-color: var(--md-surface-container-low); /* 竹纸底衬 */
  border: 1px solid var(--md-outline-variant);
  border-radius: 2px;
  padding: var(--md-spacing-6) var(--md-spacing-5);
  box-shadow: 1px 1px 0px color-mix(in srgb, var(--md-on-surface) 4%, transparent);
  transition:
    background-color 0.25s ease,
    border-color 0.25s ease,
    box-shadow 0.25s ease,
    color 0.25s ease,
    transform 0.25s ease;
}

.bp__char-card:hover {
  background-color: var(--md-surface);
  border-color: var(--md-outline);
  box-shadow: 2px 2px 0px color-mix(in srgb, var(--md-on-surface) 8%, transparent);
}

.bp__char-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1.5px solid var(--md-outline-variant);
  padding-bottom: var(--md-spacing-2);
  margin-bottom: var(--md-spacing-3);
}

.bp__char-name {
  font-family: var(--md-font-serif);
  font-size: 17px;
  font-weight: 700;
  color: var(--md-primary-dark);
  letter-spacing: 0.03em;
}

.bp__char-role {
  background-color: transparent;
  border: 1px solid var(--md-outline); /* 竹青细框印记 */
  color: var(--md-primary-light);
  padding: 2px var(--md-spacing-3);
  border-radius: 1px; /* 方正印记 */
  font-size: var(--md-label-small);
  font-family: var(--md-font-serif);
  font-weight: 600;
  line-height: 1.1;
  box-shadow: 0.5px 0.5px 0px color-mix(in srgb, var(--md-on-surface) 8%, transparent);
}

.bp__char-fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 260px), 1fr)); /* 自适应分栏 */
  gap: var(--md-spacing-3);
  margin-bottom: var(--md-spacing-3);
}

.bp__char-field {
  background-color: var(--md-surface); /* 熟宣底托 */
  border: 1px solid var(--md-outline-variant);
  border-radius: 2px;
  padding: var(--md-spacing-3) var(--md-spacing-4);
  font-size: 13.5px;
  line-height: 1.6;
  display: flex;
  flex-direction: column;
}

.bp__char-field-label {
  font-family: var(--md-font-serif);
  font-weight: 600;
  color: var(--md-primary-light);
  margin-bottom: 2px;
  border-bottom: 1.5px solid var(--md-outline-variant);
  align-self: flex-start;
  font-size: 13px;
  letter-spacing: 0.05em;
  padding-bottom: 1px;
}

.bp__char-field-value {
  color: var(--md-primary-dark);
  margin-top: var(--md-spacing-1);
}

.bp__char-desc {
  font-family: var(--md-font-family);
  font-size: 14px;
  color: var(--md-primary-light);
  background-color: var(--md-surface);
  padding: var(--md-spacing-3);
  border-radius: 2px;
  border: 1px dashed var(--md-outline-variant);
  line-height: 1.65;
  margin-top: var(--md-spacing-2);
}

/* 关系：并蒂双生墨藤/青玉细墨线 */
.bp__rel-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 320px), 1fr));
  gap: var(--md-spacing-4);
}

.bp__rel-card {
  background-color: var(--md-surface-container-low);
  border: 1px solid var(--md-outline-variant);
  border-radius: 2px;
  padding: var(--md-spacing-5);
  box-shadow: 1.5px 1.5px 0px color-mix(in srgb, var(--md-on-surface) 4%, transparent);
}

.bp__rel-pair {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--md-spacing-3);
  margin-bottom: var(--md-spacing-3);
  position: relative;
}

.bp__rel-name {
  font-family: var(--md-font-serif);
  font-weight: 600;
  color: var(--md-primary-dark);
  background-color: var(--md-surface);
  padding: 3px var(--md-spacing-4);
  border-radius: 2px;
  font-size: 14px;
  border: 1px solid var(--md-outline);
  box-shadow: 1px 1px 0px color-mix(in srgb, var(--md-on-surface) 8%, transparent);
  letter-spacing: 0.02em;
}

.bp__rel-vine {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: relative;
  min-width: 40px;
}

.bp__rel-vine-line {
  position: absolute;
  left: 0;
  right: 0;
  height: 1.5px;
  background-color: var(--md-outline); /* 青玉细线 */
}

.bp__rel-leaf {
  color: var(--md-primary-light); /* 松烟细叶徽志 */
  font-size: 8px;
  line-height: 1;
  z-index: 5;
  background-color: var(--md-surface-container-low);
  padding: 0 2px;
}

.bp__rel-leaf--left {
  margin-left: 2px;
}

.bp__rel-leaf--right {
  margin-right: 2px;
}

.bp__rel-desc {
  font-family: var(--md-font-family);
  font-size: 13.5px;
  color: var(--md-primary-light);
  background-color: var(--md-surface);
  border-radius: 2px;
  padding: var(--md-spacing-3) var(--md-spacing-4);
  border: 1px solid var(--md-outline-variant);
  line-height: 1.6;
}

.bp__rel-desc-label {
  font-family: var(--md-font-serif);
  font-weight: 600;
  color: var(--md-primary-dark);
}

/* 章节大纲：木刻牙筹/水墨编号 */
.bp__chapters {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-4);
}

.bp__chapter-item {
  display: flex;
  align-items: flex-start;
  gap: var(--md-spacing-4);
  background-color: var(--md-surface-container-low);
  border: 1px solid var(--md-outline-variant);
  border-radius: 2px;
  padding: var(--md-spacing-5) var(--md-spacing-6);
  transition:
    background-color 0.25s cubic-bezier(0.2, 0, 0, 1),
    border-color 0.25s cubic-bezier(0.2, 0, 0, 1),
    box-shadow 0.25s cubic-bezier(0.2, 0, 0, 1),
    color 0.25s cubic-bezier(0.2, 0, 0, 1),
    transform 0.25s cubic-bezier(0.2, 0, 0, 1);
}

.bp__chapter-item:hover {
  background-color: var(--md-surface);
  border-color: var(--md-outline);
  box-shadow: 2px 2px 0px color-mix(in srgb, var(--md-on-surface) 8%, transparent);
}

.bp__chapter-num {
  flex-shrink: 0;
  width: 2.25rem;
  height: 3.25rem; /* 挂筹牙筹筹牌形状 */
  background-color: var(--md-surface);
  border: 1.5px solid var(--md-outline);
  color: var(--md-primary-dark);
  border-radius: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--md-font-serif);
  font-weight: 700;
  font-size: var(--md-label-large);
  box-shadow: 1.5px 1.5px 0px color-mix(in srgb, var(--md-on-surface) 10%, transparent);
  position: relative;
  box-sizing: border-box;
}

.bp__chapter-num::before {
  content: "";
  position: absolute;
  top: 4px;
  left: 50%;
  transform: translateX(-50%); /* 朱砂挂筹红珠水平居中 */
  width: 4px;
  height: 4px;
  background-color: var(--md-secondary); /* 朱砂挂筹红绳印（全页唯一朱印落款） */
  border-radius: 50%;
}

.bp__chapter-num-text {
  writing-mode: vertical-rl; /* 优雅的古风回目竖写 */
  text-orientation: upright;
  line-height: 1;
  font-size: 11px;
  margin-top: 5px;
  letter-spacing: 0; /* 竖排回目不再负字距挤压 */
}

.bp__chapter-body {
  flex: 1;
  min-width: 0;
}

.bp__chapter-title {
  font-family: var(--md-font-serif);
  font-size: 16px;
  font-weight: 700;
  color: var(--md-primary-dark);
  margin-bottom: var(--md-spacing-2);
  letter-spacing: 0.03em;
}

.bp__chapter-summary {
  font-family: var(--md-font-family);
  color: var(--md-primary-light);
  line-height: 1.8;
  font-size: 14.5px;
  text-indent: 2em; /* 首行缩进 */
}

/* 窄屏案头：小屏留白收敛，卡片防溢出 */
@media (max-width: 640px) {
  .blueprint-display {
    padding: var(--md-spacing-4);
  }

  .blueprint-display__content {
    padding: var(--md-spacing-4);
  }

  .bp__header {
    padding: var(--md-spacing-4) var(--md-spacing-3);
  }

  .bp__section {
    padding: var(--md-spacing-4);
  }

  .bp__char-card,
  .bp__rel-card {
    padding: var(--md-spacing-4);
  }

  .blueprint-display__actions {
    gap: var(--md-spacing-3);
  }
}
</style>

