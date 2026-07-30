<!-- AIMETA P=空章节_未选择章节状态|R=空状态提示|NR=不含内容展示|E=component:ChapterEmpty|X=internal|A=空状态|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="chapter-empty" :class="{ 'chapter-empty--can-write': canGenerate }">
    <div v-if="canGenerate" class="chapter-empty__writer-guide">
      <!-- 1. 头部横幅 -->
      <header class="writer-guide__banner">
        <div class="writer-guide__banner-bg-ink"></div>
        <div class="writer-guide__banner-quill">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
            <path d="M20.24 12.24a6 6 0 0 0-8.49-8.49L5 10.5V19h8.5z" />
            <line x1="16" y1="8" x2="2" y2="22" />
            <line x1="17.5" y1="15" x2="9" y2="15" />
          </svg>
        </div>
        <h2 class="writer-guide__banner-title">故事，等待你落下第一笔</h2>
        <p class="writer-guide__banner-subtitle">
          这一章，将开启第 {{ chapterNumber }} 章的崭新情节，静候笔端波澜。
        </p>
      </header>

      <!-- 2. 大纲与看点 -->
      <div class="writer-guide__row">
        <!-- 本章目标 -->
        <section class="writer-guide__card writer-guide__card--goal">
          <h3 class="writer-guide__card-title">本章目标</h3>
          <p class="writer-guide__card-body">{{ resolvedGoal }}</p>
          <div class="writer-guide__card-icon-target">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
              <circle cx="12" cy="12" r="10" />
              <circle cx="12" cy="12" r="6" />
              <circle cx="12" cy="12" r="2" />
            </svg>
          </div>
        </section>

        <!-- 本章看点 -->
        <section class="writer-guide__card writer-guide__card--highlights">
          <h3 class="writer-guide__card-title">本章看点</h3>
          <ul class="writer-guide__bullet-list">
            <li v-for="(item, idx) in resolvedHighlights" :key="idx" class="writer-guide__bullet-item">
              {{ item }}
            </li>
          </ul>
        </section>
      </div>

      <!-- 3. 角色状态 -->
      <section class="writer-guide__card writer-guide__card--characters">
        <h3 class="writer-guide__card-title">角色状态</h3>
        <div class="writer-guide__char-grid">
          <div v-for="char in resolvedCharacterStates" :key="char.name" class="writer-guide__char-item">
            <div class="writer-guide__char-avatar" :style="{ background: getCharacterColorClass(char.name) }">
              {{ char.name.charAt(0) }}
            </div>
            <div class="writer-guide__char-info">
              <span class="writer-guide__char-name">{{ char.name }}</span>
              <span class="writer-guide__char-state">状态：{{ char.state }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- 4. 底部开始创作区 -->
      <footer class="writer-guide__footer">
        <div class="writer-guide__divider">
          <span class="writer-guide__divider-line"></span>
          <span class="writer-guide__divider-quill">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
              <path d="M20.24 12.24a6 6 0 0 0-8.49-8.49L5 10.5V19h8.5z" />
              <line x1="16" y1="8" x2="2" y2="22" />
            </svg>
          </span>
          <span class="writer-guide__divider-line"></span>
        </div>

        <button
          type="button"
          @click="$emit('generateChapter', chapterNumber)"
          :disabled="generatingChapter === chapterNumber"
          class="writer-guide__action-btn md-ripple"
        >
          <svg
            v-if="generatingChapter === chapterNumber"
            class="w-5 h-5 animate-spin"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fill-rule="evenodd"
              d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z"
              clip-rule="evenodd"
            ></path>
          </svg>
          <svg v-else class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20.24 12.24a6 6 0 0 0-8.49-8.49L5 10.5V19h8.5z" />
            <line x1="16" y1="8" x2="2" y2="22" />
          </svg>
          <span>{{ generatingChapter === chapterNumber ? '正在落笔创作...' : '开始创作本章' }}</span>
        </button>
        <span class="writer-guide__shortcut-tip">快捷键：Ctrl + Enter</span>
      </footer>
    </div>

    <section v-else class="chapter-locked">
      <div class="chapter-locked__message" role="status" aria-live="polite">
        <div class="chapter-locked__ornament" aria-hidden="true">
          <span class="chapter-locked__rule"></span>
          <span class="chapter-locked__diamond"></span>
          <span class="chapter-locked__lock">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
              <path d="M7 10V8a5 5 0 0110 0v2"></path>
              <rect x="5" y="10" width="14" height="10" rx="1"></rect>
              <path d="M12 14v3"></path>
              <path d="M11 14h2"></path>
            </svg>
          </span>
          <span class="chapter-locked__diamond"></span>
          <span class="chapter-locked__rule"></span>
        </div>

        <h3>故事还未抵达这一章</h3>
        <p>请先完成前面的待写章节，完成后本章将自动解锁。</p>
      </div>

      <button
        type="button"
        class="chapter-locked__action md-ripple"
        @click="$emit('selectChapter', lockedPrerequisiteChapterNumber ?? chapterNumber)"
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.8"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M20.24 12.24a6 6 0 0 0-8.49-8.49L5 10.5V19h8.5z"></path>
          <line x1="16" y1="8" x2="2" y2="22"></line>
          <line x1="17.5" y1="15" x2="9" y2="15"></line>
        </svg>
        <template v-if="lockedPrerequisiteChapterNumber && lockedPrerequisiteChapterTitle">
          前往第{{ lockedPrerequisiteChapterNumber }}章：<strong>{{ lockedPrerequisiteChapterTitle }}</strong>
        </template>
        <template v-else>
          前往待完成章节
        </template>
      </button>
    </section>
  </div>
</template>

<script setup lang="ts">
import type { ChapterOutline, NovelProject } from '@/api/novel'
import { readStringProperty } from '@/utils/novelContract'
import { computed, onMounted, onUnmounted } from 'vue'

interface Props {
  chapterNumber: number
  generatingChapter: number | null
  canGenerate: boolean
  lockedPrerequisiteChapterNumber?: number | null
  lockedPrerequisiteChapterTitle?: string | null
  chapterOutline?: ChapterOutline | null
  project?: NovelProject | null
}

const props = defineProps<Props>()

const emit = defineEmits(['generateChapter', 'selectChapter'])

const resolvedGoal = computed(() => {
  return props.chapterOutline?.goals?.trim() || props.chapterOutline?.summary?.trim() || '推动主线冲突，并让本章结尾为下一章留下明确推进抓手。'
})

const resolvedHighlights = computed(() => {
  if (props.chapterOutline?.highlights && props.chapterOutline.highlights.length > 0) {
    return props.chapterOutline.highlights
  }
  return [
    '承接前文剧情，展开关键冲突',
    '细腻的角色交互与情绪转换',
    '为下章预留悬念或故事抓手'
  ]
})

const resolvedCharacterStates = computed(() => {
  const statesMap = props.chapterOutline?.character_states || {}
  const result: Array<{ name: string; state: string }> = []

  if (Object.keys(statesMap).length > 0) {
    for (const [name, state] of Object.entries(statesMap)) {
      result.push({ name, state: String(state) })
    }
  }

  if (result.length === 0 && props.project?.blueprint?.characters) {
    const blueprintChars = props.project.blueprint.characters.slice(0, 4)
    for (const char of blueprintChars) {
      const name = readStringProperty(char, 'name')
      if (name) result.push({ name, state: '备战 / 待定' })
    }
  }

  if (result.length === 0) {
    return [
      { name: '主要角色', state: '状态待定' }
    ]
  }
  return result.slice(0, 4)
})

const getCharacterColorClass = (name: string) => {
  const colors = [
    'linear-gradient(135deg, #3f6c5d, #2b5043)', // 竹青
    'linear-gradient(135deg, #b83c32, #8c2820)', // 朱砂
    'linear-gradient(135deg, #c87b2e, #995c1e)', // 琥珀
    'linear-gradient(135deg, #5c6265, #43484a)', // 黛灰
    'linear-gradient(135deg, #2a4d69, #1e354a)', // 绀蓝
  ]
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash)
  }
  const index = Math.abs(hash) % colors.length
  return colors[index]
}

const onKeydown = (e: KeyboardEvent) => {
  if (props.canGenerate && (e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    if (props.generatingChapter !== props.chapterNumber) {
      emit('generateChapter', props.chapterNumber)
    }
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})
</script>

<style scoped>
.chapter-empty {
  display: flex;
  min-height: 100%;
  align-items: center;
  justify-content: center;
  padding: clamp(40px, 9vh, 112px) var(--md-spacing-6);
}

.chapter-empty--can-write {
  align-items: flex-start !important;
  justify-content: center !important;
  padding-top: clamp(24px, 5vh, 48px);
}

/* ==========================================================================
   待写章节 - 正文向导面板布局与样式 (古籍笺纸双色套印风格)
   ========================================================================== */
.chapter-empty__writer-guide {
  width: 100%;
  max-width: 900px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-5);
  animation: guide-fade-in 0.4s cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes guide-fade-in {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 1. 头部横幅 */
.writer-guide__banner {
  position: relative;
  overflow: hidden;
  padding: var(--md-spacing-6) var(--md-spacing-8);
  border: 1.5px solid var(--md-outline-variant);
  border-radius: var(--md-radius-sm);
  background: linear-gradient(135deg, var(--md-surface-container-high) 0%, var(--md-surface-container) 100%);
  box-shadow: var(--md-elevation-1);
}

/* 暗纹水墨背景 */
.writer-guide__banner-bg-ink {
  position: absolute;
  inset: 0;
  opacity: 0.04;
  pointer-events: none;
  background-image: repeating-linear-gradient(45deg, var(--md-on-surface) 0px, var(--md-on-surface) 1px, transparent 1px, transparent 10px);
}

.writer-guide__banner-quill {
  position: absolute;
  right: 48px;
  top: 50%;
  transform: translateY(-50%);
  width: 80px;
  height: 80px;
  color: var(--md-outline);
  opacity: 0.14;
  pointer-events: none;
  transition: transform 0.6s cubic-bezier(0.22, 1, 0.36, 1), color 0.6s, opacity 0.6s;
}

.writer-guide__banner:hover .writer-guide__banner-quill {
  transform: translateY(-50%) rotate(-12deg) scale(1.1);
  color: var(--md-secondary);
  opacity: 0.28;
}

.writer-guide__banner-title {
  margin: 0 0 10px 0;
  font-family: var(--md-font-serif);
  font-size: 28px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: var(--md-secondary);
}

.writer-guide__banner-subtitle {
  margin: 0;
  font-family: var(--md-font-serif);
  font-size: var(--md-title-medium);
  line-height: 1.6;
  color: var(--md-on-surface-variant);
}

/* 2. 双列布局 */
.writer-guide__row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--md-spacing-5);
}

.writer-guide__card {
  position: relative;
  overflow: hidden;
  padding: var(--md-spacing-5) var(--md-spacing-6);
  border: 1.5px solid var(--md-outline-variant);
  border-radius: var(--md-radius-xs);
  background-color: var(--md-surface-container-low);
  box-shadow: 1px 1px 0px rgba(0, 0, 0, 0.05);
}

.writer-guide__card-title {
  margin: 0 0 var(--md-spacing-4) 0;
  font-family: var(--md-font-kai);
  font-size: var(--md-label-large);
  font-weight: 700;
  letter-spacing: 0.05em;
  color: var(--md-primary);
  border-left: 3.5px solid var(--md-secondary);
  padding-left: var(--md-spacing-2);
  line-height: 1.2;
}

.writer-guide__card-body {
  margin: 0;
  font-family: var(--md-font-serif);
  font-size: var(--md-body-medium);
  line-height: 1.8;
  color: var(--md-on-surface-variant);
}

.writer-guide__card-icon-target {
  position: absolute;
  right: 16px;
  bottom: 8px;
  width: 48px;
  height: 48px;
  color: var(--md-outline);
  opacity: 0.08;
  pointer-events: none;
}

/* 本章看点列表 */
.writer-guide__bullet-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.writer-guide__bullet-item {
  position: relative;
  padding-left: 16px;
  font-family: var(--md-font-serif);
  font-size: var(--md-body-medium);
  line-height: 1.6;
  color: var(--md-on-surface-variant);
}

.writer-guide__bullet-item::before {
  content: '·';
  position: absolute;
  left: 0;
  top: -2px;
  color: var(--md-secondary);
  font-weight: bold;
  font-size: 1.5rem;
}

/* 3. 角色状态 */
.writer-guide__char-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--md-spacing-4);
  margin-top: var(--md-spacing-3);
}

.writer-guide__char-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: var(--md-spacing-3);
  border-radius: var(--md-radius-xs);
  background-color: var(--md-surface-container);
  border: 1px dashed var(--md-outline-variant);
}

.writer-guide__char-avatar {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff !important;
  font-family: var(--md-font-kai);
  font-weight: bold;
  font-size: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
  flex-shrink: 0;
}

.writer-guide__char-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.writer-guide__char-name {
  font-family: var(--md-font-serif);
  font-size: var(--md-body-medium);
  font-weight: 600;
  color: var(--md-on-surface);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.writer-guide__char-state {
  font-family: var(--md-font-serif);
  font-size: var(--md-body-small);
  color: var(--md-on-surface-variant);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 4. 底部落笔区 */
.writer-guide__footer {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-top: var(--md-spacing-4);
}

.writer-guide__divider {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 18px;
  margin-bottom: var(--md-spacing-6);
}

.writer-guide__divider-line {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--md-outline-variant), transparent);
}

.writer-guide__divider-quill {
  color: var(--md-outline-variant);
  display: flex;
  align-items: center;
}

.writer-guide__divider-quill svg {
  width: 20px;
  height: 20px;
}

.writer-guide__action-btn {
  display: inline-flex;
  min-height: 54px;
  min-width: 280px;
  align-items: center;
  justify-content: center;
  gap: var(--md-spacing-3);
  padding: 0 var(--md-spacing-8);
  border: 3px double var(--chapter-locked-action-border);
  border-radius: var(--md-radius-xs);
  background: color-mix(in srgb, var(--md-secondary) 6%, var(--md-surface));
  color: var(--md-secondary);
  font-family: var(--md-font-serif);
  font-size: var(--md-title-medium);
  font-weight: 600;
  letter-spacing: 0.05em;
  box-shadow: 2px 2px 0 var(--md-outline);
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.22, 1, 0.36, 1);
}

.writer-guide__action-btn:hover:not(:disabled) {
  border-color: var(--md-secondary);
  color: #ffffff;
  background-color: var(--md-secondary);
  box-shadow: 3px 3px 0 var(--md-outline);
  transform: translate(-1px, -1px);
}

.writer-guide__action-btn:active:not(:disabled) {
  box-shadow: 0 0 0 var(--md-outline);
  transform: translate(1px, 1px);
}

.writer-guide__action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.writer-guide__action-btn svg {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.writer-guide__shortcut-tip {
  margin-top: 8px;
  font-size: var(--md-body-small);
  font-family: var(--md-font-serif);
  color: var(--md-on-surface-variant);
  opacity: 0.7;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .writer-guide__row {
    grid-template-columns: 1fr;
    gap: var(--md-spacing-4);
  }

  .writer-guide__banner {
    padding: var(--md-spacing-5) var(--md-spacing-6);
  }

  .writer-guide__banner-quill {
    display: none;
  }

  .writer-guide__banner-title {
    font-size: 22px;
  }
}

.m3-empty-card {
  border-radius: var(--md-radius-sm) !important;
  border-color: var(--md-outline) !important;
  background-color: var(--md-surface-dim) !important;
  box-shadow: 2px 2px 0px rgba(28, 32, 34, 0.08) !important;
}

.m3-empty-icon-wrapper {
  background-color: var(--md-surface-container) !important;
}

.m3-empty-icon {
  color: var(--md-on-surface-variant) !important;
}

.chapter-locked {
  --chapter-locked-accent: color-mix(in srgb, var(--md-on-surface) 74%, var(--md-warning) 26%);
  --chapter-locked-text: color-mix(in srgb, var(--md-on-surface) 86%, var(--md-warning) 14%);
  --chapter-locked-muted: color-mix(in srgb, var(--md-on-surface-variant) 70%, var(--md-on-surface) 30%);
  --chapter-locked-line: color-mix(in srgb, var(--chapter-locked-accent) 58%, transparent);
  --chapter-locked-glow: color-mix(in srgb, var(--md-warning) 26%, transparent);
  --chapter-locked-action-bg: color-mix(in srgb, var(--md-surface) 76%, transparent);
  --chapter-locked-action-hover-bg: color-mix(in srgb, var(--md-warning-container) 28%, var(--md-surface));
  --chapter-locked-action-border: color-mix(in srgb, var(--chapter-locked-accent) 76%, var(--md-outline));
  --chapter-locked-action-shadow: color-mix(in srgb, var(--chapter-locked-accent) 38%, transparent);
  --chapter-locked-action-hover-shadow: color-mix(in srgb, var(--chapter-locked-accent) 44%, transparent);

  width: min(520px, 100%);
  margin: auto;
  text-align: center;
  color: var(--md-on-surface);
}

:root:not([data-theme='dark']) .chapter-locked,
:root[data-theme='light'] .chapter-locked {
  --chapter-locked-accent: #c8a875;
  --chapter-locked-text: #9e8662;
  --chapter-locked-muted: #667172;
  --chapter-locked-line: rgba(200, 168, 117, 0.46);
  --chapter-locked-glow: rgba(200, 168, 117, 0.16);
  --chapter-locked-action-bg: rgba(250, 246, 237, 0.64);
  --chapter-locked-action-hover-bg: rgba(253, 246, 236, 0.92);
  --chapter-locked-action-border: #cdbb9c;
  --chapter-locked-action-shadow: rgba(200, 168, 117, 0.3);
  --chapter-locked-action-hover-shadow: rgba(200, 168, 117, 0.4);
}

.chapter-locked__ornament {
  display: grid;
  grid-template-columns: minmax(56px, 86px) 10px 74px 10px minmax(56px, 86px);
  align-items: center;
  justify-content: center;
  gap: 14px;
  margin-bottom: var(--md-spacing-5);
}

.chapter-locked__rule {
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--chapter-locked-line));
}

.chapter-locked__rule:last-child {
  transform: scaleX(-1);
}

.chapter-locked__diamond {
  width: 7px;
  height: 7px;
  border: 1px solid var(--chapter-locked-accent);
  transform: rotate(45deg);
}

.chapter-locked__lock {
  position: relative;
  display: grid;
  width: 74px;
  height: 74px;
  place-items: center;
  color: var(--chapter-locked-accent);
}

.chapter-locked__lock::before {
  position: absolute;
  inset: -22px;
  border-radius: 50%;
  background: radial-gradient(circle, var(--chapter-locked-glow) 0%, transparent 68%);
  content: '';
}

.chapter-locked__lock svg {
  position: relative;
  width: 44px;
  height: 44px;
  color: var(--chapter-locked-accent);
}

.chapter-locked h3 {
  margin: 0 0 var(--md-spacing-4);
  color: var(--chapter-locked-text);
  font-family: var(--md-font-serif);
  font-size: 36px;
  font-weight: 600;
  letter-spacing: 0;
  line-height: 1.25;
}

.chapter-locked p {
  margin: 0;
  color: var(--chapter-locked-muted);
  font-family: var(--md-font-serif);
  font-size: var(--md-title-medium);
  font-weight: 500;
  line-height: 1.8;
  letter-spacing: 0;
}

.chapter-locked__action {
  display: inline-flex;
  min-height: 52px;
  min-width: min(360px, 100%);
  align-items: center;
  justify-content: center;
  gap: var(--md-spacing-3);
  margin-top: var(--md-spacing-8);
  padding: 0 var(--md-spacing-6);
  border: 3px double var(--chapter-locked-action-border);
  border-radius: var(--md-radius-xs);
  background: var(--chapter-locked-action-bg);
  color: var(--chapter-locked-text);
  font-family: var(--md-font-serif);
  font-size: var(--md-title-medium);
  font-weight: 600;
  letter-spacing: 0;
  box-shadow: 2px 2px 0 var(--chapter-locked-action-shadow);
  cursor: pointer;
  transition:
    background-color var(--md-duration-short) var(--md-easing-standard),
    border-color var(--md-duration-short) var(--md-easing-standard),
    color var(--md-duration-short) var(--md-easing-standard),
    transform var(--md-duration-short) var(--md-easing-standard),
    box-shadow var(--md-duration-short) var(--md-easing-standard);
}

.chapter-locked__action:hover {
  border-color: var(--chapter-locked-accent);
  color: var(--chapter-locked-accent);
  background-color: var(--chapter-locked-action-hover-bg);
  box-shadow: 3px 3px 0 var(--chapter-locked-action-hover-shadow);
  transform: translate(-1px, -1px);
}

.chapter-locked__action:active {
  box-shadow: 0 0 0 var(--chapter-locked-action-shadow);
  transform: translate(1px, 1px);
}

.chapter-locked__action:focus-visible {
  outline: 2px solid var(--chapter-locked-accent);
  outline-offset: 3px;
}

.chapter-locked__action svg {
  width: 22px;
  height: 22px;
  flex: 0 0 auto;
}

@media (max-width: 640px) {
  .chapter-empty {
    padding: var(--md-spacing-8) var(--md-spacing-4);
  }

  .chapter-locked__ornament {
    grid-template-columns: 52px 8px 62px 8px 52px;
    gap: 10px;
  }

  .chapter-locked h3 {
    font-size: 27px;
  }

  .chapter-locked p,
  .chapter-locked__action {
    font-size: var(--md-title-small);
  }
}
</style>
