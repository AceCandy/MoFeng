# 技术设计：正文节点模型路由展示

## 1. 边界

本任务对齐前端展示与 stage-routes 配置，将候选正文路由拆成 `chapter_writing_1`、`chapter_writing_2`，并以 `general_chat` 承接未显式传入业务 stage 的通用调用。GET/PUT `/stage-routes` 的数据结构、数据库结构、默认模型回退和正文 workflow 拓扑不变。

## 2. 定义源

将 `ChapterGenerating.vue` 内的正文节点数组收口为共享静态定义。每个节点保留现有 `PipelineStep` 展示字段，并增加可选的路由元数据：

- `routeStage`：实际 stage key。
- `routeCapability`：`chat` 或 `embedding`。
- 无 `routeStage` 的节点按现有 `kind` 显示无模型调用。

`ChapterGenerating` 从共享定义创建自己的 `PipelineStep[]`；路由面板消费同一定义的分组、label、kind 和 route 映射。不将设置页的选择状态带入生成组件。

## 3. 路由数据

`useStageRoutes` 的 stage 全集由两部分去重合并：

1. 正文节点定义中的 `routeStage`，包含 `rag_embedding`。
2. 其他功能的现有 stage 定义。

`rag_query` 作为现有合同 stage 继续保留在其他功能中；由于当前没有 `stage="rag_query"` 的运行时模型调用，不把它伪装成 `retrieve_context` 的第二个模型。

`routeSelections` 仍以 stage key 为唯一键。因此共用 stage 的多个节点只是同一响应式值的多个视图，任一 select 改动后其余视图自动同步。保存 payload 每个 stage 最多一条，不会按节点重复提交。

候选版本 1、2 分别映射 `chapter_writing_1`、`chapter_writing_2`，不再共享选择。旧 `chapter_writing` 从前后端 stage 集合中直接移除，不做兼容回退或数据迁移；模型服务的默认 stage 改为 `general_chat`，设置页只在“其他功能”展示它。

## 4. 界面

`RoutingStagesPanel` 保留现有阶段路由 tab，内部分成：

- “正文工作流”：按生成页相同的上下文、候选、评审修订、草稿选择、正式定稿、摘要、记忆、RAG、伏笔、汇合分组展示。
- “其他功能”：保留未映射到正文 DAG 的 stage 配置。

模型节点显示 stage/共用标记、用途说明和 capability 匹配的 select。默认 option 直接包含当前回退模型与供应商；无默认模型时显示未配置。非模型节点只展示 kind 与“无模型调用”，不渲染禁用 select。

空状态从“必须有 chat 模型”改为按节点 capability 分别给出配置引导，避免用户只配置 embedding 时无法看到 RAG 节点。

## 5. 兼容与回滚

- 不修改 API schema、OpenAPI、ORM 或数据库。
- 后端 chat stage 以两个候选 stage 和 `general_chat` 替换 `chapter_writing`；候选调用按 ordinal 选择对应 stage。
- 功能尚未上线，不保留旧 `chapter_writing` 数据或运行时回退。
- 回滚只需回退前端共享定义、路由面板和相关测试。
- 主要风险是前后端 stage 集合或候选 ordinal 映射漂移；通过共享前端节点定义和前后端聚焦测试限制，不新增 API 类型。

## 6. 验证

- 聚焦 Vitest：共享定义、路由面板渲染/事件、`useStageRoutes` 同步与 payload。
- 聚焦 Pytest：stage capability 与候选 ordinal 到 stage 的映射。
- 前端 `npm run type-check`。
- 必要时运行与修改文件相关的现有 UI 回归测试；不默认运行后端或全量编译。
