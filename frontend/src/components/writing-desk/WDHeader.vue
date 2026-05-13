<!-- AIMETA P=写作台头部_顶部导航栏|R=导航_操作按钮|NR=不含内容区域|E=component:WDHeader|X=ui|A=头部组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="md-top-app-bar md-elevation-1 flex-shrink-0 z-30 backdrop-blur-md">
    <div class="w-full px-4 sm:px-6 lg:px-8">
      <div class="flex items-center justify-between h-16">
        <!-- 左侧：项目信息 -->
        <div class="flex items-center gap-2 sm:gap-4 min-w-0">
          <button @click="$emit('goBack')" class="md-icon-btn md-ripple flex-shrink-0">
            <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L4.414 9H17a1 1 0 110 2H4.414l5.293 5.293a1 1 0 010 1.414z" clip-rule="evenodd"></path>
            </svg>
          </button>
          <div class="min-w-0">
            <h1 class="md-title-large font-semibold truncate">{{ project?.title || '加载中...' }}</h1>
            <div class="hidden sm:flex items-center gap-2 md:gap-4 md-body-small md-on-surface-variant">
              <span>{{ project?.blueprint?.genre || '--' }}</span>
              <span class="hidden md:inline">•</span>
              <span class="hidden md:inline">{{ progress }}% 完成</span>
              <span class="hidden lg:inline">•</span>
              <span class="hidden lg:inline">{{ completedChapters }}/{{ totalChapters }} 章</span>
            </div>
          </div>
        </div>

        <!-- 右侧：操作按钮 -->
        <div class="flex items-center gap-1 sm:gap-2">
          <button
            v-if="hasIncompleteChapters"
            @click="$emit('locateIncomplete')"
            class="md-btn md-btn-tonal md-ripple flex items-center gap-2"
          >
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span class="hidden sm:inline">定位到未完成</span>
            <span class="sm:hidden">未完成</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { NovelProject } from '@/api/novel'

interface Props {
  project: NovelProject | null
  progress: number
  completedChapters: number
  totalChapters: number
  hasIncompleteChapters: boolean
}

defineProps<Props>()

defineEmits(['goBack', 'locateIncomplete'])
</script>
