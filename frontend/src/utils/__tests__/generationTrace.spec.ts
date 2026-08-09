// AIMETA P=章节生成轨迹节点映射测试|R=durable节点到现有进度条步骤映射|NR=不测试Vue响应式或轨迹详情|E=test:utils:generation-trace|X=internal|A=normalizePipelineStepKey|D=vitest|S=test|RD=../README.ai
import { describe, expect, it } from 'vitest'

import { normalizePipelineStepKey } from '@/utils/generationTrace'

describe('normalizePipelineStepKey', () => {
  it.each([
    ['freeze_context', 'context_prep'],
    ['plan_and_direct', 'director_mission'],
    ['generate_candidates', 'draft_generation'],
    ['review_candidates', 'quality_review'],
    ['persist_candidates', 'review_refinement'],
    ['waiting_for_selection', 'review_refinement'],
    ['finalize_revision', 'real_summary'],
    ['projection_pending', 'chapter_ingest'],
    ['observe_projection', 'foreshadowing_sync'],
    ['successful', 'finalized'],
  ])('maps durable workflow node %s to %s', (nodeKey, pipelineStep) => {
    expect(normalizePipelineStepKey(nodeKey)).toBe(pipelineStep)
  })
})
