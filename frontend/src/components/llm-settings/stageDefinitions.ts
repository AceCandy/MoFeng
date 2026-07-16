import type { StageGroup } from './modelRoutingTypes'

/**
 * 创作阶段静态定义。从 PersonalModelRouting.vue 抽出（Slice 1，纯数据零依赖）。
 * 每个阶段对应一个可独立指定模型的创作环节，用于阶段路由分区（routes）的模型选择网格。
 * 当前所有阶段 capability 均为 chat。
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
        key: 'chapter_writing',
        label: '正文生成',
        capability: 'chat',
        description: '章节正文主生成',
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
        key: 'foreshadowing',
        label: '伏笔处理',
        capability: 'chat',
        description: '伏笔候选、状态判断和提醒',
      },
    ],
  },
]
