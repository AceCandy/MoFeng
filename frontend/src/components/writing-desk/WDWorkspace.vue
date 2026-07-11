<!-- AIMETA P=写作台工作区_主编辑区域|R=章节编辑_生成|NR=不含侧边栏|E=component:WDWorkspace|X=ui|A=工作区|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <section class="writing-workspace">
    <div class="md-card md-card-outlined writing-workspace__panel">
      <!-- 章节工作区头部 -->
      <div v-if="selectedChapterNumber !== null" class="writing-workspace__header">
        <div class="writing-workspace__header-row">
          <div class="writing-workspace__chapter-meta">
            <div class="writing-workspace__chapter-title-line">
              <h2 class="md-title-large font-semibold writing-workspace__chapter-no">
                第{{ selectedChapterNumber }}章
              </h2>
              <Tooltip :text="chapterTitleTooltipText" :show-delay="150">
                <button
                  type="button"
                  class="writing-workspace__title-copy md-title-medium md-on-surface"
                  @click="copySelectedChapterTitle"
                  @mouseleave="resetChapterTitleTooltip"
                >
                  {{ selectedChapterOutline?.title || '未知标题' }}
                </button>
              </Tooltip>
              <span
                class="writing-workspace__status-tag"
                :class="`writing-workspace__status-tag--${chapterStatusTone}`"
              >
                {{ chapterStatusLabel }}
              </span>
              <span class="writing-workspace__chapter-inline-meta md-label-small md-on-surface-variant">
                {{ chapterInlineMeta }}
              </span>
            </div>
            <p class="writing-workspace__summary md-body-small md-on-surface-variant">
              {{ selectedChapterOutline?.summary || '暂无章节描述' }}
            </p>
          </div>
          <aside
            v-if="shouldShowChapterToolbar"
            class="writing-workspace__toolbar"
            role="toolbar"
            aria-label="章节操作"
          >
            <div v-if="isFinalizedSuccessful" class="writing-workspace__toolbar-row writing-workspace__toolbar-row--utility">
              <div class="writing-workspace__toolbar-group writing-workspace__toolbar-group--utility">
                <button
                  type="button"
                  @click="copySelectedChapterContent"
                  :disabled="!hasSelectedChapterContent"
                  class="md-btn md-btn-text md-ripple writing-workspace__tool-btn writing-workspace__tool-btn--ghost disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  复制
                </button>
                <button
                  type="button"
                  @click="exportContentAsTxt"
                  :disabled="!isChapterContentView"
                  class="md-btn md-btn-text md-ripple writing-workspace__tool-btn writing-workspace__tool-btn--ghost disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  导出
                </button>
              </div>
            </div>

            <div v-if="isDraftWaitingConfirm" class="writing-workspace__toolbar-row writing-workspace__toolbar-row--primary">
              <div class="writing-workspace__toolbar-group writing-workspace__toolbar-group--emphasis">
              <button
                type="button"
                @click="openEditModal"
                :disabled="!hasSelectedChapterContent"
                class="md-btn md-btn-outlined md-ripple writing-workspace__tool-btn writing-workspace__tool-btn--secondary writing-workspace__tool-btn--hero disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span class="writing-workspace__label-full">编辑草稿</span>
                <span class="writing-workspace__label-short">编辑</span>
              </button>

              <button
                v-if="isDraftWaitingConfirm && hasSelectedChapterContent"
                type="button"
                @click="$emit('confirmVersionSelection', {})"
                class="md-btn md-btn-filled md-ripple writing-workspace__tool-btn writing-workspace__tool-btn--primary writing-workspace__tool-btn--hero"
              >
                <span class="writing-workspace__label-full">确认定稿</span>
                <span class="writing-workspace__label-short">定稿</span>
              </button>

              <div ref="aiMenuRef" class="writing-workspace__ai-menu">
                <button
                  ref="aiMenuTriggerRef"
                  type="button"
                  @click="toggleAiMenu"
                  :disabled="isAiMenuDisabled"
                  class="md-btn md-btn-tonal md-ripple writing-workspace__tool-btn writing-workspace__tool-btn--primary writing-workspace__tool-btn--hero disabled:opacity-50 disabled:cursor-not-allowed"
                  :aria-expanded="showAiMenu ? 'true' : 'false'"
                  aria-haspopup="menu"
                  :aria-controls="aiMenuId"
                >
                  <span class="writing-workspace__label-full">AI优化</span>
                  <span class="writing-workspace__label-short">AI</span>
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M19 9l-7 7-7-7"
                    ></path>
                  </svg>
                </button>

                <div
                  v-if="showAiMenu"
                  :id="aiMenuId"
                  ref="aiMenuPanelRef"
                  class="writing-workspace__ai-menu-panel"
                  role="menu"
                  tabindex="-1"
                  @keydown="handleAiMenuKeydown"
                >
                  <button
                    :ref="(el) => registerAiMenuItemRef(el, 0)"
                    type="button"
                    role="menuitem"
                    @click="handleLayeredOptimize"
                    :disabled="!hasSelectedChapterContent"
                    class="writing-workspace__ai-menu-item disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    分层优化
                  </button>
                  <button
                    :ref="(el) => registerAiMenuItemRef(el, 1)"
                    type="button"
                    role="menuitem"
                    @click="handlePolishContent"
                    :disabled="!hasSelectedChapterContent"
                    class="writing-workspace__ai-menu-item disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    润色正文
                  </button>
                  <button
                    :ref="(el) => registerAiMenuItemRef(el, 2)"
                    type="button"
                    role="menuitem"
                    @click="handleAdjustRhythm"
                    :disabled="!hasSelectedChapterContent"
                    class="writing-workspace__ai-menu-item disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    调整节奏
                  </button>
                  <button
                    :ref="(el) => registerAiMenuItemRef(el, 3)"
                    type="button"
                    role="menuitem"
                    @click="handleRewriteStyle"
                    :disabled="!hasSelectedChapterContent"
                    class="writing-workspace__ai-menu-item disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    改写风格
                  </button>
                </div>
              </div>
              </div>
            </div>
          </aside>
        </div>
      </div>

      <div
        v-if="selectedChapter?.generation_status === 'successful' && hasSelectedChapterContent"
        class="writing-workspace__tabs-row"
      >
        <nav class="writing-workspace__tabs" aria-label="章节工作台分区">
          <button
            type="button"
            class="writing-workspace__tab-btn md-ripple"
            :class="{ 'is-active': activeTab === 'content' }"
            @click="activeTab = 'content'"
          >
            <span class="tab-badge">🎴</span>
            <span>章节正文</span>
          </button>
          <button
            type="button"
            class="writing-workspace__tab-btn md-ripple"
            :class="{ 'is-active': activeTab === 'versions' }"
            @click="activeTab = 'versions'"
          >
            <span class="tab-badge">📜</span>
            <span>查看版本 ({{ availableVersions.length }})</span>
          </button>
          <button
            type="button"
            class="writing-workspace__tab-btn md-ripple"
            :class="{ 'is-active': activeTab === 'evaluation' }"
            @click="activeTab = 'evaluation'"
          >
            <span class="tab-badge">⚖️</span>
            <span>AI 评审反馈</span>
          </button>
        </nav>
      </div>

      <!-- 章节内容展示区 -->
      <div class="writing-workspace__content">
          <ChapterReaderBar
            v-if="isFinalizedSuccessful"
            :status="readerStatus"
            :isBrowserFallback="readerIsBrowserFallback"
            :currentParagraphIndex="readerCurrentParagraphIndex"
            :paragraphCount="readerParagraphCount"
            :voiceURI="readerVoiceURI"
            :rate="readerRate"
            :voiceOptions="readerVoiceOptions"
            :rateOptions="READER_RATE_OPTIONS"
            @start="handleReaderStart"
            @play-pause="handleReaderPlayPause"
            @reset="handleReaderReset"
            @voice-change="chapterReader.setVoiceURI"
            @rate-change="chapterReader.setRate"
            @preview-voice="chapterReader.previewVoice"
          />
          <div class="writing-workspace__body h-full">
            <ChapterGenerating
              v-if="shouldShowDraftTraceReplay"
              class="writing-workspace__trace-replay"
              v-bind="draftTraceReplayProps"
            />

            <!-- 1. 章节正文 Tab 分支 -->
            <component
              v-if="activeTab === 'content' || selectedChapter?.generation_status !== 'successful' || !hasSelectedChapterContent"
              ref="bodyComponentRef"
              :is="currentComponent"
              v-bind="currentComponentProps"
              @hideVersionSelector="$emit('hideVersionSelector')"
              @update:selectedVersionIndex="$emit('update:selectedVersionIndex', $event)"
              @showVersionDetail="$emit('showVersionDetail', $event)"
              @confirmVersionSelection="$emit('confirmVersionSelection', $event)"
              @generateChapter="$emit('generateChapter', $event)"
              @retryFromNode="$emit('retryFromNode', $event)"
              @selectChapter="$emit('selectChapter', $event)"
              @showVersionSelector="$emit('showVersionSelector')"
              @regenerateChapter="$emit('regenerateChapter')"
              @evaluateChapter="$emit('evaluateChapter')"
              @showEvaluationDetail="$emit('showEvaluationDetail')"
            />

            <!-- 2. 历史版本多维平铺查阅面板 -->
            <div v-else-if="activeTab === 'versions'" class="writing-workspace__versions-panel flex flex-col h-full overflow-hidden">
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

            <!-- 3. AI 章节评审反馈面板 -->
            <div v-else-if="activeTab === 'evaluation'" class="writing-workspace__evaluation-panel flex flex-col h-full overflow-y-auto">
              <div v-if="selectedChapter?.evaluation" class="space-y-6">
                <!-- 情况 A：解析 JSON 成功 -->
                <template v-if="parsedEvaluation">
                  <!-- 格式 1: 含有 best_choice 或 evaluation 的多版本评阅 -->
                  <div v-if="parsedEvaluation.best_choice || parsedEvaluation.evaluation" class="space-y-6">
                    <div v-if="parsedEvaluation.best_choice" class="md-card md-card-filled p-4 m3-eval-best-choice-card">
                      <p class="md-title-small font-semibold m3-eval-best-choice-title">🏆 最佳推荐：版本 {{ parsedEvaluation.best_choice }}</p>
                      <p class="md-body-small mt-2 m3-eval-best-choice-reason" style="color: var(--md-on-surface)">
                        {{ parsedEvaluation.reason_for_choice }}
                      </p>
                    </div>
                    <div class="space-y-4">
                      <div v-for="item in sortedEvaluationEntries" :key="item.key" class="md-card md-card-outlined p-4 m3-eval-version-card" style="border: 1px solid var(--md-outline); background: var(--md-surface-container-low)">
                        <h5 class="md-title-medium font-semibold mb-2" style="font-family: var(--md-font-serif); color: var(--md-secondary)">
                          版本 {{ item.versionNumber }} 评估
                        </h5>
                        <div class="prose prose-sm max-w-none md-on-surface space-y-3">
                          <div v-if="item.result.overall_review">
                            <p class="font-semibold" style="color: var(--md-on-surface)">综合评价:</p>
                            <p style="color: var(--md-on-surface-variant)">{{ item.result.overall_review }}</p>
                          </div>
                          <div v-if="item.result.pros && item.result.pros.length">
                            <p class="font-semibold" style="color: var(--md-on-surface)">优点:</p>
                            <ul class="list-disc pl-5 space-y-1" style="color: var(--md-on-surface-variant)">
                              <li v-for="(pro, i) in item.result.pros" :key="`pro-${i}`">{{ pro }}</li>
                            </ul>
                          </div>
                          <div v-if="item.result.cons && item.result.cons.length">
                            <p class="font-semibold" style="color: var(--md-on-surface)">缺点:</p>
                            <ul class="list-disc pl-5 space-y-1" style="color: var(--md-on-surface-variant)">
                              <li v-for="(con, i) in item.result.cons" :key="`con-${i}`">{{ con }}</li>
                            </ul>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- 格式 2: 含有 scores 或 feedback/decision 的评分评阅 -->
                  <div v-else-if="parsedEvaluation.scores || parsedEvaluation.feedback || parsedEvaluation.decision" class="space-y-6">
                    <div v-if="parsedEvaluation.decision" class="md-card md-card-filled p-4 m3-eval-best-choice-card">
                      <p class="md-title-small font-semibold m3-eval-best-choice-title">⚖️ 评阅大案决策</p>
                      <p class="md-body-small mt-2" style="color: var(--md-on-surface)">{{ parsedEvaluation.decision }}</p>
                    </div>

                    <div v-if="parsedEvaluation.scores" class="grid grid-cols-2 md:grid-cols-3 gap-4">
                      <div v-for="(score, key) in parsedEvaluation.scores" :key="key" class="writing-workspace__evaluation-card p-4" style="border: 1px solid var(--md-outline); background: var(--md-surface-container-low)">
                        <h5 class="dimension-title" style="font-family: var(--md-font-serif); font-weight: bold; color: var(--md-secondary)">
                          <span class="dimension-mark">✒️</span> {{ key }}
                        </h5>
                        <p class="dimension-desc md-display-small font-semibold mt-2" style="color: var(--md-primary)">
                          {{ score }} <span class="text-sm font-normal text-muted" style="color: var(--md-on-surface-variant)">分</span>
                        </p>
                      </div>
                    </div>

                    <div v-if="parsedEvaluation.feedback" class="writing-workspace__evaluation-card is-suggestion-card p-4" style="border: 1px solid var(--md-outline); background: var(--md-surface-container-low)">
                      <h5 class="dimension-title is-suggestion" style="font-family: var(--md-font-serif); font-weight: bold; color: var(--md-secondary)">
                        <span class="dimension-mark">💡</span> 评阅意见反馈
                      </h5>
                      <div class="prose prose-sm max-w-none mt-2 whitespace-pre-wrap" style="color: var(--md-on-surface-variant)" v-html="parseMarkdown(parsedEvaluation.feedback)"></div>
                    </div>
                  </div>

                  <!-- 格式 3: 原作者脑补的 summary / dimensions / suggestions 格式 -->
                  <div v-else class="space-y-6">
                    <!-- 评审大字号金石综合评价 -->
                    <div v-if="parsedEvaluation.summary" class="writing-workspace__evaluation-hero">
                      <div class="hero-seal">
                        <span>評</span>
                      </div>
                      <div class="hero-text">
                        <h4>本章综合评阅报告</h4>
                        <p class="md-body-medium">
                          {{ parsedEvaluation.summary }}
                        </p>
                      </div>
                    </div>

                    <!-- 各项维度细分卡片 -->
                    <div v-if="parsedEvaluation.dimensions" class="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div
                        v-for="(item, key) in parsedEvaluation.dimensions"
                        :key="key"
                        class="writing-workspace__evaluation-card"
                      >
                        <h5 class="dimension-title">
                          <span class="dimension-mark">✒️</span>
                          {{ key }}
                        </h5>
                        <p class="dimension-desc md-body-small">
                          {{ item.analysis || item }}
                        </p>
                      </div>
                    </div>

                    <!-- 优化改进建议 -->
                    <div v-if="parsedEvaluation.suggestions" class="writing-workspace__evaluation-card is-suggestion-card">
                      <h5 class="dimension-title is-suggestion">
                        <span class="dimension-mark">💡</span>
                        大案改进意见
                      </h5>
                      <ul class="suggestion-list">
                        <li v-for="(suggestion, sIdx) in parsedEvaluation.suggestions" :key="sIdx">
                          {{ suggestion }}
                        </li>
                      </ul>
                    </div>
                  </div>
                </template>

                <!-- 情况 B：解析 JSON 失败，直接作为 Markdown/文本渲染 -->
                <div v-else class="prose prose-sm max-w-none md-on-surface p-6 m3-eval-markdown-container rounded-sm" style="border: 1px dashed var(--md-outline); background: var(--md-surface-container-low)" v-html="parseMarkdown(selectedChapter.evaluation)"></div>
              </div>
              <div v-else class="h-full flex flex-col justify-center items-center py-12">
                <div class="text-center space-y-4 max-w-sm">
                  <span class="text-4xl">⚖️</span>
                  <h4 class="md-title-large font-semibold">尚无本章评阅报告</h4>
                  <p class="md-body-medium md-on-surface-variant">
                    阁主可呼叫 AI 评阅官，对当前已完成的章节正文进行全方位结构、文笔和剧情连贯性评阅。
                  </p>
                  <button
                    type="button"
                    class="md-btn md-btn-filled md-ripple"
                    style="background-color: var(--md-secondary); color: var(--md-on-secondary)"
                    :disabled="evaluatingChapter !== null"
                    @click="$emit('evaluateChapter')"
                  >
                    <span>{{ evaluatingChapter !== null ? '正在分析评审中...' : '呼叫 AI 评阅官' }}</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

    <!-- 编辑章节内容模态框 -->
    <div v-if="showEditModal" class="md-dialog-overlay" @click.self="closeEditModal">
      <div
        ref="editDialogRef"
        class="md-dialog w-full h-full max-w-5xl m3-editor-dialog"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="editDialogTitleId"
      >
        <!-- 模态框头部 -->
        <div
          class="flex items-center justify-between p-6 border-b m3-editor-dialog__header"
        >
          <h3 :id="editDialogTitleId" class="md-title-large font-semibold">
            编辑第{{ selectedChapterNumber }}章内容
          </h3>
          <button
            ref="editCloseButtonRef"
            data-dialog-initial-focus
            type="button"
            @click="closeEditModal"
            class="md-icon-btn md-ripple"
            aria-label="关闭编辑窗口"
          >
            <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
              <path
                fill-rule="evenodd"
                d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                clip-rule="evenodd"
              ></path>
            </svg>
          </button>
        </div>

        <!-- 模态框内容 -->
        <div class="flex-1 p-6 overflow-hidden">
          <div class="flex flex-col h-full">
            <label :for="editingContentInputId" class="md-text-field-label mb-2"> 章节内容 </label>
            <textarea
              :id="editingContentInputId"
              v-model="editingContent"
              class="md-textarea flex-1 w-full resize-none"
              placeholder="请输入章节内容..."
              :disabled="isSaving"
            ></textarea>
            <div class="md-body-small md-on-surface-variant mt-2">
              字数统计: {{ editingWordCount }}
            </div>
          </div>
        </div>

        <!-- 模态框底部 -->
        <div
          class="flex items-center justify-end gap-3 p-6 border-t m3-editor-dialog__footer"
        >
          <button
            type="button"
            @click="closeEditModal"
            :disabled="isSaving"
            class="md-btn md-btn-outlined md-ripple disabled:opacity-50"
          >
            取消
          </button>
          <button
            type="button"
            @click="saveEditedContent"
            :disabled="isSaving || !editingContent.trim()"
            class="md-btn md-btn-filled md-ripple disabled:opacity-50 flex items-center gap-2"
          >
            <svg
              v-if="isSaving"
              class="w-4 h-4 animate-spin"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fill-rule="evenodd"
                d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-1-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z"
                clip-rule="evenodd"
              ></path>
            </svg>
            {{ isSaving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import Tooltip from '@/components/Tooltip.vue'
import { globalAlert } from '@/composables/useAlert'
import { useDialogA11y } from '@/composables/useDialogA11y'
import { useChapterReader } from '@/composables/useChapterReader'
import type {
  Chapter,
  ChapterOutline,
  ChapterGenerationResponse,
  ChapterVersion,
  NovelProject,
} from '@/api/novel'
import { countNonWhitespaceChars } from '@/utils/text'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import WorkspaceInitial from './workspace/WorkspaceInitial.vue'
import ChapterGenerating from './workspace/ChapterGenerating.vue'
import VersionSelector from './workspace/VersionSelector.vue'
import ChapterContent from './workspace/ChapterContent.vue'
import ChapterReaderBar from './ChapterReaderBar.vue'
import ChapterFailed from './workspace/ChapterFailed.vue'
import ChapterEmpty from './workspace/ChapterEmpty.vue'

interface Props {
  project: NovelProject | null
  selectedChapterNumber: number | null
  generatingChapter: number | null
  evaluatingChapter: number | null
  showVersionSelector: boolean
  chapterGenerationResult: ChapterGenerationResponse | null
  selectedVersionIndex: number
  availableVersions: ChapterVersion[]
  isSelectingVersion?: boolean
}

const props = defineProps<Props>()

const emit = defineEmits([
  'regenerateChapter',
  'evaluateChapter',
  'hideVersionSelector',
  'update:selectedVersionIndex',
  'showVersionDetail',
  'confirmVersionSelection',
  'generateChapter',
  'retryFromNode',
  'selectChapter',
  'showVersionSelector',
  'showEvaluationDetail',
  'fetchChapterStatus',
  'editChapter',
])

interface ChapterContentExpose {
  openOptimizerPanel?: () => void
  openOptimizerPanelWithPreset?: (preset?: { dimension?: string; notes?: string }) => void
  exportCurrentChapterAsTxt?: () => void
}

const bodyComponentRef = ref<ChapterContentExpose | null>(null)
const aiMenuRef = ref<HTMLElement | null>(null)
const aiMenuPanelRef = ref<HTMLElement | null>(null)
const aiMenuTriggerRef = ref<HTMLButtonElement | null>(null)
const aiMenuItemRefs = ref<Array<HTMLElement | null>>([])
const aiMenuId = 'wd-workspace-ai-menu'
const showAiMenu = ref(false)
const chapterReader = useChapterReader()
const readerStatus = chapterReader.status

const copyTextLegacy = (text: string): boolean => {
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', 'readonly')
  textarea.style.position = 'fixed'
  textarea.style.top = '-9999px'
  textarea.style.left = '-9999px'
  document.body.appendChild(textarea)
  textarea.focus()
  textarea.select()

  let copied = false
  try {
    copied = document.execCommand('copy')
  } catch (error) {
    copied = false
  }

  document.body.removeChild(textarea)
  return copied
}

const chapterTitleTooltipText = ref('点击复制')

const resetChapterTitleTooltip = () => {
  chapterTitleTooltipText.value = '点击复制'
}

const copyText = async (text: string) => {
  try {
    if (window.isSecureContext && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }

    return copyTextLegacy(text)
  } catch (error) {
    console.error('复制失败:', error)
    return copyTextLegacy(text)
  }
}

const copySelectedChapterTitle = async () => {
  const title = (selectedChapterOutline.value?.title || '未知标题').trim()
  if (!title) return

  const copied = await copyText(title)
  chapterTitleTooltipText.value = copied ? '复制成功' : '复制失败'
}

const copySelectedChapterContent = async () => {
  const content = selectedChapterResolvedContent.value.trim()
  if (!content) return

  const copied = await copyText(content)
  if (!copied) {
    globalAlert.showError('复制失败，请手动选择文本复制。')
  }
}

// 编辑模态框状态
const showEditModal = ref(false)
const editDialogRef = ref<HTMLElement | null>(null)
const editCloseButtonRef = ref<HTMLElement | null>(null)
const editDialogTitleId = 'wd-workspace-edit-dialog-title'
const editingContentInputId = 'wd-workspace-edit-content-input'
const editingContent = ref('')
const isSaving = ref(false)

// 清理版本内容的辅助函数
const cleanVersionContent = (content: string): string => {
  if (!content) return ''
  try {
    const parsed = JSON.parse(content)
    const extractContent = (value: any): string | null => {
      if (!value) return null
      if (typeof value === 'string') return value
      if (Array.isArray(value)) {
        for (const item of value) {
          const nested = extractContent(item)
          if (nested) return nested
        }
        return null
      }
      if (typeof value === 'object') {
        for (const key of ['content', 'chapter_content', 'chapter_text', 'text', 'body', 'story']) {
          if (value[key]) {
            const nested = extractContent(value[key])
            if (nested) return nested
          }
        }
      }
      return null
    }
    const extracted = extractContent(parsed)
    if (extracted) {
      content = extracted
    }
  } catch (error) {
    // not a json
  }
  let cleaned = content.replace(/^"|"$/g, '')
  cleaned = cleaned.replace(/\\n/g, '\n')
  cleaned = cleaned.replace(/\\"/g, '"')
  cleaned = cleaned.replace(/\\t/g, '\t')
  cleaned = cleaned.replace(/\\\\/g, '\\')
  return cleaned
}

const editingWordCount = computed(() => countNonWhitespaceChars(editingContent.value))

const openEditModal = () => {
  if (hasSelectedChapterContent.value) {
    editingContent.value = selectedChapterResolvedContent.value
    showEditModal.value = true
  }
}

const closeEditModal = () => {
  if (isSaving.value) return
  showEditModal.value = false
  editingContent.value = ''
  isSaving.value = false
}

useDialogA11y({
  active: showEditModal,
  dialogRef: editDialogRef,
  onClose: closeEditModal,
  initialFocusRef: editCloseButtonRef,
})

const saveEditedContent = async () => {
  if (props.selectedChapterNumber === null || !editingContent.value.trim()) return

  isSaving.value = true
  try {
    emit('editChapter', {
      chapterNumber: props.selectedChapterNumber,
      content: editingContent.value,
    })
    closeEditModal()
  } catch (error) {
    console.error('保存章节内容失败:', error)
  } finally {
    isSaving.value = false
  }
}

const selectedChapter = computed<Chapter | null>(() => {
  if (!props.project || props.selectedChapterNumber === null) return null
  return (
    props.project.chapters.find((ch) => ch.chapter_number === props.selectedChapterNumber) || null
  )
})

const selectedChapterOutline = computed(() => {
  if (!props.project?.blueprint?.chapter_outline || props.selectedChapterNumber === null)
    return null
  return (
    props.project.blueprint.chapter_outline.find(
      (ch) => ch.chapter_number === props.selectedChapterNumber,
    ) || null
  )
})

const toBoundedVersionIndex = (value: unknown): number | null => {
  const index = Number(value)
  if (!Number.isInteger(index) || index < 0 || index >= props.availableVersions.length) {
    return null
  }
  return index
}

const resolveRecommendedVersionIndex = (chapter: Chapter | null): number | null => {
  if (!chapter || props.availableVersions.length === 0) {
    return null
  }

  const metadataIndex = props.availableVersions.findIndex((version) => {
    const metadata = version.metadata
    return metadata?.ai_review?.is_best === true
  })
  if (metadataIndex >= 0) {
    return metadataIndex
  }

  for (const version of props.availableVersions) {
    const metadata = version.metadata
    const metadataBestIndex = toBoundedVersionIndex(
      metadata?.review_summaries?.ai_review?.best_version_index ??
        metadata?.ai_review?.best_version_index,
    )
    if (metadataBestIndex !== null) {
      return metadataBestIndex
    }
  }

  const traces = [...(chapter.generation_traces ?? [])].reverse()
  for (const trace of traces) {
    if (trace.node_key !== 'save_draft') {
      continue
    }
    const metadata = trace.metadata && typeof trace.metadata === 'object' ? trace.metadata : {}
    for (const candidate of [
      metadata.input_payload?.recommended_version_index,
      metadata.metrics?.recommended_version_index,
      metadata.recommended_version_index,
      metadata.input_payload?.best_version_index,
      metadata.metrics?.best_version_index,
    ]) {
      const traceIndex = toBoundedVersionIndex(candidate)
      if (traceIndex !== null) {
        return traceIndex
      }
    }
  }

  return null
}

const resolveVersionFallbackOrder = (chapter: Chapter | null): number[] => {
  const indices: number[] = []
  const pushIndex = (index: number | null) => {
    if (index !== null && !indices.includes(index)) {
      indices.push(index)
    }
  }

  const selectedIndex = toBoundedVersionIndex(props.selectedVersionIndex)
  const recommendedIndex = resolveRecommendedVersionIndex(chapter)
  // 待确认草稿初始索引常为 0；若 AI 明确推荐其他版本，正文兜底先展示推荐版本。
  if (chapter?.generation_status === 'waiting_for_confirm' && props.selectedVersionIndex === 0) {
    pushIndex(recommendedIndex)
  }
  pushIndex(selectedIndex)
  pushIndex(recommendedIndex)
  props.availableVersions.forEach((_, index) => pushIndex(index))
  return indices
}

const resolveChapterContent = (chapter: Chapter | null): string => {
  if (!chapter) {
    return ''
  }

  const directContent = cleanVersionContent(chapter?.content || '')
  if (directContent.trim()) {
    return directContent
  }

  for (const index of resolveVersionFallbackOrder(chapter)) {
    const version = props.availableVersions[index]
    const normalized = cleanVersionContent(version.content || '')
    if (normalized.trim()) {
      return normalized
    }
  }

  return ''
}

const selectedChapterResolvedContent = computed(() => resolveChapterContent(selectedChapter.value))

const selectedChapterForDisplay = computed<Chapter | null>(() => {
  const chapter = selectedChapter.value
  if (!chapter) return null
  if (chapter.content && cleanVersionContent(chapter.content).trim()) {
    return chapter
  }
  return {
    ...chapter,
    content: selectedChapterResolvedContent.value,
  }
})

const hasSelectedChapterContent = computed(() => {
  return selectedChapterResolvedContent.value.trim().length > 0
})

const isFinalizedSuccessful = computed(() => {
  return selectedChapter.value?.generation_status === 'successful' && hasSelectedChapterContent.value
})

// 朗读控件：入口仅在 idle 显示，点击后原地展开为播放条；重置即停止回到入口
const readerCurrentParagraphIndex = chapterReader.currentParagraphIndex
const readerParagraphCount = chapterReader.paragraphCount
const readerIsBrowserFallback = chapterReader.isBrowserFallback
const readerVoiceURI = chapterReader.voiceURI
const readerRate = chapterReader.rate

// 浏览器朗读音色：仅在浏览器 fallback 时可选，选项来自本机 getVoices，存 localStorage
const browserVoiceOptions = ref<SpeechSynthesisVoice[]>([])
const refreshBrowserVoices = () => {
  browserVoiceOptions.value = (window.speechSynthesis?.getVoices?.() ?? []).filter(
    (voice) => /^zh/i.test(voice.lang) && /natural|neural/i.test(voice.name),
  )
}
// 微软在线神经语音英文名 → 中文友好名（带性别/地区），未命中的回退原英文名
const VOICE_CN_LABEL: Record<string, string> = {
  Xiaoxiao: '晓晓（女）',
  Xiaoyi: '晓伊（女）',
  Yunjian: '云健（男）',
  Yunxi: '云希（男）',
  Yunxia: '云夏（女）',
  Yunyang: '云扬（男）',
  Xiaobei: '晓北（女·东北话）',
  Xiaoni: '晓妮（女·陕西话）',
  HsiaoChen: '晓臻（女·台湾）',
  HsiaoYu: '晓雨（女·台湾）',
  YunJhe: '云哲（男·台湾）',
  HiuGaai: '曉佳（女·粤语）',
  HiuMaan: '曉敏（女·粤语）',
  WanLung: '雲龍（男·粤语）',
}
const readerVoiceLabel = (voice: SpeechSynthesisVoice) => {
  const match = voice.name.match(/Microsoft\s+([A-Za-z]+)/i)
  return (match && VOICE_CN_LABEL[match[1]]) || voice.name
}

// 悬浮控件音色选项（URI + 清洗后的标签）
const readerVoiceOptions = computed(() =>
  browserVoiceOptions.value.map((voice) => ({ uri: voice.voiceURI, label: readerVoiceLabel(voice) })),
)

// 朗读倍速：浏览器与模型 TTS 通用
const READER_RATE_OPTIONS = [0.75, 1, 1.25, 1.5, 2]

const handleReaderStart = () => {
  const chapterTitle = `第${props.selectedChapterNumber}章 ${selectedChapterOutline.value?.title || '未知标题'}`
  void chapterReader.start(chapterTitle, selectedChapterResolvedContent.value)
}

const handleReaderPlayPause = () => {
  if (readerStatus.value === 'playing') {
    chapterReader.pause()
    return
  }
  if (readerStatus.value === 'paused') {
    chapterReader.resume()
    return
  }
  if (readerStatus.value === 'generating') {
    chapterReader.stop()
  }
}

// 重置：停止朗读，收缩回「准备播放」入口
const handleReaderReset = () => {
  chapterReader.stop()
}

const isDraftWaitingConfirm = computed(() => {
  const status = selectedChapter.value?.generation_status
  return status === 'waiting_for_confirm'
})

const shouldShowDraftTraceReplay = computed(() => {
  return isDraftWaitingConfirm.value && hasSelectedChapterContent.value
})

const selectedChapterWordCount = computed(() => countNonWhitespaceChars(selectedChapterResolvedContent.value))

const lockedPrerequisiteChapterNumber = computed(() => {
  if (props.selectedChapterNumber === null || !props.project?.blueprint?.chapter_outline) {
    return null
  }

  const chaptersByNumber = new Map(
    (props.project.chapters ?? []).map((chapter) => [chapter.chapter_number, chapter]),
  )
  const sortedOutlines = [...props.project.blueprint.chapter_outline].sort(
    (left, right) => left.chapter_number - right.chapter_number,
  )

  // 未解锁的核心规则：当前章之前必须全部生成成功，才允许推进当前章。
  for (const outline of sortedOutlines) {
    if (outline.chapter_number >= props.selectedChapterNumber) break
    const chapter = chaptersByNumber.get(outline.chapter_number)
    if (chapter?.generation_status !== 'successful') {
      return outline.chapter_number
    }
  }

  return null
})

const lockedPrerequisiteChapterTitle = computed(() => {
  const num = lockedPrerequisiteChapterNumber.value
  if (num === null || !props.project?.blueprint?.chapter_outline) {
    return null
  }
  const outline = props.project.blueprint.chapter_outline.find(
    (ch) => ch.chapter_number === num,
  )
  return outline?.title || null
})


const isSelectedChapterLocked = computed(() => {
  if (props.selectedChapterNumber === null) return false
  if (lockedPrerequisiteChapterNumber.value === null) return false
  if (hasSelectedChapterContent.value) return false
  const status = selectedChapter.value?.generation_status
  return status !== 'failed' && status !== 'evaluation_failed' && status !== 'waiting_for_confirm'
})

const shouldShowChapterToolbar = computed(() => {
  if (isSelectedChapterLocked.value) return false
  return isFinalizedSuccessful.value || isDraftWaitingConfirm.value
})

const chapterStatusLabel = computed(() => {
  const status = props.evaluatingChapter === props.selectedChapterNumber
    ? 'evaluating'
    : selectedChapter.value?.generation_status
  switch (status) {
    case 'successful':
      return '已完成'
    case 'generating':
      return '生成中'
    case 'evaluating':
      return '评审中'
    case 'selecting':
      return '选择版本'
    case 'finalizing':
      return '定稿中'
    case 'waiting_for_confirm':
      return '待确认'
    case 'failed':
      return '生成失败'
    case 'evaluation_failed':
      return '评审失败'
    default:
      return '待开始'
  }
})

const chapterStatusTone = computed(() => {
  const status = props.evaluatingChapter === props.selectedChapterNumber
    ? 'evaluating'
    : selectedChapter.value?.generation_status
  if (status === 'successful') return 'success'
  if (status === 'failed' || status === 'evaluation_failed') return 'error'
  if (status === 'generating' || status === 'evaluating' || status === 'selecting' || status === 'finalizing') return 'progress'
  if (status === 'waiting_for_confirm') return 'pending'
  return 'idle'
})

const formatDateTime = (value?: string | null) => {
  if (!value) return '--'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return '--'
  const year = parsed.getFullYear()
  const month = String(parsed.getMonth() + 1).padStart(2, '0')
  const day = String(parsed.getDate()).padStart(2, '0')
  const hour = String(parsed.getHours()).padStart(2, '0')
  const minute = String(parsed.getMinutes()).padStart(2, '0')
  return `${year}/${month}/${day} ${hour}:${minute}`
}

const chapterLastEditedText = computed(() =>
  formatDateTime(selectedChapter.value?.status_updated_at ?? selectedChapter.value?.generation_started_at),
)

const chapterInlineMeta = computed(() => {
  const segments: string[] = []
  if (hasSelectedChapterContent.value) {
    segments.push(`${selectedChapterWordCount.value}字`)
  }
  segments.push(`最后编辑 ${chapterLastEditedText.value}`)
  return segments.join(' · ')
})

const isChapterGenerating = (chapterNumber: number) => {
  if (!props.project?.chapters) return false
  const chapter = props.project.chapters.find((ch) => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'generating'
}

const isSelectedChapterGeneratingLike = computed(() => {
  if (props.selectedChapterNumber === null) return false
  return (
    props.generatingChapter === props.selectedChapterNumber ||
    isChapterGenerating(props.selectedChapterNumber)
  )
})

const isChapterFailed = (chapterNumber: number) => {
  if (!props.project?.chapters) return false
  const chapter = props.project.chapters.find((ch) => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'failed'
}

const isChapterEvaluationFailed = (chapterNumber: number) => {
  if (!props.project?.chapters) return false
  const chapter = props.project.chapters.find((ch) => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'evaluation_failed'
}

const isInProgressStatus = (status: Chapter['generation_status'] | null | undefined) => {
  return status === 'generating' || status === 'evaluating' || status === 'selecting' || status === 'finalizing'
}

const isGeneratingInFlight = computed(() => {
  if (props.selectedChapterNumber === null) return false
  if (props.generatingChapter !== props.selectedChapterNumber) return false

  // Regenerating a completed chapter can briefly keep backend status as `successful`
  // before the async pipeline updates to `generating`.
  // Keep showing progress UI while local request is still in-flight.
  const status = selectedChapter.value?.generation_status
  return !(status === 'waiting_for_confirm' || status === 'selecting')
})

const canGenerateChapter = (chapterNumber: number | null) => {
  if (chapterNumber === null || !props.project?.blueprint?.chapter_outline) return false

  const outlines = props.project.blueprint.chapter_outline.sort(
    (a, b) => a.chapter_number - b.chapter_number,
  )

  for (const outline of outlines) {
    if (outline.chapter_number >= chapterNumber) break

    const chapter = props.project?.chapters.find(
      (ch) => ch.chapter_number === outline.chapter_number,
    )
    if (!chapter || chapter.generation_status !== 'successful') {
      return false
    }
  }

  const currentChapter = props.project?.chapters.find((ch) => ch.chapter_number === chapterNumber)
  if (currentChapter && currentChapter.generation_status === 'successful') {
    return true
  }

  return true
}

const currentComponent = computed(() => {
  if (props.selectedChapterNumber === null) {
    return WorkspaceInitial
  }

  const status = props.evaluatingChapter === props.selectedChapterNumber
    ? 'evaluating'
    : selectedChapter.value?.generation_status
  const shouldRenderGenerating =
    (isInProgressStatus(status) || isGeneratingInFlight.value || status === 'failed' || status === 'evaluation_failed') &&
    !(status === 'successful' && hasSelectedChapterContent.value)
  if (shouldRenderGenerating) {
    return ChapterGenerating // Use a generic "in-progress" component
  }

  if (status === 'waiting_for_confirm') {
    if (hasSelectedChapterContent.value) {
      return ChapterContent
    }
    return VersionSelector
  }

  // 仅在不处于选版态时展示正文，避免生成完成后看不到新版本选择区。
  if (hasSelectedChapterContent.value) {
    return ChapterContent
  }

  if (isChapterFailed(props.selectedChapterNumber)) {
    return ChapterFailed
  }
  return ChapterEmpty
})

const isChapterContentView = computed(
  () => currentComponent.value === ChapterContent && hasSelectedChapterContent.value,
)
const canViewVersions = computed(() => props.availableVersions.length > 0)
const isAiMenuDisabled = computed(
  () => isSelectedChapterGeneratingLike.value && !isChapterContentView.value,
)

const resolveMenuElement = (element: unknown) => {
  if (element instanceof HTMLElement) {
    return element
  }
  if (element && typeof element === 'object' && '$el' in element) {
    const componentElement = (element as { $el?: unknown }).$el
    if (componentElement instanceof HTMLElement) {
      return componentElement
    }
  }
  return null
}

const registerAiMenuItemRef = (element: unknown, index: number) => {
  aiMenuItemRefs.value[index] = resolveMenuElement(element)
}

const getEnabledMenuItems = (items: Array<HTMLElement | null>) => {
  return items.filter((item) => item && !item.hasAttribute('disabled')) as HTMLElement[]
}

const focusMenuItemAtIndex = (items: Array<HTMLElement | null>, targetIndex: number) => {
  const enabledItems = getEnabledMenuItems(items)
  if (enabledItems.length === 0) return
  const safeIndex = ((targetIndex % enabledItems.length) + enabledItems.length) % enabledItems.length
  enabledItems[safeIndex]?.focus()
}

const focusFirstMenuItem = (items: Array<HTMLElement | null>) => {
  focusMenuItemAtIndex(items, 0)
}

const handleMenuKeydown = (
  event: KeyboardEvent,
  items: Array<HTMLElement | null>,
  closeMenu: (restoreFocus?: boolean) => void,
) => {
  const enabledItems = getEnabledMenuItems(items)
  if (enabledItems.length === 0) return

  const activeElement = document.activeElement as HTMLElement | null
  const currentIndex = enabledItems.findIndex((item) => item === activeElement)

  if (event.key === 'Escape') {
    event.preventDefault()
    closeMenu(true)
    return
  }

  if (event.key === 'Tab') {
    closeMenu()
    return
  }

  if (event.key === 'ArrowDown') {
    event.preventDefault()
    focusMenuItemAtIndex(enabledItems, currentIndex + 1)
    return
  }

  if (event.key === 'ArrowUp') {
    event.preventDefault()
    focusMenuItemAtIndex(enabledItems, currentIndex - 1)
    return
  }

  if (event.key === 'Home') {
    event.preventDefault()
    focusMenuItemAtIndex(enabledItems, 0)
    return
  }

  if (event.key === 'End') {
    event.preventDefault()
    focusMenuItemAtIndex(enabledItems, enabledItems.length - 1)
  }
}

const handleAiMenuKeydown = (event: KeyboardEvent) => {
  handleMenuKeydown(event, aiMenuItemRefs.value, closeAiMenu)
}

const closeAiMenu = (restoreFocus: boolean = false) => {
  showAiMenu.value = false
  if (restoreFocus) {
    aiMenuTriggerRef.value?.focus()
  }
}

const toggleAiMenu = () => {
  if (isAiMenuDisabled.value) return
  showAiMenu.value = !showAiMenu.value
  if (showAiMenu.value) {
    nextTick(() => {
      focusFirstMenuItem(aiMenuItemRefs.value)
    })
  }
}

const openVersionDetail = () => {
  if (!canViewVersions.value) {
    globalAlert.showError('当前章节暂无可查看版本')
    return
  }

  const maxIndex = props.availableVersions.length - 1
  const safeIndex = Math.min(Math.max(props.selectedVersionIndex, 0), maxIndex)
  emit('showVersionDetail', safeIndex)
}

const openContentOptimizer = () => {
  bodyComponentRef.value?.openOptimizerPanel?.()
}

const openContentOptimizerWithPreset = (preset?: { dimension?: string; notes?: string }) => {
  bodyComponentRef.value?.openOptimizerPanelWithPreset?.(preset)
}

const exportContentAsTxt = () => {
  bodyComponentRef.value?.exportCurrentChapterAsTxt?.()
}

const handleLayeredOptimize = () => {
  closeAiMenu()
  if (!isChapterContentView.value) return
  openContentOptimizer()
}

const handlePolishContent = () => {
  closeAiMenu()
  if (!isChapterContentView.value) return
  openContentOptimizerWithPreset({
    dimension: 'dialogue',
    notes: '请优先润色正文表达，让叙述更顺滑、更有画面感。',
  })
}

const handleAdjustRhythm = () => {
  closeAiMenu()
  if (!isChapterContentView.value) return
  openContentOptimizerWithPreset({
    dimension: 'rhythm',
    notes: '请重点调整章节节奏，控制信息密度与推进速度。',
  })
}

const handleRewriteStyle = () => {
  closeAiMenu()
  if (!isChapterContentView.value) return
  openContentOptimizerWithPreset({
    dimension: 'dialogue',
    notes: '请在不改变剧情事实的前提下改写文风，统一语气并提升辨识度。',
  })
}

const handleAiMenuOutsideClick = (event: MouseEvent) => {
  const targetNode = event.target as Node | null
  if (!targetNode) return
  if (showAiMenu.value && !aiMenuRef.value?.contains(targetNode)) {
    showAiMenu.value = false
  }
}

const requestChapterStatus = () => {
  emit('fetchChapterStatus')
}

watch(
  [
    () => props.selectedChapterNumber,
    () => selectedChapter.value?.generation_status ?? null,
    () => selectedChapter.value?.versions?.length ?? 0,
    () => Boolean(selectedChapter.value?.content),
  ],
  ([chapterNumber, status, versionsCount, hasContent]) => {
    if (chapterNumber === null) {
      return
    }

    // 需要服务端推送同步的场景：
    // 1) 生成/评审/选择中（状态推进）
    // 2) 等待确认但正文还没同步（含版本已到但正文未到的短暂窗口）
    // 3) 已成功但正文暂未同步（避免必须手动刷新）
    const needsPolling =
      isGeneratingInFlight.value ||
      status === 'generating' ||
      status === 'evaluating' ||
      status === 'selecting' ||
      status === 'finalizing' ||
      (status === 'waiting_for_confirm' && !hasContent) ||
      (status === 'successful' && !hasContent)

    if (needsPolling) {
      requestChapterStatus()
    }
  },
  { immediate: true },
)

watch(
  () => props.selectedChapterNumber,
  () => {
    closeAiMenu()
    chapterReader.stop()
  },
)

onMounted(() => {
  document.addEventListener('click', handleAiMenuOutsideClick)
  refreshBrowserVoices()
  window.speechSynthesis?.addEventListener('voiceschanged', refreshBrowserVoices)
})

onUnmounted(() => {
  document.removeEventListener('click', handleAiMenuOutsideClick)
  window.speechSynthesis?.removeEventListener('voiceschanged', refreshBrowserVoices)
  chapterReader.stop()
})

const currentComponentProps = computed(() => {
  if (props.selectedChapterNumber === null) {
    return {}
  }
  const status = props.evaluatingChapter === props.selectedChapterNumber
    ? 'evaluating'
    : selectedChapter.value?.generation_status
  const isBackendInProgress = isInProgressStatus(status)
  const isFailed = status === 'failed' || status === 'evaluation_failed'
  const shouldRenderGenerating =
    (isBackendInProgress || isGeneratingInFlight.value || isFailed) &&
    !(status === 'successful' && hasSelectedChapterContent.value)
  if (shouldRenderGenerating) {
    // 重试请求仍在途时，忽略旧 failed 快照，避免轮询旧响应把进度条拉回失败节点。
    const renderAsLocalGenerating = isGeneratingInFlight.value && !isBackendInProgress
    const renderStatus = renderAsLocalGenerating ? 'generating' : status
    const generationProgress = renderAsLocalGenerating
      ? 0
      : isBackendInProgress
        ? (selectedChapter.value?.generation_progress ?? null)
        : null
    const generationStep = renderAsLocalGenerating
      ? 'context_prep'
      : isBackendInProgress || isFailed
        ? (selectedChapter.value?.generation_step ?? null)
        : null
    const generationStepIndex = renderAsLocalGenerating
      ? 1
      : isBackendInProgress
        ? (selectedChapter.value?.generation_step_index ?? null)
        : null
    const generationStepTotal = renderAsLocalGenerating
      ? 7
      : isBackendInProgress
        ? (selectedChapter.value?.generation_step_total ?? null)
        : null

    return {
      chapterNumber: props.selectedChapterNumber,
      chapterTitle: selectedChapterOutline.value?.title || '',
      chapterSummary: selectedChapterOutline.value?.summary || '',
      chapterContentPreview: cleanVersionContent(selectedChapter.value?.content || ''),
      status: renderStatus,
      generationProgress,
      generationStep,
      generationStepIndex,
      generationStepTotal,
      generationStartedAt: isBackendInProgress
        ? (selectedChapter.value?.generation_started_at ?? null)
        : null,
      statusUpdatedAt: isBackendInProgress
        ? (selectedChapter.value?.status_updated_at ?? null)
        : null,
      generationTraces: renderAsLocalGenerating
        ? []
        : (selectedChapter.value?.generation_traces ?? []),
      generatingChapter: props.generatingChapter,
      availableVersions: props.availableVersions,
      selectedVersionIndex: props.selectedVersionIndex,
    }
  }

  if (status === 'waiting_for_confirm') {
    if (hasSelectedChapterContent.value) {
      return {
        selectedChapter: selectedChapterForDisplay.value,
        projectId: props.project?.id,
        activeParagraphIndex: readerCurrentParagraphIndex.value,
      }
    }

    return {
      selectedChapter: selectedChapter.value,
      chapterGenerationResult: props.chapterGenerationResult,
      availableVersions: props.availableVersions,
      selectedVersionIndex: props.selectedVersionIndex,
      isSelectingVersion: props.isSelectingVersion,
      evaluatingChapter: props.evaluatingChapter,
      isEvaluationFailed: isChapterEvaluationFailed(props.selectedChapterNumber),
    }
  }
  if (hasSelectedChapterContent.value) {
    return {
      selectedChapter: selectedChapterForDisplay.value,
      projectId: props.project?.id,
      activeParagraphIndex: readerCurrentParagraphIndex.value,
    }
  }
  if (isChapterFailed(props.selectedChapterNumber)) {
    return {
      chapterNumber: props.selectedChapterNumber,
      generatingChapter: props.generatingChapter,
      generationStatus: selectedChapter.value?.generation_status ?? 'failed',
      generationStep: selectedChapter.value?.generation_step ?? null,
    }
  }
  return {
    chapterNumber: props.selectedChapterNumber,
    generatingChapter: props.generatingChapter,
    canGenerate: canGenerateChapter(props.selectedChapterNumber),
    lockedPrerequisiteChapterNumber: lockedPrerequisiteChapterNumber.value,
    lockedPrerequisiteChapterTitle: lockedPrerequisiteChapterTitle.value,
    chapterOutline: selectedChapterOutline.value,
    project: props.project,
  }
})

const draftTraceReplayProps = computed(() => ({
  chapterNumber: props.selectedChapterNumber,
  chapterTitle: selectedChapterOutline.value?.title || '',
  chapterSummary: selectedChapterOutline.value?.summary || '',
  chapterContentPreview: selectedChapterResolvedContent.value,
  status: selectedChapter.value?.generation_status ?? null,
  generationProgress: selectedChapter.value?.generation_progress ?? null,
  generationStep: selectedChapter.value?.generation_step ?? 'waiting_for_confirm',
  generationStepIndex: selectedChapter.value?.generation_step_index ?? null,
  generationStepTotal: selectedChapter.value?.generation_step_total ?? null,
  generationStartedAt: selectedChapter.value?.generation_started_at ?? null,
  statusUpdatedAt: selectedChapter.value?.status_updated_at ?? null,
  generationTraces: selectedChapter.value?.generation_traces ?? [],
  generatingChapter: props.generatingChapter,
  availableVersions: props.availableVersions,
  selectedVersionIndex: props.selectedVersionIndex,
  readOnly: true,
}))

// ==========================================================================
// 写作台正文/历史版本/AI评审三合一 Tab 切换区状态与逻辑
// ==========================================================================
const activeTab = ref<'content' | 'versions' | 'evaluation'>('content')
const previewVersionIndex = ref<number>(0)

watch(
  () => props.selectedChapterNumber,
  () => {
    activeTab.value = 'content'
    previewVersionIndex.value = 0
  }
)

watch(
  () => props.availableVersions,
  (newVersions) => {
    if (previewVersionIndex.value >= newVersions.length) {
      previewVersionIndex.value = 0
    }
  },
  { deep: true }
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
  activeTab.value = 'content' // 自动切回正文
}

const isCurrentVersion = (index: number) => {
  const version = props.availableVersions[index]
  if (!version) return false
  return cleanVersionContent(version.content).trim() === selectedChapterResolvedContent.value.trim()
}

const parsedEvaluation = computed(() => {
  const evalStr = selectedChapter.value?.evaluation
  if (!evalStr) return null
  try {
    let data = JSON.parse(evalStr)
    if (typeof data === 'string') {
      data = JSON.parse(data)
    }
    return data
  } catch (error) {
    console.error('Failed to parse evaluation JSON in WDWorkspace:', error)
    return null
  }
})

const getEvaluationVersionNumber = (versionKey: string | number): number => {
  const normalizedKey = String(versionKey)
  const match = normalizedKey.match(/\d+/)
  return match ? Number.parseInt(match[0], 10) : 0
}

const sortedEvaluationEntries = computed(() => {
  const evaluation = parsedEvaluation.value?.evaluation
  if (!evaluation || typeof evaluation !== 'object' || Array.isArray(evaluation)) {
    return []
  }

  // 多版本编号必须和候选版本数组一致：version1 对应 availableVersions[0]。
  return Object.entries(evaluation)
    .map(([key, result]) => ({
      key,
      result: result as Record<string, any>,
      versionNumber: getEvaluationVersionNumber(key),
    }))
    .sort((a, b) => a.versionNumber - b.versionNumber)
})

const parseMarkdown = (text: string | null | undefined): string => {
  if (!text) return ''
  try {
    let cleaned = text
      .replace(/\\n/g, '\n')
      .replace(/\\"/g, '"')
      .replace(/\\'/g, "'")
      .replace(/\\\\/g, '\\')

    let parsed = ''
    if (marked && typeof marked.parse === 'function') {
      parsed = marked.parse(cleaned, { breaks: true }) as string
    } else if (typeof marked === 'function') {
      parsed = (marked as any)(cleaned, { breaks: true }) as string
    } else {
      parsed = cleaned
    }

    return DOMPurify.sanitize(parsed, {
      USE_PROFILES: { html: true },
    })
  } catch (error) {
    console.error('Failed to parse Markdown in WDWorkspace:', error)
    return DOMPurify.sanitize(text, {
      USE_PROFILES: { html: true },
    })
  }
}
</script>

<style scoped>
.writing-workspace {
  min-width: 0;
  min-height: 0;
  height: 100%;
}

.writing-workspace__panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  border-radius: 0 !important; /* 方直古籍 */
  background: var(--md-surface);
  /* 极致国风脑洞：工作区熟宣纹理 */
  background-image: repeating-linear-gradient(90deg, rgba(28, 32, 34, 0.006) 0px, rgba(28, 32, 34, 0.006) 1px, transparent 1px, transparent 36px);
  border: 3px double var(--md-outline) !important;
  box-shadow: 3px 3px 0px var(--md-outline);
}

.writing-workspace__header {
  flex-shrink: 0;
  padding: var(--md-spacing-4) var(--md-spacing-5);
  border-bottom: 1px dashed var(--md-outline);
  background-color: var(--md-surface-container-low);
}

.writing-workspace__header-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--md-spacing-4);
}

.writing-workspace__chapter-meta {
  flex: 1 1 auto;
  min-width: 0;
}

.writing-workspace__chapter-title-line {
  display: flex;
  align-items: center;
  gap: var(--md-spacing-2);
  margin-bottom: var(--md-spacing-1);
  flex-wrap: wrap;
}

.writing-workspace__chapter-no {
  flex-shrink: 0;
  font-size: 22px;
  font-family: var(--md-font-serif);
  font-weight: 600;
  letter-spacing: 0.04em;
}

/* 极致国风脑洞：将状态标签改造为方直“金石印章方印” */
.writing-workspace__status-tag {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 7px;
  border-radius: 0 !important; /* 强制去圆角 */
  border: 1.5px solid transparent;
  font-size: 11px;
  font-weight: 600;
  font-family: var(--md-font-serif);
  letter-spacing: 0.08em;
  white-space: nowrap;
}

/* 竹青阴刻 */
.writing-workspace__status-tag--success {
  color: var(--md-on-primary);
  background-color: var(--md-success);
  border-color: var(--md-success-text);
  box-shadow: 1px 1px 0px rgba(63, 108, 93, 0.25);
}

/* 赭红阴刻 */
.writing-workspace__status-tag--error {
  color: var(--md-on-primary);
  background-color: var(--md-error);
  border-color: var(--md-error-text);
  box-shadow: 1px 1px 0px rgba(184, 60, 50, 0.25);
}

/* 朱砂阳刻（红底白字或红边红字） */
.writing-workspace__status-tag--progress {
  color: var(--md-secondary);
  background-color: rgba(184, 60, 50, 0.05);
  border-color: var(--md-secondary);
  box-shadow: 1.5px 1.5px 0px rgba(184, 60, 50, 0.15);
}

.writing-workspace__status-tag--pending {
  color: var(--md-secondary);
  background-color: rgba(184, 60, 50, 0.03);
  border-color: var(--md-secondary);
}

.writing-workspace__status-tag--idle {
  color: var(--md-on-surface-variant);
  background-color: var(--md-surface-container-low);
  border-color: var(--md-outline);
}

.writing-workspace__chapter-inline-meta {
  white-space: nowrap;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.08em;
  font-family: var(--md-font-serif);
}

.writing-workspace__title-copy {
  min-width: 0;
  flex: 1;
  padding: 0;
  border: 0;
  background: transparent;
  text-align: left;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: pointer;
  appearance: none;
  font-size: 22px;
  font-family: var(--md-font-serif);
  font-weight: 600;
  letter-spacing: 0.04em;
  transition: color 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}

.writing-workspace__title-copy:hover {
  color: var(--md-secondary);
  text-decoration: underline;
}

.writing-workspace__title-copy:focus-visible {
  outline: 2.5px solid var(--md-secondary);
  outline-offset: 3px;
  border-radius: 0 !important;
}

.writing-workspace__summary {
  max-width: 88ch;
  font-size: 15px;
  line-height: 1.75;
  letter-spacing: 0.02em;
  color: var(--md-on-surface-variant);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-family: var(--md-font-serif);
  font-weight: 500;
  font-style: normal;
  opacity: 0.85;
}

.writing-workspace__toolbar {
  margin-left: auto;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: flex-start;
  gap: 8px;
  padding-top: 4px;
  white-space: nowrap;
}

.writing-workspace__toolbar-row {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  width: 100%;
}

.writing-workspace__toolbar-row--utility {
  opacity: 0.96;
}

.writing-workspace__toolbar-row--primary {
  justify-content: flex-end;
}

.writing-workspace__toolbar-group {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

.writing-workspace__toolbar-group--utility {
  gap: 6px;
}

.writing-workspace__toolbar-group--emphasis {
  gap: 8px;
}

.writing-workspace__toolbar-divider {
  width: 1px;
  height: 20px;
  background-color: var(--md-outline);
}

/* 极致国风脑洞：工具栏按钮的直角古朴金石风骨 */
.writing-workspace__tool-btn {
  min-height: 32px;
  height: 32px;
  padding-inline: 12px;
  border-radius: 0 !important; /* 去除圆角 */
  font-size: var(--md-label-medium);
  letter-spacing: 0.05em;
  font-family: var(--md-font-serif);
  font-weight: 600;
  border: 1px solid var(--md-outline);
  box-shadow: 1.5px 1.5px 0px var(--md-outline);
  transition:
    background-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.25s cubic-bezier(0.22, 1, 0.36, 1);
}

/* Hover 状态 */
.writing-workspace__tool-btn:hover:not(:disabled) {
  transform: translate(-0.5px, -0.5px);
  box-shadow: 2px 2px 0px var(--md-outline);
  background-color: var(--md-surface-container-low);
}

/* 脑洞：Active 点击时产生用力向下一压的钤印重力反馈 */
.writing-workspace__tool-btn:active:not(:disabled) {
  transform: translate(1.5px, 1.5px) !important;
  box-shadow: 0px 0px 0px var(--md-outline) !important;
}

.writing-workspace__tool-btn--hero {
  height: 38px;
  min-height: 38px;
  padding-inline: 16px;
  font-size: var(--md-title-small);
  font-weight: bold;
  border: 1.5px solid var(--md-outline) !important;
  box-shadow: 2px 2px 0px var(--md-outline);
}

.writing-workspace__tool-btn--hero:hover:not(:disabled) {
  transform: translate(-1px, -1px);
  box-shadow: 3px 3px 0px var(--md-outline);
}

.writing-workspace__tool-btn--hero:active:not(:disabled) {
  transform: translate(1.5px, 1.5px) !important;
  box-shadow: 0.5px 0.5px 0px var(--md-outline) !important;
}

.writing-workspace__label-full {
  display: inline;
}

.writing-workspace__label-short {
  display: none;
}

.writing-workspace__tool-btn--ghost {
  border-color: var(--md-outline);
  color: var(--md-on-surface-variant);
  background-color: transparent;
  box-shadow: 1px 1px 0px var(--md-outline);
}

.writing-workspace__tool-btn--ghost:hover:not(:disabled) {
  color: var(--md-secondary);
  border-color: var(--md-secondary);
  background-color: rgba(184, 60, 50, 0.02);
  box-shadow: 1.5px 1.5px 0px var(--md-secondary);
}

.writing-workspace__tool-btn--ghost:active:not(:disabled) {
  box-shadow: 0px 0px 0px var(--md-secondary) !important;
}

.writing-workspace__tool-btn--secondary {
  border-color: var(--md-outline) !important;
  background-color: var(--md-surface);
  color: var(--md-on-surface);
}

.writing-workspace__tool-btn--primary {
  border-color: var(--md-secondary) !important;
  background-color: rgba(184, 60, 50, 0.05);
  color: var(--md-secondary);
  box-shadow: 2px 2px 0px var(--md-secondary);
}

.writing-workspace__tool-btn--primary:hover:not(:disabled) {
  background-color: rgba(184, 60, 50, 0.09);
  box-shadow: 3px 3px 0px var(--md-secondary);
  border-color: var(--md-secondary) !important;
}

.writing-workspace__tool-btn--primary:active:not(:disabled) {
  box-shadow: 0px 0px 0px var(--md-secondary) !important;
}

/* 极致国风脑洞：下拉菜单重塑为方直“折页折扇”宣纸面板 */
.writing-workspace__ai-menu-panel {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  z-index: 48;
  min-width: 156px;
  padding: 4px;
  border-radius: 0 !important; /* 强制直角 */
  border: 2px solid var(--md-outline) !important;
  background: var(--md-surface);
  box-shadow: 3px 3px 0px var(--md-outline);
  animation: ink-menu-slide 0.3s cubic-bezier(0.22, 1, 0.36, 1) both;
}

.writing-workspace__ai-menu-panel {
  min-width: 180px;
}

/* 极致国风脑洞：菜单项 Hover 水墨吸水徐徐晕开淡染 */
.writing-workspace__ai-menu-item {
  display: block;
  width: 100%;
  min-height: 38px;
  padding: 8px 12px;
  border: 0;
  border-radius: 0 !important;
  background: transparent;
  text-align: left;
  font-size: var(--md-label-medium);
  font-family: var(--md-font-serif);
  font-weight: 600;
  color: var(--md-on-surface);
  cursor: pointer;
  transition: background-color 0.28s cubic-bezier(0.22, 1, 0.36, 1);
}

.writing-workspace__ai-menu-item:hover:not(:disabled) {
  background-color: rgba(184, 60, 50, 0.08) !important; /* 朱砂慢晕淡染 */
  color: var(--md-secondary);
}

.writing-workspace__ai-menu-item:focus-visible {
  outline: 1.5px solid var(--md-secondary);
  background-color: rgba(184, 60, 50, 0.04);
}

.writing-workspace__ai-menu-item--danger {
  color: #b83c32;
}

.writing-workspace__ai-menu-item--danger:hover:not(:disabled) {
  background-color: rgba(184, 60, 50, 0.12) !important;
}

/* 极致国风脑洞：正文区融入古典竹青淡墨横线信笺格背景 */
.writing-workspace__content {
  position: relative;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  padding: 0 !important; /* 彻底去除灰色间距，使内部稿纸能够完美顶边铺满 */
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-4);
  background-color: var(--md-surface);
}

.writing-workspace__body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.writing-workspace__trace-replay {
  padding: var(--md-spacing-3) var(--md-spacing-5) 0;
}

.m3-editor-dialog {
  max-width: min(1200px, calc(100vw - 32px));
  max-height: calc(var(--app-viewport-unit) - 32px);
  border-radius: 0 !important; /* 强制方直 */
  border: 3px double var(--md-outline) !important;
  background-color: var(--md-surface) !important;
  box-shadow: 4px 4px 0px var(--md-outline) !important;
}

.m3-editor-dialog__header {
  border-bottom: 1px dashed var(--md-outline) !important;
  background-color: var(--md-surface-container-low);
  font-family: var(--md-font-serif);
}

.m3-editor-dialog__header h3 {
  font-weight: bold;
  letter-spacing: 0.05em;
}

.m3-editor-dialog__footer {
  border-top: 1px dashed var(--md-outline) !important;
  background-color: var(--md-surface-container-low) !important;
}

.md-textarea {
  border-radius: 0 !important;
  border: 1px solid var(--md-outline) !important;
  background-color: var(--md-surface) !important;
  font-family: var(--md-font-family);
  font-size: var(--md-body-large);
  line-height: 1.7;
  padding: 12px;
}

.md-textarea:focus {
  border-color: var(--md-secondary) !important;
  box-shadow: 2px 2px 0px rgba(184, 60, 50, 0.2) !important;
  outline: none;
}

@media (max-width: 1160px) {
  .writing-workspace__toolbar-divider {
    display: none;
  }
}

@media (max-width: 940px) {
  .writing-workspace__header-row {
    flex-direction: column;
    gap: var(--md-spacing-3);
  }

  .writing-workspace__toolbar {
    width: 100%;
    align-items: stretch;
    margin-left: 0;
  }

  .writing-workspace__toolbar-row {
    justify-content: flex-end;
  }

  .writing-workspace__summary {
    max-width: 100%;
  }
}

@media (max-width: 640px) {
  .writing-workspace__header {
    padding: var(--md-spacing-4);
  }

  .writing-workspace__chapter-title-line {
    gap: 6px;
  }

  .writing-workspace__chapter-inline-meta {
    width: 100%;
  }

  .writing-workspace__tool-btn {
    min-width: 70px;
    padding-inline: 8px;
  }

  .writing-workspace__tool-btn--hero {
    height: 44px;
    min-height: 44px;
    padding-inline: 12px;
  }

  .writing-workspace__label-full {
    display: none;
  }

  .writing-workspace__label-short {
    display: inline;
  }

  .writing-workspace__ai-menu-panel {
    right: 0;
    left: auto;
  }

  .writing-workspace__content {
    padding: var(--md-spacing-4);
  }
}

/* 极致国风脑洞：折页折扇徐徐挂下、模糊渐变清晰的宣纸舒展 */
@keyframes ink-menu-slide {
  from {
    opacity: 0;
    transform: scaleY(0.8) translateY(-8px);
    transform-origin: top right;
  }
  to {
    opacity: 1;
    transform: scaleY(1) translateY(0);
    transform-origin: top right;
  }
}

/* ==========================================================================
   三合一 Tab 切换栏样式与中国风金石重塑
   ========================================================================== */
.writing-workspace__tabs-row {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  margin-top: var(--md-spacing-3);
  padding: 0 var(--md-spacing-4);
  border-bottom: 1.5px solid var(--md-outline-variant);
  padding-bottom: 1px;
}

.writing-workspace__tabs {
  display: flex;
  gap: 4px;
}

.writing-workspace__tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 38px;
  padding: 0 16px;
  border: 1px solid var(--md-outline-variant) !important;
  border-bottom: none !important;
  border-radius: 4px 4px 0 0 !important; /* 笺片式上圆角 */
  background-color: rgba(28, 32, 34, 0.015) !important;
  color: var(--md-on-surface-variant) !important;
  font-family: var(--md-font-serif);
  font-size: 13.5px;
  font-weight: 600;
  cursor: pointer;
  transition:
    background-color 0.2s ease,
    color 0.2s ease,
    box-shadow 0.2s ease;
}

.writing-workspace__tab-btn:hover {
  background-color: var(--md-surface-container-low) !important;
  color: var(--md-primary-dark) !important;
}

/* 激活的朱砂方章笺条 */
.writing-workspace__tab-btn.is-active {
  border: 1.5px solid var(--md-secondary) !important;
  border-bottom: 1.5px solid var(--md-surface) !important; /* 无缝贴合底线 */
  background-color: var(--md-surface) !important; /* 熟宣暖白 */
  color: var(--md-secondary) !important; /* 朱红色 */
  box-shadow: 0 1.5px 0px var(--md-surface);
  margin-bottom: -1.5px; /* 压住底线，呈现一体化连卷 */
  z-index: 10;
}

.tab-badge {
  font-size: 14px;
}

/* 大纲计划概要卡片优化 */
.writing-workspace__summary {
  margin: var(--md-spacing-2) 0 0;
  padding: 0;
  border: none;
  background-color: transparent;
  font-family: var(--md-font-family);
  font-size: 15px;
  font-weight: 500;
  line-height: 1.75;
  letter-spacing: 0.02em;
  color: var(--md-on-surface-variant);
  font-style: normal;
}

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

/* ==========================================================================
   AI 评阅分析面板
   ========================================================================== */
.writing-workspace__evaluation-panel {
  padding-right: var(--md-spacing-2);
  height: 100%;
}

.writing-workspace__evaluation-hero {
  display: flex;
  align-items: flex-start;
  gap: var(--md-spacing-4);
  padding: var(--md-spacing-4);
  border: 3px double var(--md-outline);
  border-radius: var(--md-radius-xs);
  background-color: var(--md-surface-container-low); /* 竹纸底 */
}

.writing-workspace__evaluation-hero .hero-seal {
  width: 38px;
  height: 38px;
  border: 1.5px solid var(--md-secondary);
  border-radius: 50%;
  display: grid;
  place-items: center;
  color: var(--md-secondary);
  font-family: var(--md-font-serif);
  font-size: 16px;
  font-weight: bold;
  background-color: rgba(184, 60, 50, 0.05);
  flex-shrink: 0;
  transform: rotate(-10deg);
  box-shadow: inset 1px 1px 0px rgba(184, 60, 50, 0.2);
}

.writing-workspace__evaluation-hero .hero-text {
  flex: 1;
  min-width: 0;
}

.writing-workspace__evaluation-hero h4 {
  margin: 0 0 6px;
  font-family: var(--md-font-serif);
  font-weight: bold;
  font-size: 16px;
  color: var(--md-primary-dark);
  letter-spacing: 0.05em;
}

.writing-workspace__evaluation-hero p {
  margin: 0;
  color: var(--md-on-surface);
  line-height: 1.6;
}

.writing-workspace__evaluation-card {
  padding: var(--md-spacing-4);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-xs);
  background-color: var(--md-surface);
  transition: border-color 0.2s ease;
}

.writing-workspace__evaluation-card:hover {
  border-color: var(--md-outline);
}

.writing-workspace__evaluation-card .dimension-title {
  margin: 0 0 var(--md-spacing-3);
  font-family: var(--md-font-serif);
  font-weight: 700;
  font-size: 14.5px;
  color: var(--md-primary-dark);
  display: flex;
  align-items: center;
  gap: 6px;
  border-bottom: 1.5px solid var(--md-outline-variant);
  padding-bottom: 4px;
}

.dimension-mark {
  font-size: 14px;
}

.dimension-desc {
  margin: 0;
  color: var(--md-on-surface);
  line-height: 1.6;
  text-justify: inter-character;
}

.writing-workspace__evaluation-card.is-suggestion-card {
  border: 1.5px solid var(--md-outline);
  background-color: var(--md-surface-container-low);
}

.dimension-title.is-suggestion {
  color: var(--md-secondary) !important;
  border-bottom-color: var(--md-outline) !important;
}

.suggestion-list {
  margin: 0;
  padding-left: 20px;
  list-style-type: decimal;
  color: var(--md-on-surface);
  line-height: 1.7;
  font-size: 13.5px;
  font-weight: 500;
}

.suggestion-list li {
  margin-bottom: 8px;
}

.suggestion-list li:last-child {
  margin-bottom: 0;
}
</style>
