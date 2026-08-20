// AIMETA P=阶段路由状态|R=路由同步_去重保存_脏状态|NR=不渲染路由界面|E=composable:useStageRoutes|X=internal|A=model-routing|D=vue-query|S=state|RD=./README.ai
import { computed, reactive, ref, watch, type Ref } from 'vue'
import type { useLLMConfigBundleQuery, useSaveStageRoutesMutation } from '@/queries/llm'
import type { ProviderFormMode } from './modelRoutingTypes'
import { stageRouteKeys } from './stageDefinitions'

export const buildStageRoutePayload = (routeSelections: Record<string, string>) =>
  stageRouteKeys.flatMap((stage) => {
    const modelId = routeSelections[stage]
    return modelId ? [{ stage, model_id: Number(modelId) }] : []
  })

interface UseStageRoutesOptions {
  bundleQuery: ReturnType<typeof useLLMConfigBundleQuery>
  saveStageRoutesMutation: ReturnType<typeof useSaveStageRoutesMutation>
  /** 供应商表单模式（null 表示未打开），isDirty 据此判断表单脏状态 */
  providerFormMode: Ref<ProviderFormMode | null>
  setFeedback: (type: 'success' | 'error', message: string) => void
  /** 阶段路由保存成功后的回调（主组件用于 emit('saved')，延迟绑定规避 const TDZ） */
  onSaved: () => void
}

/**
 * 阶段路由状态机。从 PersonalModelRouting.vue 抽出（Slice 5）。
 * 内化 routeSelections/initialRouteSelections + allStageKeys +
 * syncRouteSelectionsFromBundle/saveRoutes + isDirty（含 providerFormMode 与 routes 两分支）+
 * watch(bundleQuery.data→sync, immediate)。saveRoutes 的 emit('saved') 经 onSaved 回调交父。
 */
export const useStageRoutes = (options: UseStageRoutesOptions) => {
  const { bundleQuery, saveStageRoutesMutation, providerFormMode, setFeedback, onSaved } = options

  const routeSelections = reactive<Record<string, string>>({})
  const initialRouteSelections = ref<Record<string, string>>({})
  const allStageKeys = computed(() => stageRouteKeys)

  const syncRouteSelectionsFromBundle = () => {
    const bundle = bundleQuery.data.value
    for (const key of allStageKeys.value) {
      routeSelections[key] = ''
    }
    for (const route of bundle?.stage_routes ?? []) {
      if (allStageKeys.value.includes(route.stage)) {
        routeSelections[route.stage] = String(route.model_id)
      }
    }
    // 备份一份初始状态，以便判断脏数据
    initialRouteSelections.value = { ...routeSelections }
  }

  const saveRoutes = async () => {
    const routes = buildStageRoutePayload(routeSelections)

    try {
      const savedRoutes = await saveStageRoutesMutation.mutateAsync({ routes })
      for (const key of allStageKeys.value) {
        routeSelections[key] = ''
      }
      for (const route of savedRoutes) {
        if (allStageKeys.value.includes(route.stage)) {
          routeSelections[route.stage] = String(route.model_id)
        }
      }
      // 保存成功，重置脏数据状态
      initialRouteSelections.value = { ...routeSelections }
      setFeedback('success', '阶段路由已保存。')
      onSaved()
    } catch (error) {
      const message = error instanceof Error ? error.message : '未知错误'
      setFeedback('error', `阶段路由保存失败：${message}`)
    }
  }

  const isDirty = computed(() => {
    // 1. 如果正在编辑或创建供应商表单，则有未保存修改
    if (providerFormMode.value !== null) {
      return true
    }

    // 2. 检查阶段路由是否有未保存修改
    for (const key of allStageKeys.value) {
      const currentVal = routeSelections[key] || ''
      const initialVal = initialRouteSelections.value[key] || ''
      if (currentVal !== initialVal) {
        return true
      }
    }

    return false
  })

  watch(
    () => bundleQuery.data.value,
    () => {
      syncRouteSelectionsFromBundle()
    },
    { immediate: true },
  )

  return {
    routeSelections,
    allStageKeys,
    syncRouteSelectionsFromBundle,
    saveRoutes,
    isDirty,
  }
}
