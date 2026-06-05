<!-- AIMETA P=空章节_未选择章节状态|R=空状态提示|NR=不含内容展示|E=component:ChapterEmpty|X=internal|A=空状态|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="chapter-empty">
    <div v-if="canGenerate" class="md-card md-card-outlined p-8 text-center max-w-md m3-empty-card">
      <div class="w-16 h-16 flex items-center justify-center mx-auto mb-4 m3-empty-icon-wrapper">
        <svg class="w-7 h-7 m3-empty-icon" fill="currentColor" viewBox="0 0 20 20">
          <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"></path>
        </svg>
      </div>
      <h3 class="md-title-medium font-semibold mb-2">开始创作</h3>

      <p class="md-body-medium md-on-surface-variant mb-4">点击"开始创作"按钮生成这个章节</p>
      <button
        type="button"
        @click="$emit('generateChapter', chapterNumber)"
        :disabled="generatingChapter === chapterNumber"
        class="md-btn md-btn-filled md-ripple flex items-center gap-2 mx-auto disabled:opacity-50"
      >
        <svg
          v-if="generatingChapter === chapterNumber"
          class="w-4 h-4 animate-spin"
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path
            fill-rule="evenodd"
            d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z"
            clip-rule="evenodd"
          ></path>
        </svg>
        <svg v-else class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
          <path
            d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"
          ></path>
        </svg>
        {{ generatingChapter === chapterNumber ? '生成中...' : '开始创作' }}
      </button>
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
interface Props {
  chapterNumber: number
  generatingChapter: number | null
  canGenerate: boolean
  lockedPrerequisiteChapterNumber?: number | null
  lockedPrerequisiteChapterTitle?: string | null
}

defineProps<Props>()

defineEmits(['generateChapter', 'selectChapter'])
</script>

<style scoped>
.chapter-empty {
  display: flex;
  min-height: 100%;
  align-items: center;
  justify-content: center;
  padding: clamp(40px, 9vh, 112px) var(--md-spacing-6);
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
