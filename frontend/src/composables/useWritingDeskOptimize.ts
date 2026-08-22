import { computed, ref } from 'vue'
import type { ComputedRef, Ref } from 'vue'
import type { Chapter, NovelProject } from '@/api/novel'
import { useWritingDeskProject } from '@/composables/useWritingDeskProject'
import { useWritingDeskVersionDetail } from '@/composables/useWritingDeskVersionDetail'
import {
  useApplyOptimizationMutation,
  useOptimizeRecommendedVersionMutation,
} from '@/queries/novel'
import { cleanVersionContent, normalizeOptimizeResult, parseEvaluationPayload } from '@/utils/chapter'
import { globalAlert } from '@/composables/useAlert'

interface UseWritingDeskOptimizeOptions {
  projectId: () => string
  project: ComputedRef<NovelProject | null>
  selectedChapter: ComputedRef<Chapter | null>
  availableVersions: ReturnType<typeof useWritingDeskVersionDetail>['availableVersions']
  refetchChapterIntoProject: ReturnType<typeof useWritingDeskProject>['refetchChapterIntoProject']
  showEvaluationDetailModal: Ref<boolean>
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === 'object' && !Array.isArray(value)

/**
 * 写作台「评审推荐优化」流程。
 *
 * 从 WritingDesk.vue 抽出（行为逐行等价）。负责基于评审结果推荐版本的优化：
 * optimize 触发后端优化并预览、apply 应用优化正文并投递后处理、close 在应用中拦截关闭。
 * 优化结果 modal 的开关 state、优化内容/备注、优化中/应用中标志、两个 mutation 仅本流程使用，
 * 故内化；showEvaluationDetailModal 来自弹窗 composable（apply 后一并关闭评审详情）。
 */
export const useWritingDeskOptimize = ({
  projectId,
  project,
  selectedChapter,
  availableVersions,
  refetchChapterIntoProject,
  showEvaluationDetailModal,
}: UseWritingDeskOptimizeOptions) => {
  const optimizeRecommendedVersionMutation = useOptimizeRecommendedVersionMutation()
  const applyOptimizationMutation = useApplyOptimizationMutation(projectId)

  const showRecommendedOptimizeResultModal = ref(false)
  const recommendedOptimizedContent = ref('')
  const recommendedOptimizeResultNotes = ref('')

  const isOptimizingRecommendedVersion = computed(
    () => optimizeRecommendedVersionMutation.isPending.value,
  )
  const isApplyingRecommendedOptimization = computed(() => applyOptimizationMutation.isPending.value)

  const closeRecommendedOptimizeResult = () => {
    if (isApplyingRecommendedOptimization.value) return
    showRecommendedOptimizeResultModal.value = false
  }

  const optimizeRecommendedVersionFromEvaluation = async () => {
    if (!project.value || !selectedChapter.value) {
      globalAlert.showError('缺少章节信息，无法执行优化')
      return
    }

    const evaluationPayload = parseEvaluationPayload(selectedChapter.value.evaluation || null)
    if (!evaluationPayload) {
      globalAlert.showError('当前评审结果无法解析，暂时不能执行评审优化')
      return
    }

    const rawBestChoice = evaluationPayload.best_choice
    const bestChoice = typeof rawBestChoice === 'string' || typeof rawBestChoice === 'number'
      ? Number(rawBestChoice)
      : Number.NaN
    if (!Number.isInteger(bestChoice) || bestChoice < 1) {
      globalAlert.showError('当前评审结果缺少推荐版本，无法执行优化')
      return
    }

    const versionIndex = bestChoice - 1
    const sourceVersion = availableVersions.value[versionIndex]
    if (!sourceVersion?.content?.trim()) {
      globalAlert.showError('推荐版本正文不存在，无法执行优化')
      return
    }

    const evaluations = evaluationPayload.evaluation
    const rawVersionReview = isRecord(evaluations) ? evaluations[`version${bestChoice}`] : undefined
    const versionReview = isRecord(rawVersionReview) ? rawVersionReview : {}
    const reasonForChoice = evaluationPayload.reason_for_choice
    try {
      const result = await optimizeRecommendedVersionMutation.mutateAsync({
        project_id: project.value.id,
        chapter_number: selectedChapter.value.chapter_number,
        source_content: cleanVersionContent(sourceVersion.content),
        review_summary: typeof reasonForChoice === 'string' ? reasonForChoice.trim() : '',
        version_number: bestChoice,
        version_review: versionReview,
      })

      const normalized = normalizeOptimizeResult(result.optimized_content, result.optimization_notes)
      if (!normalized.content.trim()) {
        globalAlert.showError('优化结果为空，请稍后重试')
        return
      }

      recommendedOptimizedContent.value = normalized.content
      recommendedOptimizeResultNotes.value = normalized.notes
      showRecommendedOptimizeResultModal.value = true
    } catch (error: unknown) {
      console.error('评审优化失败:', error)
      globalAlert.showError(error instanceof Error && error.message
        ? error.message
        : '评审优化失败，请稍后重试')
    }
  }

  const applyRecommendedOptimization = async () => {
    if (!project.value || !selectedChapter.value || !recommendedOptimizedContent.value.trim()) {
      return
    }

    try {
      const applyResult = await applyOptimizationMutation.mutateAsync({
        projectId: project.value.id,
        chapterNumber: selectedChapter.value.chapter_number,
        optimizedContent: recommendedOptimizedContent.value,
      })

      globalAlert.showToast(applyResult.message, 'success')

      showRecommendedOptimizeResultModal.value = false
      showEvaluationDetailModal.value = false
      recommendedOptimizedContent.value = ''
      recommendedOptimizeResultNotes.value = ''
      await refetchChapterIntoProject(selectedChapter.value.chapter_number)
    } catch (error: unknown) {
      console.error('应用评审优化失败:', error)
      globalAlert.showError(error instanceof Error && error.message
        ? error.message
        : '应用优化失败，请稍后重试')
    }
  }

  return {
    showRecommendedOptimizeResultModal,
    recommendedOptimizedContent,
    recommendedOptimizeResultNotes,
    isOptimizingRecommendedVersion,
    isApplyingRecommendedOptimization,
    closeRecommendedOptimizeResult,
    optimizeRecommendedVersionFromEvaluation,
    applyRecommendedOptimization,
  }
}
