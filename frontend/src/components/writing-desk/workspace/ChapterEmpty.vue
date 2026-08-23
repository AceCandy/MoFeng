<!-- AIMETA P=章节前置条件锁定状态|R=锁定说明_跳转首个未完成章节|NR=不触发生成或工作流命令|E=component:ChapterEmpty|X=internal|A=locked-state|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="chapter-empty">
    <section class="chapter-locked">
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
        @click="emit('selectChapter', lockedPrerequisiteChapterNumber ?? chapterNumber)"
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
        <template v-else>前往待完成章节</template>
      </button>
    </section>
  </div>
</template>

<script setup lang="ts">
interface Props {
  chapterNumber: number
  lockedPrerequisiteChapterNumber?: number | null
  lockedPrerequisiteChapterTitle?: string | null
}

defineProps<Props>()
const emit = defineEmits<{
  (event: 'selectChapter', chapterNumber: number): void
}>()
</script>

<style scoped>
.chapter-empty {
  display: flex;
  min-height: 100%;
  align-items: center;
  justify-content: center;
  padding: clamp(40px, 9vh, 112px) var(--md-spacing-6);
}

.chapter-locked {
  --chapter-locked-accent: #c8a875;
  --chapter-locked-text: #9e8662;
  --chapter-locked-muted: #667172;
  --chapter-locked-line: rgba(200, 168, 117, 0.46);
  --chapter-locked-glow: rgba(200, 168, 117, 0.16);
  --chapter-locked-action-bg: rgba(250, 246, 237, 0.64);
  --chapter-locked-action-hover-bg: rgba(253, 246, 236, 0.92);
  --chapter-locked-action-border: #cdbb9c;
  width: min(520px, 100%);
  margin: auto;
  text-align: center;
  color: var(--md-on-surface);
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
  letter-spacing: 0.05em;
  line-height: 1.25;
}

.chapter-locked p {
  margin: 0;
  color: var(--chapter-locked-muted);
  font-family: var(--md-font-serif);
  font-size: var(--md-title-medium);
  font-weight: 500;
  line-height: 1.8;
  letter-spacing: 0.03em;
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
  letter-spacing: 0.03em;
  box-shadow: var(--md-elevation-paper-1);
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
  box-shadow: var(--md-elevation-paper-2);
  transform: translate(-1px, -1px);
}

.chapter-locked__action:active {
  box-shadow: none;
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
