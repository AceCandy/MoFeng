<!-- AIMETA P=历史版本预览面板_多版本平铺查阅|R=版本卡片_详情入口_应用版本|NR=不含版本数据来源与tab切换|E=component:ChapterVersionsPanel|X=internal|A=版本预览|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="writing-workspace__versions-panel flex flex-col h-full overflow-hidden">
    <div class="flex-1 flex min-h-0 divide-x" style="border-color: var(--md-outline-variant)">
      <!-- 左侧版本卡片列表 -->
      <div class="w-64 overflow-y-auto pr-4 flex flex-col gap-3">
        <div
          v-for="(version, index) in availableVersions"
          :key="`version-tab-${index}`"
          class="writing-workspace__version-tab-card"
          :class="{ 'is-active': previewVersionIndex === index }"
          @click="previewVersionIndex = index"
        >
          <div class="flex items-center justify-between">
            <span class="version-label">版本 {{ index + 1 }}</span>
            <span class="version-badge">{{ version.style || '标准' }}</span>
          </div>
          <p class="version-preview-text line-clamp-2">
            {{ cleanVersionContent(version.content).substring(0, 50) }}...
          </p>
          <div class="version-meta">
            {{ countNonWhitespaceChars(version.content) }} 字
          </div>
        </div>
      </div>

      <!-- 右侧选定版本正文大卷预览 -->
      <div class="flex-1 overflow-y-auto pl-6 flex flex-col justify-between">
        <div class="flex-1 whitespace-pre-wrap leading-relaxed prose max-w-none text-justify" style="color: var(--md-on-surface); font-family: var(--md-font-family);">
          <p v-for="(paragraph, pIndex) in previewVersionParagraphs" :key="`para-${pIndex}`" class="mb-4">
            {{ paragraph }}
          </p>
        </div>
        <div class="mt-6 pt-4 border-t flex items-center justify-between" style="border-top-color: var(--md-outline-variant)">
          <span class="text-sm md-on-surface-variant font-medium">
            此版本共 {{ previewVersionWordCount }} 字，风格为【{{ availableVersions[previewVersionIndex]?.style || '标准' }}】
          </span>
          <div class="flex items-center gap-2">
            <button
              type="button"
              class="md-btn md-btn-outlined md-ripple"
              @click="emit('showVersionDetail', previewVersionIndex)"
            >
              版本详情
            </button>
            <button
              type="button"
              class="md-btn md-btn-filled md-ripple flex items-center gap-2"
              style="background-color: var(--md-primary); color: var(--md-on-primary)"
              :disabled="isCurrentVersion(previewVersionIndex)"
              @click="selectVersionFromTab(previewVersionIndex)"
            >
              <span>{{ isCurrentVersion(previewVersionIndex) ? '当前正在使用' : '应用此版本为当前正文' }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { ChapterVersion } from '@/api/novel'
import { cleanVersionContent } from '@/utils/chapter'
import { countNonWhitespaceChars } from '@/utils/text'
import { globalAlert } from '@/composables/useAlert'

interface Props {
  availableVersions: ChapterVersion[]
  selectedChapterNumber: number | null
  resolvedContent: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (event: 'showVersionDetail', versionIndex: number): void
  (event: 'editChapter', payload: { chapterNumber: number; content: string }): void
  (event: 'switchToContent'): void
}>()

const previewVersionIndex = ref<number>(0)

// 切换章节时回到首个版本预览
watch(
  () => props.selectedChapterNumber,
  () => {
    previewVersionIndex.value = 0
  },
)

// 候选版本变动时校验预览索引越界
watch(
  () => props.availableVersions,
  (newVersions) => {
    if (previewVersionIndex.value >= newVersions.length) {
      previewVersionIndex.value = 0
    }
  },
  { deep: true },
)

const previewVersionResolvedContent = computed(() => {
  const version = props.availableVersions[previewVersionIndex.value]
  return version ? cleanVersionContent(version.content) : ''
})

const previewVersionParagraphs = computed(() => {
  if (!previewVersionResolvedContent.value.trim()) return []
  return previewVersionResolvedContent.value
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter(Boolean)
})

const previewVersionWordCount = computed(() => {
  return countNonWhitespaceChars(previewVersionResolvedContent.value)
})

const selectVersionFromTab = (index: number) => {
  const version = props.availableVersions[index]
  if (!version || props.selectedChapterNumber === null) return
  const cleanContent = cleanVersionContent(version.content)
  emit('editChapter', {
    chapterNumber: props.selectedChapterNumber,
    content: cleanContent,
  })
  globalAlert.showToast('成功应用所选历史版本！', 'success')
  emit('switchToContent') // 自动切回正文
}

const isCurrentVersion = (index: number) => {
  const version = props.availableVersions[index]
  if (!version) return false
  return cleanVersionContent(version.content).trim() === props.resolvedContent.trim()
}
</script>

<style scoped>
/* ==========================================================================
   历史版本预览面板
   ========================================================================== */
.writing-workspace__versions-panel {
  height: 100%;
}

.writing-workspace__version-tab-card {
  padding: var(--md-spacing-3);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-xs);
  background-color: rgba(28, 32, 34, 0.01);
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease,
    transform 0.2s ease;
}

.writing-workspace__version-tab-card:hover {
  border-color: var(--md-outline);
  background-color: var(--md-surface-container-low);
  transform: translateX(2px);
}

.writing-workspace__version-tab-card.is-active {
  border-color: var(--md-secondary);
  background-color: rgba(184, 60, 50, 0.02);
  box-shadow: inset 2px 0 0 var(--md-secondary);
}

.writing-workspace__version-tab-card .version-label {
  font-family: var(--md-font-serif);
  font-weight: 700;
  font-size: 13.5px;
  color: var(--md-primary-dark);
}

.writing-workspace__version-tab-card.is-active .version-label {
  color: var(--md-secondary);
}

.writing-workspace__version-tab-card .version-badge {
  font-size: 10.5px;
  padding: 1px 4px;
  border-radius: 2px;
  border: 1px solid var(--md-outline-variant);
  background-color: var(--md-surface-container);
  color: var(--md-on-surface-variant);
}

.version-preview-text {
  margin: var(--md-spacing-2) 0 4px;
  color: var(--md-on-surface-variant);
  font-size: 12px;
  line-height: 1.45;
}

.version-meta {
  color: var(--md-on-surface-variant);
  font-size: 11px;
  opacity: 0.8;
}
</style>
