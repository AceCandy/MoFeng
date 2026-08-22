<!-- AIMETA P=关系区_角色关系展示|R=关系图谱|NR=不含编辑功能|E=component:RelationshipsSection|X=ui|A=关系组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="blueprint-page relationships-section">
    <header class="blueprint-section-header">
      <div class="blueprint-section-header__main">
        <span class="blueprint-section-header__icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M22 8l-3 3-3-3M19 11V4" />
          </svg>
        </span>
        <div class="blueprint-section-header__text">
          <p class="blueprint-kicker">关系档案</p>
          <h2 class="blueprint-title">人物关系</h2>
          <p class="blueprint-subtitle">集中查看角色之间的牵引、冲突与情感纽带，便于后续章节沿着既定关系推进。</p>
        </div>
      </div>
      <button
        v-if="editable"
        type="button"
        class="blueprint-icon-action"
        aria-label="编辑人物关系"
        title="编辑人物关系"
        @click="emitEdit('relationships', '人物关系', data?.relationships)"
      >
        <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
          <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
        </svg>
      </button>
    </header>

    <div v-if="relationships.length" class="blueprint-card-grid blueprint-card-grid--wide">
      <article
        v-for="(relation, index) in relationships"
        :key="`${relation.character_from || 'from'}-${relation.character_to || 'to'}-${index}`"
        class="blueprint-item-card relationships-section__card"
      >
        <div class="relationships-section__pair">
          <div class="relationships-section__person">
            <span class="relationships-section__avatar" aria-hidden="true">
              {{ relation.character_from?.slice(0, 1) || '角' }}
            </span>
            <strong>{{ relation.character_from || '未知角色' }}</strong>
          </div>
          <span class="relationships-section__arrow" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M5 12h14M13 6l6 6-6 6" />
            </svg>
          </span>
          <div class="relationships-section__person relationships-section__person--end">
            <strong>{{ relation.character_to || '未知角色' }}</strong>
            <span class="relationships-section__avatar relationships-section__avatar--secondary" aria-hidden="true">
              {{ relation.character_to?.slice(0, 1) || '角' }}
            </span>
          </div>
        </div>
        <div class="relationships-section__type">
          <p class="blueprint-kicker">关系类型</p>
          <h3 class="blueprint-item-title">{{ relation.relationship_type || '关系待补充' }}</h3>
          <p class="blueprint-item-meta">{{ relation.description || '暂无描述' }}</p>
        </div>
      </article>
    </div>

    <div v-else class="blueprint-empty">
      <div>
        <p class="blueprint-empty__title">暂无人际关系信息</p>
        <p class="blueprint-empty__desc">补充关系后，角色冲突和情感推进会更清晰。</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface RelationshipItem {
  character_from?: string
  character_to?: string
  relationship_type?: string
  description?: string
}

const props = defineProps<{
  data: { relationships?: RelationshipItem[] } | null
  editable?: boolean
}>()

const emit = defineEmits<{
  (e: 'edit', payload: { field: string; title: string; value: unknown }): void
}>()

const relationships = computed(() => props.data?.relationships || [])

const emitEdit = (field: string, title: string, value: unknown) => {
  if (!props.editable) return
  emit('edit', { field, title, value })
}
</script>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'RelationshipsSection',
})
</script>

<style scoped>
.relationships-section__card {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-4);
}

.relationships-section__pair {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 32px minmax(0, 1fr);
  align-items: center;
  gap: var(--md-spacing-3);
}

.relationships-section__person {
  display: flex;
  align-items: center;
  gap: var(--md-spacing-2);
  min-width: 0;
}

.relationships-section__person--end {
  justify-content: flex-end;
  text-align: right;
}

.relationships-section__person strong {
  min-width: 0;
  overflow: hidden;
  color: var(--md-on-surface);
  font-size: var(--md-body-medium);
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.relationships-section__avatar {
  width: 36px;
  height: 36px;
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  border: 1px solid var(--md-outline);
  border-radius: var(--md-radius-xs);
  background-color: var(--md-surface-container);
  color: var(--md-primary-dark);
  font-family: var(--md-font-display);
  font-weight: 700;
}

.relationships-section__avatar--secondary {
  color: var(--md-success-text);
}

.relationships-section__arrow {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  color: var(--md-on-surface-variant);
}

.relationships-section__arrow svg {
  width: 22px;
  height: 22px;
}

.relationships-section__type {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-2);
  padding-top: var(--md-spacing-4);
  border-top: 1px dashed var(--md-outline-variant);
}

@media (max-width: 560px) {
  .relationships-section__pair {
    grid-template-columns: minmax(0, 1fr);
  }

  .relationships-section__arrow {
    transform: rotate(90deg);
  }

  .relationships-section__person--end {
    justify-content: flex-start;
    text-align: left;
  }
}
</style>
