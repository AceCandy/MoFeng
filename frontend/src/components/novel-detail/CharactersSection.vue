<!-- AIMETA P=角色区_角色信息展示|R=角色卡片|NR=不含编辑功能|E=component:CharactersSection|X=ui|A=角色组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="blueprint-page characters-section">
    <header class="blueprint-section-header">
      <div class="blueprint-section-header__main">
        <span class="blueprint-section-header__icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
          </svg>
        </span>
        <div class="blueprint-section-header__text">
          <p class="blueprint-kicker">人物档案</p>
          <h2 class="blueprint-title">主要角色</h2>
          <p class="blueprint-subtitle">查看核心人物的身份、目标、能力与主角关系，帮助角色在长篇创作中保持一致。</p>
        </div>
      </div>
      <button
        v-if="editable"
        type="button"
        class="blueprint-icon-action"
        aria-label="编辑主要角色"
        title="编辑主要角色"
        @click="emitEdit('characters', '主要角色', data?.characters)"
      >
        <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
          <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
        </svg>
      </button>
    </header>

    <div v-if="characters.length" class="blueprint-card-grid blueprint-card-grid--wide">
      <article
        v-for="(character, index) in characters"
        :key="`${character.name || 'character'}-${index}`"
        class="blueprint-item-card characters-section__card"
      >
        <header class="characters-section__card-head">
          <span class="characters-section__avatar" aria-hidden="true">
            {{ character.name?.slice(0, 1) || '角' }}
          </span>
          <div class="characters-section__identity">
            <h3 class="blueprint-item-title">{{ character.name || '未命名角色' }}</h3>
            <p class="blueprint-item-meta">{{ character.identity || '身份待补充' }}</p>
          </div>
        </header>
        <dl class="characters-section__facts">
          <div v-for="fact in characterFacts(character)" :key="fact.label" class="characters-section__fact">
            <dt>{{ fact.label }}</dt>
            <dd>{{ fact.value }}</dd>
          </div>
        </dl>
      </article>
    </div>

    <div v-else class="blueprint-empty">
      <div>
        <p class="blueprint-empty__title">暂无角色信息</p>
        <p class="blueprint-empty__desc">补充角色后，关系、章节推进和 AI 续写会有更稳定的上下文。</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface CharacterItem {
  name?: string
  identity?: string
  personality?: string
  goals?: string
  abilities?: string
  relationship_to_protagonist?: string
}

const props = defineProps<{
  data: { characters?: CharacterItem[] } | null
  editable?: boolean
}>()

const emit = defineEmits<{
  (e: 'edit', payload: { field: string; title: string; value: unknown }): void
}>()

const characters = computed(() => props.data?.characters || [])

const characterFacts = (character: CharacterItem) =>
  [
    { label: '性格', value: character.personality },
    { label: '目标', value: character.goals },
    { label: '能力', value: character.abilities },
    { label: '与主角关系', value: character.relationship_to_protagonist },
  ].filter((fact): fact is { label: string; value: string } => Boolean(fact.value))

const emitEdit = (field: string, title: string, value: unknown) => {
  if (!props.editable) return
  emit('edit', { field, title, value })
}
</script>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'CharactersSection',
})
</script>

<style scoped>
.characters-section__card {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-4);
}

.characters-section__card-head {
  display: flex;
  align-items: center;
  gap: var(--md-spacing-3);
  min-width: 0;
}

.characters-section__avatar {
  width: 48px;
  height: 48px;
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  border: 1px solid var(--md-outline);
  border-radius: var(--md-radius-xs);
  background-color: var(--md-surface-container);
  color: var(--md-primary-dark);
  font-family: var(--md-font-display);
  font-size: 1.1rem;
  font-weight: 700;
}

.characters-section__identity {
  min-width: 0;
}

.characters-section__facts {
  display: grid;
  gap: var(--md-spacing-3);
  margin: 0;
}

.characters-section__fact {
  padding-top: var(--md-spacing-3);
  border-top: 1px dashed var(--md-outline-variant);
}

.characters-section__fact dt {
  margin: 0 0 var(--md-spacing-1);
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-medium);
  font-weight: 700;
  letter-spacing: 0.08em;
}

.characters-section__fact dd {
  margin: 0;
  color: var(--md-on-surface);
  font-size: var(--md-body-medium);
  line-height: 1.75;
}
</style>
