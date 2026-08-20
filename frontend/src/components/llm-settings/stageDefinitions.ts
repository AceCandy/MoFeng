// AIMETA P=模型路由阶段定义|R=stage分组_能力_正文节点外阶段|NR=不持有路由选择|E=data:stageDefinitions|X=internal|A=model-routing|D=typescript|S=pure|RD=./README.ai
import { CHAPTER_WORKFLOW_STEPS } from '@/utils/generationTrace'
import type { StageGroup } from './modelRoutingTypes'

/**
 * 创作阶段静态定义。从 PersonalModelRouting.vue 抽出（Slice 1，纯数据零依赖）。
 * 每个阶段对应一个可独立指定模型的创作环节，用于阶段路由分区（routes）的模型选择网格。
 * capability 决定路由可选模型；正文节点展示另复用真实 workflow 定义。
 */
export const stageGroups: StageGroup[] = [
  {
    title: '导入与灵感',
    stages: [
      {
        key: 'import_analysis',
        label: '导入分析',
        capability: 'chat',
        description: '导入小说角色筛选与结构分析',
      },
      {
        key: 'concept_conversation',
        label: '灵感对话',
        capability: 'chat',
        description: '灵感模式多轮概念对话',
      },
      {
        key: 'world_blueprint',
        label: '完整蓝图',
        capability: 'chat',
        description: '由灵感历史生成整本书蓝图',
      },
    ],
  },
  {
    title: '规划',
    stages: [
      {
        key: 'chapter_outline',
        label: '章节大纲',
        capability: 'chat',
        description: '续写章节大纲',
      },
      {
        key: 'chapter_blueprint',
        label: '章节蓝图',
        capability: 'chat',
        description: '单章或批量章节蓝图',
      },
      {
        key: 'chapter_mission',
        label: '导演脚本',
        capability: 'chat',
        description: '章节写作前的执行脚本',
      },
    ],
  },
  {
    title: '写作',
    stages: [
      {
        key: 'chapter_preview',
        label: '章节预览',
        capability: 'chat',
        description: '预览、评估与扩写',
      },
      {
        key: 'chapter_writing_1',
        label: '候选版本 1',
        capability: 'chat',
        description: '生成第一份候选正文',
      },
      {
        key: 'chapter_writing_2',
        label: '候选版本 2',
        capability: 'chat',
        description: '生成第二份候选正文',
      },
      {
        key: 'chapter_rewrite',
        label: '护栏重写',
        capability: 'chat',
        description: '一致性和护栏自动修复',
      },
      {
        key: 'chapter_compression',
        label: '字数压缩',
        capability: 'chat',
        description: '超长章节压缩',
      },
      {
        key: 'chapter_enrichment',
        label: '章节润色',
        capability: 'chat',
        description: '对话、场景和章节增强',
      },
    ],
  },
  {
    title: '复盘与优化',
    stages: [
      {
        key: 'version_review',
        label: '版本评审',
        capability: 'chat',
        description: '多版本评审和单版本评价',
      },
      {
        key: 'chapter_optimization',
        label: '章节优化',
        capability: 'chat',
        description: '节奏、心理、环境、对白优化',
      },
      {
        key: 'deep_review',
        label: '深度审稿',
        capability: 'chat',
        description: '六维复盘、读者模拟、自我批评',
      },
      {
        key: 'emotion_analysis',
        label: '情绪曲线',
        capability: 'chat',
        description: '章节情绪曲线分析',
      },
      {
        key: 'consistency_check',
        label: '一致性检查',
        capability: 'chat',
        description: '只诊断问题，不改正文',
      },
    ],
  },
  {
    title: '记忆与 RAG',
    stages: [
      {
        key: 'summary_memory',
        label: '摘要记忆',
        capability: 'chat',
        description: '章节摘要、全局摘要、角色状态',
      },
      {
        key: 'rag_query',
        label: '检索规划',
        capability: 'chat',
        description: '检索查询生成和上下文过滤',
      },
      {
        key: 'rag_embedding',
        label: '向量检索',
        capability: 'embedding',
        description: '章节检索与索引的向量生成',
      },
      {
        key: 'foreshadowing',
        label: '伏笔处理',
        capability: 'chat',
        description: '伏笔候选、状态判断和提醒',
      },
    ],
  },
  {
    title: '通用',
    stages: [
      {
        key: 'general_chat',
        label: '通用模型调用',
        capability: 'chat',
        description: '未明确指定业务阶段的模型调用',
      },
    ],
  },
]

export const stageRouteKeys = [
  ...new Set(stageGroups.flatMap((group) => group.stages.map((stage) => stage.key))),
]

export const stageDefinitionByKey = Object.fromEntries(
  stageGroups.flatMap((group) => group.stages.map((stage) => [stage.key, stage])),
)

const workflowRouteStages = new Set(
  CHAPTER_WORKFLOW_STEPS.flatMap((step) => (step.routeStage ? [step.routeStage] : [])),
)

export const otherStageGroups = stageGroups
  .map((group) => ({
    ...group,
    stages: group.stages.filter((stage) => !workflowRouteStages.has(stage.key)),
  }))
  .filter((group) => group.stages.length > 0)
