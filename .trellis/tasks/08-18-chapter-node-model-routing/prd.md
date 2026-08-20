# 统一正文节点模型路由展示

## Goal

让用户在“阶段路由”设置中按正文生成页面的真实工作流节点查看当前有效模型，并清楚区分独立路由、共用路由和无模型节点，避免现有“业务阶段列表”与真实正文 DAG 不一致造成误解。

## Background / Confirmed Facts

- 正文生成页在 `frontend/src/components/writing-desk/workspace/ChapterGenerating.vue:114-146` 展示 30 个真实 DAG 节点，包括模型、本地事务、人工等待、汇合与终态节点。
- 阶段路由页的 `stageDefinitions.ts:8-145` 只列出 19 个 chat stage，不是正文节点清单，且漏掉后端已支持的 `rag_embedding`。
- 后端路由合同调整为 21 个 chat stage 与 `rag_embedding` 的并集；未显式覆盖时，chat 回退主模型，embedding 回退当前检索模型（`backend/app/services/llm_service.py:988-1025`）。
- `rag_query` 虽保留在 chat stage 合同中，但当前项目没有以 `stage="rag_query"` 发起模型调用的运行时调用点；正文 `retrieve_context` 对应的实际模型调用是 `rag_embedding`。
- 当前正文工作流的实际路由映射为：
  - `plan_chapter` → `chapter_mission`。
  - `generate_candidate_1` → `chapter_writing_1`，`generate_candidate_2` → `chapter_writing_2`，两个候选可独立选模。
  - 未显式传入业务 stage 的通用模型调用 → `general_chat`；该 stage 不属于正文 DAG。
  - `review_candidates` → `version_review`；单候选时不调用模型。
  - `refine_candidate`、`enhance_content`、`repair_consistency`、`optimize_style`、`enrich_content`、`compress_candidate` → 当前共用 `chapter_optimization`。
  - `generate_summary` 及四个 memory 节点 → 共用 `summary_memory`。
  - `retrieve_context`、`project_rag` 中的向量调用 → 共用 `rag_embedding`。
  - 两个 foreshadowing 节点 → 共用 `foreshadowing`。
  - 其余本地事务、等待、汇合和终态节点不配置模型。
- 旧任务 `.trellis/tasks/archive/2026-08/08-14-split-chapter-workflow-nodes/` 已确立：真实 DAG 是节点展示事实源，系统/控制节点可展示但不能伪装成模型调用。

## Requirements

### R1. 正文工作流展示

阶段路由页增加“正文工作流”区域，按 `ChapterGenerating` 现有节点顺序、分组和并行语义展示。模型节点显示路由选择和当前有效模型；系统、控制与终态节点明确显示“无模型调用”。

### R2. 独立候选与共用 stage 语义

候选版本 1、2 必须分别编辑 `chapter_writing_1`、`chapter_writing_2`，可选择不同模型。其他映射到同一 stage 的节点仍标记“共用路由”；在任一节点修改时，所有共用节点立即反映同一选择。

### R3. Chat 与 Embedding 覆盖

路由编辑根据 stage capability 仅提供匹配模型：chat 节点使用已启用 chat 模型，`rag_embedding` 使用已启用 embedding 模型。无显式覆盖时，界面必须显示具体的主模型/当前检索模型，不只显示抽象的“使用主模型”。

### R4. 其他功能阶段

导入、灵感、蓝图、独立审稿等不属于正文 DAG 的现有 stage 保留在“其他功能”区域，不删除、不更名、不改变路由保存语义。

### R5. 单一定义源

正文节点的 key、label、分组、kind 与 route stage 映射必须收口到一份可被生成页和设置页共用的前端静态定义，禁止两个组件继续各自维护节点清单。

### R6. 保存与兼容

继续使用现有 stage-routes GET/PUT 数据结构。`chapter_writing` 由两个候选 stage 与 `general_chat` 替换，不保留历史兼容；保存时必须包含所有已配置的 chat/embedding stage。

## Acceptance Criteria

- [x] AC1：阶段路由页按正文生成页相同的节点顺序与分组展示完整正文 DAG，无模型节点有明确说明。
- [x] AC2：候选版本 1、2 可独立选择不同模型；修订链、记忆链、RAG 与伏笔节点继续正确显示和同步共用 stage。
- [x] AC3：`rag_embedding` 可选择 embedding 模型，不出现 chat 模型；其他模型节点仅显示 chat 模型。
- [x] AC4：未显式配置路由时，每个模型节点显示当前会回退到的具体模型与供应商；缺少对应默认模型时显示明确未配置状态。
- [x] AC5：其他功能阶段仍可配置，`general_chat` 明确标注为通用调用；21 个 chat stage 与 `rag_embedding` 可完整读取、编辑和保存，不改变 API 或数据库结构。
- [x] AC6：正文生成页与阶段路由页消费同一份节点定义，聚焦单元测试覆盖分组、capability 过滤、默认模型文案、共用 stage 同步与保存 payload。
- [x] AC7：路由面板保持键盘可操作、有效 aria-label，并在窄屏下无水平溢出。

## Out of Scope

- 不拆分候选版本之外的共用 stage。
- 不改变正文工作流拓扑、提示词、模型参数、重试或生成算法。
- 不让设置页展示历史某次运行实际使用的模型；本页表达的是当前路由配置及其默认回退。
- 不删除当前正文工作流未使用、但被其他业务功能使用的 stage。

## Key Decisions / Risks

- 用户已确认采用“正文节点镜像展示 + 底层继续使用 stage 路由 + 其他功能单独保留”方案。
- 直接复制两份节点数组会继续漂移，因此需先将现有正文节点静态定义抽到共享模块；不新增 API 或通用抽象。
- 设置页的“当前有效模型”会随保存后配置变化，不是历史运行审计信息。
