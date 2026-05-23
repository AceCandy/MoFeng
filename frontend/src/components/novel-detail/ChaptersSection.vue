<!-- AIMETA P=章节区_章节列表展示|R=章节列表_状态|NR=不含编辑功能|E=component:ChaptersSection|X=ui|A=章节组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="flex flex-col h-full min-h-0 overflow-hidden relative">
    <div class="flex flex-row flex-1 h-full lg:min-h-0 overflow-hidden">
      <!-- 移动端遮罩层 -->
      <div
        v-if="showChapterList"
        class="fixed inset-0 bg-[var(--md-scrim)] z-40 lg:hidden"
        @click="showChapterList = false"
      ></div>

      <!-- 章节列表侧边栏 -->
      <aside
        class="fixed lg:static inset-y-0 left-0 z-50 w-72 lg:w-72 bg-[var(--md-surface)] lg:bg-[var(--md-surface-container-low)] border-r border-[var(--md-outline-variant)] flex flex-col h-full min-h-0 max-h-full overflow-hidden transition-transform duration-300 lg:translate-x-0 shadow-2xl lg:shadow-none"
        :class="showChapterList ? 'translate-x-0' : '-translate-x-full'"
      >
        <div class="px-5 py-4 border-b border-[var(--md-outline-variant)] flex items-center justify-between">
          <h3 class="text-base font-semibold text-[var(--md-on-surface)]">章节</h3>
          <span class="text-xs text-[var(--md-on-surface-variant)]">{{ chapters.length }} 篇</span>
        </div>
        <ul class="flex-1 h-full overflow-y-auto divide-y divide-[var(--md-outline-variant)] overscroll-contain">
          <li v-for="(chapter, index) in chapters" :key="chapter.chapter_number">
            <button
              :ref="(el) => setChapterRef(chapter.chapter_number, el)"
              class="w-full text-left px-5 py-3 transition-colors duration-200"
              :class="selectedChapter?.chapter_number === chapter.chapter_number ? 'bg-[var(--md-primary-container)] text-[var(--md-primary)] font-semibold' : 'hover:bg-[var(--md-surface-container-low)] lg:hover:bg-[var(--md-surface)] text-[var(--md-on-surface)]'"
              @click="selectChapter(chapter.chapter_number)"
            >
              <div class="flex items-center justify-between gap-3">
                <div class="flex items-center gap-3 min-w-0">
                  <span class="inline-flex items-center justify-center w-6 h-6 text-xs font-semibold text-[var(--md-on-surface-variant)] bg-[var(--md-surface-container)] rounded-xs border border-[var(--md-outline-variant)]">
                    {{ index + 1 }}
                  </span>
                  <span class="truncate">{{ chapter.title || `第${chapter.chapter_number}章` }}</span>
                </div>
                <span
                  v-if="selectedChapter?.chapter_number === chapter.chapter_number"
                  class="text-xs text-[var(--md-on-surface-variant)]"
                >
                  {{ calculateWordCount(selectedChapter.content) }} 字
                </span>
                <span v-else class="text-xs text-[var(--md-on-surface-variant)]">-</span>
              </div>
              <p v-if="chapter.summary" class="mt-1 text-xs text-[var(--md-on-surface-variant)] truncate">
                {{ chapter.summary }}
              </p>
            </button>
          </li>
        </ul>
      </aside>

      <section class="flex-1 flex flex-col bg-[var(--md-surface)] h-full min-h-0 max-h-full overflow-hidden relative">
        <!-- 移动端浮动按钮 -->
        <button
          type="button"
          v-if="!showChapterList"
          @click="showChapterList = true"
          class="lg:hidden fixed bottom-6 left-6 z-30 w-14 h-14 bg-[var(--md-primary)] text-[var(--md-on-primary)] rounded-xs shadow-[4px_4px_0px_rgba(28,32,34,0.15)] flex items-center justify-center hover:bg-[var(--md-primary-dark)] transition-colors focus-visible:outline-2 focus-visible:outline-[var(--md-primary)] focus-visible:outline-offset-2"
          aria-label="打开章节列表"
          title="打开章节列表"
        >
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        <!-- Loading State -->
        <div v-if="isLoading" class="h-full flex items-center justify-center">
          <div class="text-center">
            <div class="w-10 h-10 border-4 border-[var(--md-primary-container)] border-t-[var(--md-primary)] rounded-full animate-spin mx-auto mb-3"></div>
            <p class="text-sm text-[var(--md-on-surface-variant)]">加载中...</p>
          </div>
        </div>

        <!-- Error State -->
        <div v-else-if="error" class="h-full flex items-center justify-center">
          <div class="text-center">
            <div class="w-12 h-12 bg-[var(--md-error-container)] rounded-full flex items-center justify-center mx-auto mb-3">
              <svg class="w-6 h-6 text-[var(--md-error-text)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <p class="text-sm text-[var(--md-on-surface-variant)]">{{ error }}</p>
          </div>
        </div>

        <!-- Content -->
        <template v-else-if="selectedChapter">
          <!-- Header with Status and Tabs -->
          <header class="px-6 py-4 border-b border-[var(--md-outline-variant)] bg-[var(--md-surface-container-low)]">
            <div class="flex items-start justify-between gap-4 mb-3">
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 flex-wrap">
                  <h4 class="text-xl font-bold text-[var(--md-on-surface)]">{{ selectedChapter.title || `第${selectedChapter.chapter_number}章` }}</h4>
                </div>
                <div class="flex items-center gap-3 mt-1.5">
                  <span class="text-sm text-[var(--md-on-surface-variant)]">第 {{ selectedChapter.chapter_number }} 章</span>
                  <span class="text-sm text-[var(--md-on-surface-variant)]">·</span>
                  <span class="text-sm text-[var(--md-on-surface-variant)]">{{ calculateWordCount(selectedChapter.content) }} 字</span>
                </div>
              </div>
              <div class="flex items-center gap-2 flex-wrap justify-end">
                <button
                  class="inline-flex items-center gap-1 min-h-[44px] px-3.5 py-2 text-sm font-medium rounded-xs border transition-colors duration-200 focus-visible:outline-2 focus-visible:outline-[var(--md-primary)] focus-visible:outline-offset-2"
                  :class="selectedChapter?.content ? 'border-[var(--md-primary-container)] text-[var(--md-on-primary-container)] hover:bg-[var(--md-primary-container)]' : 'border-[var(--md-outline-variant)] text-[var(--md-on-surface-variant)] cursor-not-allowed'"
                  :disabled="!selectedChapter?.content"
                  @click="exportChapterAsTxt"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v16h16V4m-4 4l-4-4-4 4m4-4v12" />
                  </svg>
                  导出TXT
                </button>
                <span v-if="selectedChapter.generation_status"
                  class="m3-signet-seal px-3 py-1 text-xs font-medium border rounded-xs"
                  :class="getStatusColor(selectedChapter.generation_status)">
                  {{ getStatusLabel(selectedChapter.generation_status) }}
                </span>
              </div>
            </div>

            <!-- Tab Navigation -->
            <div class="flex gap-2">
              <button
                v-for="tab in tabs"
                :key="tab.key"
                @click="activeTab = tab.key"
                class="px-4 py-2 min-h-[44px] text-sm font-medium rounded-xs border border-transparent transition-[background-color,box-shadow,color] duration-200 focus-visible:outline-2 focus-visible:outline-[var(--md-primary)] focus-visible:outline-offset-2"
                :class="activeTab === tab.key
                  ? 'bg-[var(--md-surface)] text-[var(--md-primary)] border-[var(--md-outline)] shadow-[2px_2px_0px_rgba(28,32,34,0.15)]'
                  : 'text-[var(--md-on-surface-variant)] hover:text-[var(--md-on-surface)] hover:bg-[var(--md-surface-container-lowest)]'"
              >
                {{ tab.label }}
                <span v-if="tab.badge && getTabBadgeCount(tab.key)"
                  class="ml-1.5 px-1.5 py-0.5 text-xs rounded-xs border border-[var(--md-outline-variant)]"
                  :class="activeTab === tab.key ? 'bg-[var(--md-primary-container)] text-[var(--md-primary)]' : 'bg-[var(--md-surface-container-high)] text-[var(--md-on-surface-variant)]'">
                  {{ getTabBadgeCount(tab.key) }}
                </span>
              </button>
            </div>
          </header>

          <!-- Tab Content -->
          <article class="flex-1 overflow-y-auto min-h-0 overscroll-contain">
            <!-- 正文 Tab -->
            <div v-show="activeTab === 'content'" class="px-2 py-3">
              <div class="max-w-full space-y-4">
                <!-- Summary Cards -->
                <div v-if="selectedChapter.summary || selectedChapter.real_summary" class="grid gap-4">
                  <div v-if="selectedChapter.summary" class="bg-[var(--md-surface-container-low)] border border-[var(--md-outline-variant)] rounded-sm p-4">
                    <h5 class="text-xs font-semibold text-[var(--md-on-surface)] mb-2 flex items-center gap-1.5">
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      计划大纲
                    </h5>
                    <p class="text-sm text-[var(--md-on-surface)] leading-relaxed">{{ selectedChapter.summary }}</p>
                  </div>
                  <div v-if="selectedChapter.real_summary" class="bg-[var(--md-success-container)] border border-[color-mix(in_oklch,var(--md-success)_20%,transparent)] rounded-sm p-4">
                    <h5 class="text-xs font-semibold text-[var(--md-success-text)] mb-2 flex items-center gap-1.5">
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                      </svg>
                      实际内容概要
                    </h5>
                    <div class="prose prose-sm prose-green max-w-none text-[var(--md-success-text)]" v-html="renderMarkdown(selectedChapter.real_summary)"></div>
                  </div>
                </div>

                <!-- Main Content -->
                <div class="prose prose-slate max-w-none p-4 sm:p-6 rounded-sm bg-[var(--md-surface-container-low)]">
                  <div class="text-base text-[var(--md-on-surface)] leading-8 whitespace-pre-wrap font-serif">
                    {{ selectedChapter.content || '暂无内容' }}
                  </div>
                </div>
              </div>
            </div>

            <!-- 版本 Tab -->
            <div v-show="activeTab === 'versions'" class="px-2 py-3">
              <div class="max-w-full">
                <div v-if="selectedChapter.versions && selectedChapter.versions.length > 0" class="space-y-4">
                  <button v-for="(version, index) in selectedChapter.versions" :key="index"
                    type="button"
                    class="chapter-version-card group"
                    :aria-label="`查看版本 ${index + 1} 全文，${calculateWordCount(version)} 字`"
                    @click="openVersionModal(version, index)">
                    <span class="chapter-version-card__head">
                      <span class="chapter-version-card__title">
                        <span class="chapter-version-card__index">
                          {{ index + 1 }}
                        </span>
                        <span>版本 {{ index + 1 }}</span>
                      </span>
                      <span class="chapter-version-card__meta">
                        <span class="text-xs text-[var(--md-on-surface-variant)]">{{ calculateWordCount(version) }} 字</span>
                        <span class="chapter-version-card__hint">
                          查看全文
                        </span>
                      </span>
                    </span>
                    <span class="chapter-version-card__excerpt line-clamp-4">
                      {{ version }}
                    </span>
                  </button>
                </div>
                <div v-else class="text-center py-12 text-[var(--md-on-surface-variant)]">
                  暂无版本记录
                </div>
              </div>
            </div>

            <!-- 评审 Tab -->
            <div v-show="activeTab === 'evaluation'" class="px-2 py-3">
              <div class="max-w-full">
                <div v-if="evaluationData" class="space-y-4">
                  <!-- 最佳选择 -->
                  <div v-if="evaluationData.best_choice" class="bg-[var(--md-primary-container)] border border-[var(--md-primary-container)] rounded-sm p-4">
                    <div class="flex items-start gap-4">
                      <div class="w-12 h-12 bg-[var(--md-primary)] rounded-xs flex items-center justify-center flex-shrink-0">
                        <svg class="w-7 h-7 text-[var(--md-on-primary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
                        </svg>
                      </div>
                      <div class="flex-1">
                        <h5 class="text-lg font-bold text-[var(--md-on-primary-container)] mb-2">最佳版本选择</h5>
                        <div class="flex items-center gap-2 mb-3">
                          <span class="px-3 py-1 bg-[var(--md-primary)] text-[var(--md-on-primary)] text-sm font-bold rounded-xs">
                            版本 {{ evaluationData.best_choice }}
                          </span>
                        </div>
                        <p v-if="evaluationData.reason_for_choice" class="text-sm text-[var(--md-on-primary-container)] leading-relaxed">
                          {{ evaluationData.reason_for_choice }}
                        </p>
                      </div>
                    </div>
                  </div>

                  <!-- 各版本详细评审 -->
                  <div v-if="evaluationData.evaluation" class="space-y-4">
                    <div v-for="(versionEval, versionKey) in evaluationData.evaluation" :key="versionKey"
                      class="border border-[var(--md-outline-variant)] rounded-sm overflow-hidden"
                      :class="isSelectedVersion(versionKey, evaluationData.best_choice) ? 'ring-2 ring-[var(--md-primary-light)]' : ''">
                      <!-- 版本标题 -->
                      <div class="px-5 py-3 bg-[var(--md-surface-container-low)] border-b border-[var(--md-outline-variant)] flex items-center justify-between">
                        <h6 class="font-bold text-[var(--md-on-surface)] flex items-center gap-2">
                          <span class="w-6 h-6 bg-[var(--md-on-surface)] text-[var(--md-surface)] rounded-xs flex items-center justify-center text-xs">
                            {{ getVersionNumber(versionKey) }}
                          </span>
                          {{ getVersionLabel(versionKey) }}
                        </h6>
                        <span v-if="isSelectedVersion(versionKey, evaluationData.best_choice)"
                          class="px-2.5 py-1 bg-[var(--md-primary-container)] text-[var(--md-primary-dark)] text-xs font-semibold rounded-xs">
                          最佳
                        </span>
                      </div>

                      <div class="p-4 space-y-3">
                        <!-- 优点 -->
                        <div v-if="versionEval.pros && versionEval.pros.length > 0"
                          class="bg-[var(--md-success-container)] border border-[color-mix(in_oklch,var(--md-success)_20%,transparent)] rounded-lg p-3">
                          <h6 class="text-xs font-bold text-[var(--md-success-text)] mb-2 flex items-center gap-1.5">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                            </svg>
                            优点
                          </h6>
                          <ul class="space-y-1.5">
                            <li v-for="(item, idx) in versionEval.pros" :key="idx"
                              class="flex items-start gap-2 text-xs text-[var(--md-success-text)] leading-relaxed">
                              <span class="w-1 h-1 bg-[var(--md-success)] rounded-full mt-1.5 flex-shrink-0"></span>
                              <span>{{ item }}</span>
                            </li>
                          </ul>
                        </div>

                        <!-- 缺点 -->
                        <div v-if="versionEval.cons && versionEval.cons.length > 0"
                          class="bg-[var(--md-error-container)] border border-[color-mix(in_oklch,var(--md-error)_20%,transparent)] rounded-lg p-3">
                          <h6 class="text-xs font-bold text-[var(--md-error-text)] mb-2 flex items-center gap-1.5">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                            </svg>
                            缺点
                          </h6>
                          <ul class="space-y-1.5">
                            <li v-for="(item, idx) in versionEval.cons" :key="idx"
                              class="flex items-start gap-2 text-xs text-[var(--md-error-text)] leading-relaxed">
                              <span class="w-1 h-1 bg-[var(--md-error)] rounded-full mt-1.5 flex-shrink-0"></span>
                              <span>{{ item }}</span>
                            </li>
                          </ul>
                        </div>

                        <!-- 总体评价 -->
                        <div v-if="versionEval.overall_review"
                          class="bg-[var(--md-surface-container-low)] border border-[var(--md-outline-variant)] rounded-lg p-3">
                          <h6 class="text-xs font-bold text-[var(--md-on-surface)] mb-2">总体评价</h6>
                          <p class="text-xs text-[var(--md-on-surface)] leading-relaxed">{{ versionEval.overall_review }}</p>
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- 简单格式兼容 -->
                  <div v-else-if="evaluationData.decision || evaluationData.feedback" class="space-y-4">
                    <!-- 评审决策 -->
                    <div v-if="evaluationData.decision" class="bg-[var(--md-primary-container)] border border-[var(--md-primary-container)] rounded-sm p-4">
                      <div class="flex items-center gap-3 mb-4">
                        <div class="w-10 h-10 bg-[var(--md-primary)] rounded-xs flex items-center justify-center">
                          <svg class="w-6 h-6 text-[var(--md-on-primary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                        </div>
                        <div>
                          <h5 class="text-sm font-bold text-[var(--md-on-primary-container)]">评审决策</h5>
                          <p class="text-xs text-[var(--md-primary-dark)]">{{ evaluationData.decision }}</p>
                        </div>
                      </div>
                    </div>

                    <!-- 评分卡片 -->
                    <div v-if="evaluationData.scores" class="grid grid-cols-2 md:grid-cols-3 gap-4">
                      <div v-for="(score, key) in evaluationData.scores" :key="key"
                        class="bg-[var(--md-surface)] border border-[var(--md-outline-variant)] rounded-sm p-4 hover:shadow-[2px_2px_0px_rgba(28,32,34,0.15)] transition-shadow">
                        <div class="flex items-center justify-between mb-2">
                          <span class="text-xs font-medium text-[var(--md-on-surface-variant)]">{{ getScoreLabel(key) }}</span>
                          <span class="text-lg font-bold" :class="getScoreColor(score)">{{ score }}</span>
                        </div>
                        <div class="w-full bg-[var(--md-surface-container)] rounded-xs h-2">
                          <div class="h-2 w-full origin-left rounded-xs transition-transform duration-300"
                            :class="getScoreBarColor(score)"
                            :style="{ transform: `scaleX(${score / 10})` }"></div>
                        </div>
                      </div>
                    </div>

                    <!-- 详细反馈 -->
                    <div v-if="evaluationData.feedback"
                      class="bg-[var(--md-surface-container-low)] border border-[var(--md-outline-variant)] rounded-sm p-4">
                      <h5 class="text-sm font-bold text-[var(--md-on-surface)] mb-3">详细反馈</h5>
                      <p class="text-sm text-[var(--md-on-surface)] leading-relaxed whitespace-pre-wrap">{{ evaluationData.feedback }}</p>
                    </div>
                  </div>
                </div>

                <div v-else class="text-center py-12">
                  <div class="w-16 h-16 bg-[var(--md-surface-container)] rounded-xs flex items-center justify-center mx-auto mb-3">
                    <svg class="w-8 h-8 text-[var(--md-on-surface-variant)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <p class="text-[var(--md-on-surface-variant)]">暂无评审意见</p>
                </div>
              </div>
            </div>
          </article>
        </template>

        <!-- Empty State -->
        <div v-else class="h-full flex items-center justify-center text-[var(--md-on-surface-variant)]">
          <div class="text-center">
            <svg class="w-16 h-16 mx-auto mb-3 text-[var(--md-outline)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
            <p class="text-sm">请选择章节查看详细内容</p>
          </div>
        </div>
      </section>
    </div>

    <!-- 版本全文弹窗 -->
    <transition
      enter-active-class="transition-opacity duration-300"
      leave-active-class="transition-opacity duration-300"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <div v-if="versionModal.show" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--md-scrim)]"
        @click.self="closeVersionModal">
        <div
          ref="versionDialogRef"
          class="bg-[var(--md-surface)] rounded-md border-3 border-double border-[var(--md-outline)] shadow-[4px_4px_0px_rgba(28,32,34,0.15)] max-w-4xl w-full max-h-[85vh] overflow-hidden"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="versionModalTitleId"
        >
          <!-- Modal Header -->
          <div class="flex items-center justify-between px-6 py-4 border-b border-[var(--md-outline-variant)] bg-[var(--md-surface-container-low)]">
            <div class="flex items-center gap-3">
              <span class="w-8 h-8 bg-[var(--md-primary)] text-[var(--md-on-primary)] rounded-xs flex items-center justify-center text-sm font-bold border border-[var(--md-outline-variant)]">
                {{ versionModal.index + 1 }}
              </span>
              <div>
                <h3 :id="versionModalTitleId" class="text-lg font-bold text-[var(--md-on-surface)]">版本 {{ versionModal.index + 1 }}</h3>
                <p class="text-xs text-[var(--md-on-surface-variant)]">{{ calculateWordCount(versionModal.content) }} 字</p>
              </div>
            </div>
            <button
              ref="versionCloseButtonRef"
              type="button"
              class="md-icon-btn focus-visible:outline-2 focus-visible:outline-[var(--md-primary)] focus-visible:outline-offset-2"
              aria-label="关闭版本全文弹窗"
              title="关闭版本全文弹窗"
              data-dialog-initial-focus
              @click="closeVersionModal"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <!-- Modal Content -->
          <div class="overflow-y-auto p-6 max-h-[calc(85vh-5rem)]">
            <div class="prose prose-slate max-w-none">
              <div class="text-base text-[var(--md-on-surface)] leading-8 whitespace-pre-wrap font-serif">
                {{ versionModal.content }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import type { ComponentPublicInstance } from 'vue'
import { useRoute } from 'vue-router'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { useNovelChapterDetailQuery } from '@/queries/novel'
import { useDialogA11y } from '@/composables/useDialogA11y'
import { resolveChapterNumberForEntry } from '@/utils/chapter'

interface ChapterItem {
  chapter_number: number
  title?: string | null
  summary?: string | null
  content?: string | null
  generation_status?: string | null
  word_count?: number
}

interface ChapterDetail extends ChapterItem {
  real_summary?: string | null
  versions?: string[] | null
  evaluation?: string | null
  generation_status?: string | null
}

const props = defineProps<{
  chapters: ChapterItem[]
  chapterOutlines?: ChapterItem[]
  isAdmin?: boolean
}>()

const route = useRoute()
const projectId = route.params.id as string

const selectedChapterNumber = ref<number | null>(null)
const chapterQuery = useNovelChapterDetailQuery(
  () => projectId,
  () => selectedChapterNumber.value,
  () => props.isAdmin,
)
const selectedChapter = computed<ChapterDetail | null>(() => {
  if (chapterQuery.data.value) {
    return chapterQuery.data.value as ChapterDetail
  }
  return (
    chapters.value.find((chapter) => chapter.chapter_number === selectedChapterNumber.value) ??
    null
  )
})
const isLoading = computed(() => chapterQuery.isLoading.value || chapterQuery.isFetching.value)
const error = computed(() => {
  const queryError = chapterQuery.error.value
  return queryError instanceof Error ? queryError.message : queryError ? String(queryError) : null
})
const activeTab = ref<'content' | 'versions' | 'evaluation'>('content')

// 移动端章节列表显示状态
const showChapterList = ref(false)

// 版本弹窗状态
const versionModal = ref({
  show: false,
  content: '',
  index: 0
})
const versionDialogRef = ref<HTMLElement | null>(null)
const versionCloseButtonRef = ref<HTMLElement | null>(null)
const isVersionModalOpen = computed(() => versionModal.value.show)
const versionModalTitleId = 'chapter-version-modal-title'

const chapters = computed(() => props.chapters || [])
const chapterOutlines = computed(() => props.chapterOutlines || [])
const chapterRefs = ref<Record<number, HTMLElement | null>>({})

// Tab 配置
const tabs = [
  { key: 'content' as const, label: '正文', badge: false },
  { key: 'versions' as const, label: '版本', badge: true },
  { key: 'evaluation' as const, label: '评审', badge: false }
]

// 计算字数的辅助函数
const calculateWordCount = (content: string | null | undefined): number => {
  if (!content) return 0
  // 移除所有空白字符后计算字数
  return content.replace(/\s/g, '').length
}

// 获取状态标签
const getStatusLabel = (status: string): string => {
  const statusMap: Record<string, string> = {
    'not_generated': '未生成',
    'generating': '生成中',
    'evaluating': '评审中',
    'selecting': '选择中',
    'failed': '生成失败',
    'evaluation_failed': '评审失败',
    'waiting_for_confirm': '待确认',
    'successful': '已完成'
  }
  return statusMap[status] || status
}

// 获取状态颜色
const getStatusColor = (status: string): string => {
  const colorMap: Record<string, string> = {
    'not_generated': 'border-[var(--md-outline-variant)] bg-[var(--md-surface-container)] text-[var(--md-on-surface-variant)]',
    'generating': 'border-[var(--md-primary)] bg-[var(--md-surface-container-low)] text-[var(--md-primary)]',
    'evaluating': 'border-[var(--md-primary-container)] bg-[var(--md-primary-container)] text-[var(--md-on-primary-container)]',
    'selecting': 'border-[var(--md-warning)] bg-[var(--md-warning-container)] text-[var(--md-warning-text)]',
    'failed': 'border-[var(--md-error)] bg-[var(--md-error-container)] text-[var(--md-error-text)]',
    'evaluation_failed': 'border-[var(--md-error)] bg-[var(--md-error-container)] text-[var(--md-error-text)]',
    'waiting_for_confirm': 'border-[var(--md-warning)] bg-[var(--md-warning-container)] text-[var(--md-warning-text)]',
    'successful': 'border-[var(--md-secondary)] bg-[var(--md-secondary-container)] text-[var(--md-secondary)]'
  }
  return colorMap[status] || 'border-[var(--md-outline-variant)] bg-[var(--md-surface-container)] text-[var(--md-on-surface-variant)]'
}

// 获取 Tab Badge 数量
const getTabBadgeCount = (tabKey: string): number => {
  if (!selectedChapter.value) return 0
  if (tabKey === 'versions') {
    return selectedChapter.value.versions?.length || 0
  }
  return 0
}

const sanitizeFileName = (name: string): string => {
  return name.replace(/[\\/:*?"<>|]/g, '_')
}

const exportChapterAsTxt = () => {
  const chapter = selectedChapter.value
  if (!chapter) return

  const title = chapter.title?.trim() || `第${chapter.chapter_number}章`
  const safeTitle = sanitizeFileName(title) || `chapter-${chapter.chapter_number}`
  const content = chapter.content ?? ''
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${safeTitle}.txt`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

// 打开版本弹窗
const openVersionModal = (content: string, index: number) => {
  versionModal.value = {
    show: true,
    content,
    index
  }
}

// 关闭版本弹窗
const closeVersionModal = () => {
  versionModal.value.show = false
}

useDialogA11y({
  active: isVersionModalOpen,
  dialogRef: versionDialogRef,
  onClose: closeVersionModal,
  initialFocusRef: versionCloseButtonRef,
})

// 解析评审数据
const evaluationData = computed(() => {
  if (!selectedChapter.value?.evaluation) return null

  try {
    // 尝试解析 JSON
    const parsed = JSON.parse(selectedChapter.value.evaluation)
    return parsed
  } catch {
    // 如果不是 JSON，返回简单的文本格式
    return {
      feedback: selectedChapter.value.evaluation
    }
  }
})

// 获取评分标签
const getScoreLabel = (key: string | number): string => {
  const normalizedKey = typeof key === 'number' ? key.toString() : key
  const labelMap: Record<string, string> = {
    'plot': '情节',
    'character': '人物',
    'writing': '文笔',
    'logic': '逻辑',
    'emotion': '情感',
    'creativity': '创意',
    'coherence': '连贯性',
    'engagement': '吸引力'
  }
  return labelMap[normalizedKey] || normalizedKey
}

// 获取评分颜色
const getScoreColor = (score: number): string => {
  if (score >= 8) return 'text-[var(--md-success-text)]'
  if (score >= 6) return 'text-[var(--md-primary)]'
  if (score >= 4) return 'text-[var(--md-warning-text)]'
  return 'text-[var(--md-error-text)]'
}

// 获取评分条颜色
const getScoreBarColor = (score: number): string => {
  if (score >= 8) return 'bg-[var(--md-success)]'
  if (score >= 6) return 'bg-[var(--md-primary)]'
  if (score >= 4) return 'bg-[var(--md-warning)]'
  return 'bg-[var(--md-error)]'
}

// 从版本 key 中提取版本号 (version1 -> 1)
const getVersionNumber = (versionKey: string | number): number => {
  const normalizedKey = typeof versionKey === 'number' ? versionKey.toString() : versionKey
  const match = normalizedKey.match(/\d+/)
  return match ? parseInt(match[0]) : 0
}

// 获取版本标签
const getVersionLabel = (versionKey: string | number): string => {
  const num = getVersionNumber(versionKey)
  return `版本 ${num}`
}

// 判断是否为选中的版本
const isSelectedVersion = (versionKey: string | number, bestChoice?: number): boolean => {
  if (!bestChoice) return false
  return getVersionNumber(versionKey) === bestChoice
}

// 渲染 Markdown
const renderMarkdown = (text: string | null | undefined): string => {
  if (!text) return ''
  try {
    const parsed = marked.parse(text, { breaks: true }) as string
    return DOMPurify.sanitize(parsed, {
      USE_PROFILES: { html: true },
    })
  } catch (error) {
    console.error('Markdown 渲染失败:', error)
    return text
  }
}

function setChapterRef(chapterNumber: number, el: Element | ComponentPublicInstance | null) {
  if (!el) {
    delete chapterRefs.value[chapterNumber]
    return
  }

  const element = el instanceof Element ? el : el.$el instanceof Element ? el.$el : null
  if (element) {
    chapterRefs.value[chapterNumber] = element as HTMLElement
  }
}

const scrollToChapter = async (chapterNumber: number | null) => {
  if (chapterNumber === null) return
  await nextTick()
  const element = chapterRefs.value[chapterNumber]
  if (!element) return
  element.scrollIntoView({
    behavior: shouldReduceMotion() ? 'auto' : 'smooth',
    block: 'center',
    inline: 'nearest',
  })
}

const shouldReduceMotion = (): boolean => {
  if (typeof window === 'undefined') return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

watch(
  chapters,
  (list) => {
    if (list.length === 0) {
      selectedChapterNumber.value = null
      return
    }
    const stillExists = list.some((chapter) => chapter.chapter_number === selectedChapterNumber.value)
    if (!selectedChapterNumber.value || !stillExists) {
      selectedChapterNumber.value = resolveChapterNumberForEntry({
        outlines: chapterOutlines.value,
        chapters: list,
      })
    }
  },
  { immediate: true }
)

watch(
  () => selectedChapterNumber.value,
  (chapterNumber) => {
    void scrollToChapter(chapterNumber)
  },
  { immediate: true },
)

const selectChapter = async (chapterNumber: number) => {
  activeTab.value = 'content' // 切换章节时重置到正文标签
  selectedChapterNumber.value = chapterNumber
  // 移动端选择章节后关闭章节列表
  showChapterList.value = false
}

const isAdmin = computed(() => props.isAdmin ?? false)

defineExpose({
  focusChapter: async (chapterNumber: number) => {
    const target = chapters.value.find(ch => ch.chapter_number === chapterNumber)
    if (target) {
      selectedChapterNumber.value = chapterNumber
      await nextTick()
      await chapterQuery.refetch()
    }
  }
})
</script>

<style scoped>
.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.line-clamp-4 {
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.line-clamp-6 {
  display: -webkit-box;
  -webkit-line-clamp: 6;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.chapter-version-card {
  width: 100%;
  display: block;
  padding: 1.25rem;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-sm, 4px);
  background-color: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition:
    background-color var(--md-duration-short) var(--md-easing-standard),
    border-color var(--md-duration-short) var(--md-easing-standard),
    box-shadow var(--md-duration-short) var(--md-easing-standard);
}

.chapter-version-card:hover {
  border-color: var(--md-primary);
  box-shadow: 2px 2px 0px rgba(28, 32, 34, 0.15);
}

.chapter-version-card:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}

.chapter-version-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--md-spacing-3);
  margin-bottom: var(--md-spacing-3);
}

.chapter-version-card__title,
.chapter-version-card__meta {
  display: inline-flex;
  align-items: center;
  gap: var(--md-spacing-2);
}

.chapter-version-card__title {
  color: var(--md-on-surface);
  font-size: 0.875rem;
  font-weight: 600;
}

.chapter-version-card__index {
  width: 1.5rem;
  height: 1.5rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--md-radius-xs, 2px);
  border: 1px solid var(--md-outline-variant);
  background-color: var(--md-surface-container);
  color: var(--md-on-surface);
  font-size: 0.75rem;
  font-weight: 700;
}

.chapter-version-card__meta {
  flex-shrink: 0;
}

.chapter-version-card__hint {
  color: var(--md-primary);
  font-size: 0.75rem;
  font-weight: 500;
  opacity: 0;
  transition: opacity var(--md-duration-short) var(--md-easing-standard);
}

.chapter-version-card:hover .chapter-version-card__hint,
.chapter-version-card:focus-visible .chapter-version-card__hint {
  opacity: 1;
}

.m3-signet-seal {
  font-family: 'STSong', 'Songti SC', serif;
  font-weight: 700;
  letter-spacing: 0.05em;
  border-style: solid;
  border-width: 1px;
  border-radius: var(--md-radius-xs, 2px);
  position: relative;
  /* 增加仿古驳杂底纹 */
  background-image: linear-gradient(45deg, rgba(255,255,255,0.05) 25%, transparent 25%, transparent 50%, rgba(255,255,255,0.05) 50%, rgba(255,255,255,0.05) 75%, transparent 75%, transparent);
  background-size: 8px 8px;
}

.chapter-version-card__excerpt {
  display: -webkit-box;
  color: var(--md-on-surface);
  font-size: 0.875rem;
  line-height: 1.75;
  white-space: pre-wrap;
}

@media (max-width: 640px) {
  .chapter-version-card__head {
    align-items: flex-start;
    flex-direction: column;
  }

  .chapter-version-card__hint {
    opacity: 1;
  }
}
</style>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'ChaptersSection'
})
</script>
