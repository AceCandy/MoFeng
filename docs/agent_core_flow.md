# Agent 核心流程

本文整理 MoFeng（墨风）当前项目里的 AI Agent 核心执行链路。这里的 “Agent” 不是单独的 `Agent` 类，也不是 LangChain Agent；章节生成主路径由 LangGraph 状态图承载阶段编排，业务能力仍由 API 入口、提示词、上下文构建、模型阶段路由、生成/评审/定稿服务共同组成。

整理日期：2026-07-27

---

## 1. 核心结论

当前项目的 Agent 主线是：

```text
用户输入
  -> FastAPI 路由
  -> ChapterContextResolver 读取并冻结项目/蓝图/章节事实
  -> PromptService 读取提示词
  -> canonical ChapterContext：历史 + 可见性 + RAG/记忆 + provenance/hash
  -> LLMService 按 stage 解析用户模型路由
  -> 生成/评审/修复/优化
  -> 写入 ChapterVersion / ChapterEvaluation / ProjectMemory / 向量库
  -> 前端刷新项目状态
```

最核心的后端文件：

- `backend/app/api/routers/novels.py`：概念对话、蓝图生成。
- `backend/app/api/routers/writer.py`：章节生成入口、版本选择、评审、定稿入口；普通生成接口会委托 LangGraph 编排器。
- `backend/app/services/pipeline_orchestrator.py`：章节生成 LangGraph 状态图编排器。
- `backend/app/services/llm_service.py`：模型调用、流式输出、向量生成、阶段路由解析。
- `backend/app/services/prompt_service.py`：提示词缓存和读取。
- `backend/app/schemas/chapter_context.py`：版本化章节上下文、section provenance 与稳定快照/hash。
- `backend/app/services/chapter_context_resolver.py`：章节上下文唯一 DB/RAG 读取、预算和降级入口。
- `backend/app/services/chapter_context_adapters.py`：生成、评审和一致性检查的纯数据视图。
- `backend/app/services/writer_context_builder.py`：由 resolver 调用的写作可见性过滤策略。
- `backend/app/services/knowledge_retrieval_service.py`：两层 RAG 检索与过滤。
- `backend/app/services/ai_review_service.py`：多版本/单版本 AI 评审。
- `backend/app/services/finalize_service.py`：定稿后的摘要、角色状态、剧情线、快照、向量库闭环。

---

## 2. HTTP 入口

| 阶段 | 入口 | 主要用途 | 主要实现 |
| --- | --- | --- | --- |
| 概念对话 | `POST /api/novels/{project_id}/concept/converse` | 和概念设计师对话，收集创作设定 | `novels.py#converse_with_concept` |
| 流式概念对话 | `POST /api/novels/{project_id}/concept/converse/stream` | SSE 返回 `ai_message` 增量 | `novels.py#converse_with_concept_stream` |
| 蓝图生成 | `POST /api/novels/{project_id}/blueprint/generate` | 把概念对话整理为小说蓝图 | `novels.py#generate_blueprint` |
| 普通章节生成 | `POST /api/writer/novels/{project_id}/chapters/generate` | 前端当前主用路径，后端委托 `PipelineOrchestrator` 的 basic 配置 | `writer.py#generate_chapter` |
| 高级章节生成 | `POST /api/writer/advanced/generate` | 通过 `PipelineOrchestrator` 统一编排更多增强能力 | `writer.py#advanced_generate_chapter` |
| 版本选择 | `POST /api/writer/novels/{project_id}/chapters/select` | 选定候选版本并写入向量库 | `writer.py#select_chapter_version` |
| 章节评审 | `POST /api/writer/novels/{project_id}/chapters/evaluate` | 对候选版本或选中版本做 AI 评审 | `writer.py#evaluate_chapter` |
| 定稿 | `POST /api/writer/chapters/{chapter_number}/finalize` | 触发记忆、快照、向量库闭环 | `writer.py#finalize_chapter` |
| 单独优化 | `POST /api/optimizer/optimize` | 按维度优化章节正文 | `optimizer.py#optimize_chapter` |

前端当前绑定情况：

- `frontend/src/api/novel.ts#generateChapter` 调用普通章节生成接口；后端会进入 LangGraph 编排器。
- `frontend/src/api/novel.ts#evaluateChapter` 调用章节评审接口。
- `frontend/src/api/novel.ts#selectChapterVersion` 调用版本选择接口。
- `frontend/src/api/novel.ts#OptimizerAPI` 调用优化接口。
- 代码中暂未发现前端直接调用 `POST /api/writer/advanced/generate`，该入口主要用于显式传入增强配置。

---

## 3. 模型调用核心：LLMService

`LLMService` 是所有 Agent 能力的模型出口。

### 3.1 文本生成路径

```text
业务服务
  -> LLMService.get_llm_response(...)
  -> LLMService._stream_and_collect(...)
  -> LLMService._resolve_llm_config(...)
  -> LLMService._resolve_model_route(...)
  -> LLMClient.stream_chat(...)
  -> 收集完整响应
```

关键点：

- `get_llm_response` 默认 `stage="chapter_writing"`。
- `stream_llm_response` 用于概念对话 SSE，默认 `stage="concept_conversation"`。
- `_stream_and_collect` 统一处理超时、连接错误、权限拒绝、空响应、`finish_reason == "length"`。
- 每次成功调用会通过 `UsageService.increment("api_request_count")` 记录调用量。

### 3.2 阶段路由

模型路由由 `LLMConfigService` 定义阶段 key，再由 `LLMService` 运行时解析用户自己的供应商、模型和阶段绑定。

主要 chat 阶段：

```text
import_analysis
concept_conversation
world_blueprint
chapter_outline
chapter_blueprint
chapter_mission
chapter_preview
chapter_writing
chapter_rewrite
chapter_compression
chapter_enrichment
version_review
chapter_optimization
deep_review
emotion_analysis
consistency_check
summary_memory
rag_query
foreshadowing
```

向量阶段：

```text
rag_embedding
```

解析优先级：

```text
显式 model_id
  -> 用户阶段路由 UserAIStageRoute
  -> 用户启用模型里的默认 chat/embedding 模型
  -> 无可用模型则抛出 400
```

当前实现禁止回退到系统默认 LLM 配置。缺少 `user_id`、缺少用户级模型、缺少主模型或向量模型时，都会直接返回配置错误。

### 3.3 向量生成路径

```text
ChapterContextResolver / ChapterIngestionService
  -> LLMService.get_embedding(...)
  -> _resolve_model_route(stage="rag_embedding", capability="embedding")
  -> OpenAI 兼容 embeddings 或 Ollama embed
  -> VectorStoreService 查询/写入
```

向量模型也必须走用户模型配置。OpenAI 兼容服务支持有 Key 和无 Key 两种调用方式；Ollama 会优先使用 `/api/embed`，失败时回退旧接口 `/api/embeddings`。

---

## 4. 概念与蓝图 Agent 流程

### 4.1 概念对话

入口：`POST /api/novels/{project_id}/concept/converse`

执行步骤：

1. `NovelService.ensure_project_owner` 校验项目归属。
2. 读取历史概念对话，拼成 `conversation_history`。
3. 读取 `concept` 提示词，并追加 JSON 响应约束。
4. 调用 `LLMService.get_llm_response(stage="concept_conversation", temperature=0.8)`。
5. 清理 `<think>` 标签和 Markdown JSON 包裹。
6. 解析 JSON，写入用户消息和助手消息。
7. 如果 `is_complete=true`，设置 `ready_for_blueprint=true`。

流式版本使用同样上下文，但调用 `LLMService.stream_llm_response`，并用 `StreamingJSONFieldExtractor("ai_message")` 只把 `ai_message` 字段增量推给前端。

### 4.2 蓝图生成

入口：`POST /api/novels/{project_id}/blueprint/generate`

执行步骤：

1. 读取历史概念对话。
2. 从历史 JSON 中提取有效的 user/assistant 内容。
3. 读取 `screenwriting` 提示词。
4. 调用 `LLMService.get_llm_response(stage="world_blueprint", temperature=0.3)`。
5. 清理并解析蓝图 JSON。
6. 映射为项目蓝图数据，后续供章节生成使用。

---

## 5. 普通章节生成流程

入口：`POST /api/writer/novels/{project_id}/chapters/generate`

这是前端当前主用路径。`writer.py#generate_chapter` 只负责保持旧接口契约、传入 basic 配置并返回最新项目结构；真正的上下文收集、RAG、写作、评审和版本入库都由 `PipelineOrchestrator.generate_chapter` 的 LangGraph 节点执行。

```text
1. 初始化章节状态
2. 解析并冻结 canonical ChapterContext
3. L2 Director 生成 ChapterMission
4. resolver 通过 WriterContextBuilder 更新可见性 section
5. resolver 在同一快照上补充 RAG section
6. 拼接写作 Prompt
7. L3 Writer 生成 1-2 个候选版本
8. Guardrails 检查并尝试重写
9. 必要时补写到最低字数并压缩到目标字数
10. 多版本时 AIReviewService 评审选优
11. 写入 ChapterVersion
12. 返回最新 NovelProjectSchema
```

### 5.1 历史上下文

生成前由 `ChapterContextResolver` 遍历当前章节之前的 successful 且有选中正文的章节：

- 没有 `real_summary` 时使用确定性正文摘录，并在 history section 标记 `summary_missing`；上下文读取不触发 LLM 副作用。
- 收集 `completed_chapters`、`completed_summaries`。
- 记录最近前一章摘要和正文结尾 500 字，用于章节衔接。
- 按 policy 稳定排序和裁剪，并把 source revision、truncation、fallback 写入 section。

### 5.2 L2 Director：章节导演脚本

`_generate_chapter_mission` 使用 `chapter_plan` 提示词，把以下内容发给模型：

- 上一章摘要。
- 上一章结尾。
- 当前章节标题和摘要。
- 已登场角色。
- 全部角色。
- 用户写作指令。

输出是结构化 `ChapterMission`，后续用于：

- 指定本章允许新登场角色。
- 提供 POV、宏观节拍、冲突、情绪等写作约束。
- 给 Guardrails 做检查依据。

如果 `chapter_plan` 缺失或调用失败，流程会记录警告并退回默认模式继续生成。

### 5.3 信息可见性过滤

`ChapterContextResolver` 调用 `WriterContextBuilder.build_visibility_context` 生成 writer visibility section，这是防剧透的关键层：

- 从已完成摘要和上一章结尾检测已登场角色。
- 从当前章节标题、摘要、写作指令检测计划登场角色。
- 合并 Director 允许的新角色。
- 从蓝图中移除 `full_synopsis`、完整章节大纲、时间线等剧透字段。
- 裁剪角色和关系，只保留 Writer 当前可见角色。
- 输出 `forbidden_characters`，供 Guardrails 检查。

这层的目标是让 L3 Writer 只能看到“已经公开”或“本章允许公开”的信息。

### 5.4 RAG 检索

普通生成使用 `ChapterContextResolver.with_retrieval`：

```text
章节标题 + 章节摘要 + 写作指令
  -> LLMService.get_embedding(stage="rag_embedding")
  -> VectorStoreService.query_chunks
  -> VectorStoreService.query_summaries
  -> Markdown 片段 + 摘要列表
```

如果 RAG 关闭、向量库不可用、embedding 失败、检索为空或检索失败，section 会分别记录显式 fallback，不阻止章节生成。查询和结果会按 policy 裁剪，snapshot id 与内容共同参与 `input_hash`。

### 5.5 写作 Prompt 拼接

普通生成会拼接这些区块：

- `[世界蓝图](JSON，已裁剪)`
- `[上一章摘要]`
- `[上一章结尾]`
- `[章节导演脚本](JSON)`
- `[检索到的剧情上下文](Markdown)`
- `[检索到的章节摘要](Markdown)`
- `[当前章节目标]`
- `[篇幅与排版要求]`
- `[禁止角色](本章不允许提及)`

写作提示词优先使用 `writing_v2`，缺失时回退 `writing`。

### 5.6 生成、护栏与版本入库

单个版本生成时：

1. 调用 `LLMService.get_llm_response(stage="chapter_writing", temperature=0.9, response_format=None, max_tokens=7000)`。
2. 清理 `<think>` 和 Markdown JSON 包裹。
3. `ChapterGuardrails.check` 检查禁止角色、POV 等违规。
4. 若违规，读取 `rewrite_guardrails` 提示词并尝试自动重写。
5. 从模型 JSON 包裹中提取正文，避免把结构化包装写入正文。
6. 如果低于最低字数，调用补写提示词做最多三轮扩展。
7. 如果超出目标字数，调用压缩提示词做一次只删减不扩写的压缩。
8. 写入 `ChapterVersion`，并把 guardrail、word_limit、chapter_mission 等放进 metadata。

候选版本数来自：

```text
SystemConfig writer.chapter_versions
  -> SystemConfig writer.version_count
  -> ENV WRITER_CHAPTER_VERSION_COUNT / WRITER_CHAPTER_VERSIONS / WRITER_VERSION_COUNT
  -> settings.writer_chapter_versions
```

当前代码把候选版本数限制在 1 到 2。

### 5.7 AI 评审

当候选版本数大于 1 时：

- `AIReviewService.review_versions` 读取 `editor_review` 提示词。
- 调用 `LLMService.get_llm_response(stage="version_review", temperature=0.3)`。
- 解析多版本评分、优缺点、最佳版本索引、修改建议。
- 评审结果写进每个版本的 metadata。

单版本评审走 `AIReviewService.review_single_version`，读取 `evaluation` 提示词。

---

## 6. LangGraph 章节编排器

入口：

- `POST /api/writer/novels/{project_id}/chapters/generate`：前端主用入口，使用 basic 配置。
- `POST /api/writer/advanced/generate`：高级入口，可传入 `flow_config`。

核心服务：`PipelineOrchestrator.generate_chapter`

编排器通过 LangGraph `StateGraph` 显式串联各阶段节点，把上下文、增强能力、评审、后处理集中在服务层。普通生成入口会固定传入 `preset=basic` 和 `enable_rag=True`；高级入口请求体里的 `flow_config` 对应 `FlowConfig`：

```python
class FlowConfig(BaseModel):
    preset: str = "basic"          # basic|enhanced|ultimate|custom
    versions: Optional[int] = None
    enable_preview: Optional[bool] = None
    enable_optimizer: Optional[bool] = None
    enable_consistency: Optional[bool] = None
    enable_enrichment: Optional[bool] = None
    async_finalize: Optional[bool] = None
    enable_rag: Optional[bool] = None
    rag_mode: Optional[str] = None # simple|two_stage
```

### 6.1 preset 行为

| preset | 默认能力 |
| --- | --- |
| `basic` | 启用简单 RAG，普通章节生成。 |
| `enhanced` | 启用 constitution、persona、foreshadowing、faction，上下文使用 two_stage RAG，并启用六维评审。 |
| `ultimate` | 启用 enhanced 的上下文准备和记忆层，但当前代码会关闭 preview、optimizer、consistency、enrichment、six_dimension、reader_sim、self_critique。 |
| `custom` | 由请求里的开关决定。 |

### 6.2 高级编排流程

```text
PipelineOrchestrator.generate_chapter
  -> LangGraph ainvoke(initial_state)
  -> initialize_chapter：解析配置，校验项目和章节纲要，初始化章节生成状态
  -> collect_context：解析 canonical ChapterContext 并保存 snapshot/hash
  -> generate_chapter_mission：生成章节导演脚本
  -> build_visibility_context：在同一 snapshot 上写入导演脚本并重算可见性
  -> prepare_enhanced_context：从 snapshot 派生 constitution / persona / foreshadowing；faction 独立读取
  -> prepare_memory_context：从 snapshot 派生项目长期记忆，按配置读取其他记忆层
  -> prepare_retrieval_context：在同一 snapshot 上执行 simple RAG 或 two_stage RAG
  -> build_writer_prompt：读取写作提示词并拼装 prompt_sections
  -> generate_versions：生成版本，并执行护栏、JSON 提取、字数补写/压缩
  -> review_versions：多版本 AI 评审
  -> apply_post_generation_reviews：可选 self_critique / reader_sim / consistency / optimizer / enrichment
  -> persist_versions：replace_chapter_versions
  -> build_response：返回 variants + review_summaries + debug_metadata
```

### 6.3 RAG 模式差异

简单 RAG：

```text
ChapterContextResolver
  -> query_chunks
  -> query_summaries
  -> 直接拼入 Prompt
```

两层 RAG：

```text
KnowledgeRetrievalService.retrieve_and_filter
  -> 获取章节蓝图信息
  -> 生成检索关键词
  -> 向量检索
  -> LLM 过滤成 plot_fuel / character_info / world_fragments / narrative_techniques / warnings
  -> 按 POV 做可见性裁剪
  -> 拼入 Prompt
```

---

## 7. 定稿与长期记忆闭环

章节生成只产出候选版本。真正进入长期上下文，要经过版本选择或定稿。

### 7.1 版本选择

入口：`POST /api/writer/novels/{project_id}/chapters/select`

执行步骤：

1. 设置章节状态为 `selecting_version`。
2. 通过 `NovelService.select_chapter_version` 选中版本。
3. 校验正文非空。
4. 调用 `ChapterIngestionService.ingest_chapter` 写入向量库。
5. 后台触发 `_sync_foreshadowings_after_finalize`：
   - 规则抽取伏笔候选。
   - 调用 `LLMService.get_llm_response(stage="foreshadowing")` 精筛候选。
   - 对历史活跃伏笔做推进/回收判断。
6. 返回最新项目结构。

### 7.2 定稿服务

入口：`POST /api/writer/chapters/{chapter_number}/finalize`

`FinalizeService.finalize_chapter` 做生成后闭环：

```text
获取或创建 ProjectMemory
  -> 更新 global_summary
  -> 更新 CharacterState
  -> 更新 plot_arcs
  -> 写入向量库
  -> 创建 ChapterSnapshot
  -> 更新 ProjectMemory.last_updated_chapter/version
  -> 更新章节蓝图状态
```

这个闭环是长篇小说连续性的关键：下一章生成时，历史摘要、项目记忆、角色状态、剧情线和 RAG 都依赖这里沉淀的数据。

---

## 8. 提示词体系

提示词源：

- 初始文件：`backend/prompts/*.md`
- 运行时读取：`PromptService.get_prompt(name)`
- 启动预热：`backend/app/main.py` 的 lifespan 调用 `PromptService.preload()`
- 管理能力：后台 Prompt CRUD 会更新数据库和进程缓存。

核心提示词 ID：

| 提示词 ID | 用途 |
| --- | --- |
| `concept` | 概念对话设计师 |
| `screenwriting` | 蓝图生成 |
| `chapter_plan` | L2 Director / ChapterMission |
| `writing_v2` / `writing` | L3 Writer 章节正文 |
| `rewrite_guardrails` | 护栏失败后的自动重写 |
| `editor_review` | 多版本评审 |
| `evaluation` | 单版本章节评审 |
| `extraction` | 章节摘要提取 |
| `optimize_dialogue` | 对话优化 |
| `optimize_environment` | 环境描写优化 |
| `optimize_psychology` | 心理描写优化 |
| `optimize_rhythm` | 节奏优化 |
| `foreshadowing_reminder` | 伏笔相关增强提示 |

---

## 9. 数据写入点

| 数据 | 写入位置 | 触发时机 |
| --- | --- | --- |
| 概念对话 | `NovelConversation` | 概念对话完成后 |
| 蓝图 | Novel 项目相关蓝图表/字段 | 蓝图生成或保存 |
| 章节候选版本 | `ChapterVersion` | 普通/高级生成完成 |
| 章节评审 | `ChapterEvaluation` | 手动触发评审 |
| 选中版本 | `Chapter.selected_version_id` | 用户选择版本 |
| 真实摘要 | `Chapter.real_summary` | 历史摘要补齐、版本选择、编辑、定稿 |
| 向量 chunk/summary | `rag_chunks` / `rag_summaries` | 选择版本、编辑、定稿、导入 |
| 长期记忆 | `ProjectMemory` | 定稿 |
| 章节快照 | `ChapterSnapshot` | 定稿 |
| 角色状态 | `CharacterState` | 定稿 |
| 伏笔 | `Foreshadowing` | 版本选择或定稿后后台同步 |

---

## 10. 当前实现注意点

1. `PipelineOrchestrator.generate_chapter` 当前通过 LangGraph 状态图执行章节生成主路径；生成、AI 评审和一致性检查都从同一个 `ChapterContext` snapshot 经纯 adapter 派生，不再维护 `_build_review_context`。

2. 前端当前章节生成入口仍是普通路径 `POST /api/writer/novels/{project_id}/chapters/generate`，但该接口已经委托到 `PipelineOrchestrator`。

3. DB/RAG 上下文读取、可见性、预算和降级集中在 `ChapterContextResolver`；`PipelineOrchestrator` 只编排 snapshot 演进与下游 adapter。恢复优先复用合法快照，旧或损坏快照会显式重建。

4. `LLMService` 已禁止系统默认模型回退。任何 Agent 能力在用户未配置可用 LLM 模型或向量模型时，都会返回 400 配置错误。

---

## 11. 改动 Agent 流程时的建议落点

- 改模型选择/阶段路由：优先看 `llm_config_service.py` 和 `llm_service.py`。
- 改章节生成 Prompt 输入结构：优先看 `pipeline_orchestrator.py#_build_prompt_sections`。
- 改章节上下文 contract/快照：看 `chapter_context.py`。
- 改上下文读取、预算、降级或防剧透接入：看 `chapter_context_resolver.py`；具体可见性规则看 `writer_context_builder.py`。
- 改 RAG：统一入口看 `chapter_context_resolver.py`，两层检索内部看 `knowledge_retrieval_service.py`。
- 改生成/评审/一致性输入映射：看 `chapter_context_adapters.py`。
- 改评审和选优：看 `ai_review_service.py`。
- 改定稿后的长期记忆：看 `finalize_service.py`。
- 改伏笔抽取/推进：看 `writer.py` 中 `_sync_foreshadowings_for_chapter` 相关函数。
