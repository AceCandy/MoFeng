// AIMETA P=章节生成轨迹节点映射测试|R=durable节点到现有进度条步骤映射|NR=不测试Vue响应式或轨迹详情|E=test:utils:generation-trace|X=internal|A=normalizePipelineStepKey|D=vitest|S=test|RD=../README.ai
import { describe, expect, it } from 'vitest'

import {
  normalizePipelineStepKey,
  resolvePipelineStepKey,
  STEP_DETAILS,
  type PipelineStep,
} from '@/utils/generationTrace'

describe('normalizePipelineStepKey', () => {
  it('preserves canonical workflow node keys', () => {
    expect(normalizePipelineStepKey('review_candidates')).toBe('review_candidates')
    expect(normalizePipelineStepKey('finalize_revision')).toBe('finalize_revision')
  })
})

describe('resolvePipelineStepKey', () => {
  const steps: PipelineStep[] = [
    { key: 'review_candidates', label: '评审候选版本' },
    { key: 'finalize_revision', label: '定稿章节版本' },
    { key: 'generate_summary', label: '生成章节梳理' },
    { key: 'project_memory', label: '更新记忆快照' },
  ]

  it('保留真实节点键', () => {
    expect(resolvePipelineStepKey('review_candidates', steps)).toBe('review_candidates')
    expect(resolvePipelineStepKey('finalize_revision', steps)).toBe('finalize_revision')
  })

  it('拒绝非当前流程节点', () => {
    expect(resolvePipelineStepKey('real_summary', steps)).toBe('')
    expect(resolvePipelineStepKey('freeze_context', steps)).toBe('')
  })
})

describe('candidate step details', () => {
  it('描述并行生成和评审前汇合', () => {
    expect(STEP_DETAILS.plan_chapter?.next).toBe('并行生成候选版本')
    expect(STEP_DETAILS.generate_candidate_1?.next).toBe('等待候选汇合后进入评审')
    expect(STEP_DETAILS.generate_candidate_2?.next).toBe('等待候选汇合后进入评审')
  })
})
