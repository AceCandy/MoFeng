import { ref, type Ref } from 'vue'
import type { NovelProject, AllSectionType } from '@/api/novel'
import type { useUpdateBlueprintMutation } from '@/queries/novel'

type SectionKey = AllSectionType

type BlueprintMutation = ReturnType<typeof useUpdateBlueprintMutation>

/**
 * NovelDetailShell 的蓝图字段编辑状态机：
 * - 编辑 Modal 开关与字段缓存（isModalOpen/modalTitle/modalContent/modalField）
 * - handleSectionEdit：分区组件触发编辑，缓存 field/title/value 并打开 Modal
 * - handleSave：拼装 blueprint payload、提交 mutation、按 field 反查并 reload 相关分区、关闭 Modal
 * - resolveSectionKey：依据 blueprint field 前缀反查需 reload 的分区（handleSave 内部用，不对外返回）
 *
 * 数据源（novel/ensureProjectLoaded/updateBlueprintMutation/loadSection）由父组件透传，
 * 本 composable 不持有 query 或项目数据，保持内聚。
 */
export function useShellBlueprintEdit(options: {
  isAdmin: () => boolean
  novel: Ref<NovelProject | null>
  ensureProjectLoaded: () => Promise<void>
  updateBlueprintMutation: BlueprintMutation
  loadSection: (section: SectionKey, force?: boolean) => Promise<void>
}) {
  const { isAdmin, novel, ensureProjectLoaded, updateBlueprintMutation, loadSection } = options

  // Modal state (user mode only)
  const isModalOpen = ref(false)
  const modalTitle = ref('')
  const modalContent = ref<any>('')
  const modalField = ref('')

  const handleSectionEdit = (payload: { field: string; title: string; value: any }) => {
    if (isAdmin()) return
    modalField.value = payload.field
    modalTitle.value = payload.title
    modalContent.value = payload.value
    isModalOpen.value = true
  }

  const resolveSectionKey = (field: string): SectionKey => {
    if (field.startsWith('world_setting')) return 'world_setting'
    if (field.startsWith('characters')) return 'characters'
    if (field.startsWith('relationships')) return 'relationships'
    if (field.startsWith('chapter_outline')) return 'chapter_outline'
    return 'overview'
  }

  const handleSave = async (data: { field: string; content: any }) => {
    if (isAdmin()) return
    await ensureProjectLoaded()
    const project = novel.value
    if (!project) return

    const { field, content } = data
    const payload: Record<string, any> = {}

    if (field.includes('.')) {
      const [parentField, childField] = field.split('.')
      payload[parentField] = {
        ...(project.blueprint?.[parentField as keyof typeof project.blueprint] as
          | Record<string, any>
          | undefined),
        [childField]: content,
      }
    } else {
      payload[field] = content
    }

    try {
      await updateBlueprintMutation.mutateAsync(payload)
      const sectionToReload = resolveSectionKey(field)
      await loadSection(sectionToReload, true)
      if (sectionToReload !== 'overview') {
        await loadSection('overview', true)
      }
      isModalOpen.value = false
    } catch (error) {
      console.error('保存变更失败:', error)
    }
  }

  return {
    isModalOpen,
    modalTitle,
    modalContent,
    modalField,
    handleSectionEdit,
    handleSave,
  }
}
