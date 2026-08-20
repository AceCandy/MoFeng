// AIMETA P=阶段路由数据测试|R=stage全集_正文映射_保存payload|NR=不测试网络请求|E=test:composable:useStageRoutes|X=internal|A=model-routing|D=vitest|S=test|RD=../README.ai
import { describe, expect, it } from 'vitest'

import { CHAPTER_WORKFLOW_STEPS } from '@/utils/generationTrace'
import { stageRouteKeys } from '@/components/llm-settings/stageDefinitions'
import { buildStageRoutePayload } from '@/components/llm-settings/useStageRoutes'

describe('stage route definitions', () => {
  it('覆盖后端已支持的二十二个唯一 stage', () => {
    expect(stageRouteKeys).toHaveLength(22)
    expect(new Set(stageRouteKeys).size).toBe(stageRouteKeys.length)
    expect(stageRouteKeys).toContain('rag_embedding')
    expect(stageRouteKeys).toContain('general_chat')
    expect(stageRouteKeys).not.toContain('chapter_writing')
  })

  it('固化正文节点的真实共用路由', () => {
    const routesFor = (stage: string) =>
      CHAPTER_WORKFLOW_STEPS.filter((step) => step.routeStage === stage).map((step) => step.key)

    expect(routesFor('chapter_writing_1')).toEqual(['generate_candidate_1'])
    expect(routesFor('chapter_writing_2')).toEqual(['generate_candidate_2'])
    expect(routesFor('chapter_optimization')).toEqual([
      'refine_candidate',
      'enhance_content',
      'repair_consistency',
      'optimize_style',
      'enrich_content',
      'compress_candidate',
    ])
    expect(routesFor('rag_embedding')).toEqual(['retrieve_context', 'project_rag'])
  })

  it('仅将已知且有选择的 stage 写入保存 payload', () => {
    expect(
      buildStageRoutePayload({
        chapter_writing_1: '2',
        chapter_writing_2: '3',
        general_chat: '5',
        rag_embedding: '4',
        chapter_mission: '',
        unknown_stage: '99',
      }),
    ).toEqual([
      { stage: 'chapter_writing_1', model_id: 2 },
      { stage: 'chapter_writing_2', model_id: 3 },
      { stage: 'rag_embedding', model_id: 4 },
      { stage: 'general_chat', model_id: 5 },
    ])
  })
})
