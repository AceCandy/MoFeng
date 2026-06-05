# 章节草稿确认与同步定稿设计

## 背景

当前章节生成流程存在状态语义错位：生成结束后章节可能直接进入 `successful`，但真实章节梳理、全局记忆、向量入库、伏笔写入与回收等后处理并不一定已经完成。前端看到“已完成”时，右侧章节梳理可能仍显示“等待系统补齐章节梳理”，伏笔同步也可能没有跑完或没有可见节点记录。

项目尚未上线，本次不需要兼容旧历史逻辑，也不保留旧的“生成即完成”语义。实现应直接把最新章节链路更新为：生成只产出草稿，用户人工确认后同步执行定稿后处理，全部完成后才进入已完成状态。

## 目标

- 章节生成完成后只保存候选草稿，状态为 `waiting_for_confirm`。
- 用户可以查看草稿、选择候选版本、手动修改草稿。
- 用户点击确认后，前端等待同步定稿流程完成。
- 定稿流程完成前，章节不得显示为 `successful`。
- 定稿流程必须执行并可展示：
  - 选中/保存最终正文。
  - 生成并写入 `Chapter.real_summary`。
  - 更新项目记忆和章节快照。
  - 写入章节向量索引。
  - 同步伏笔新写入、推进和回收。
- 每个后处理节点都写入 `ChapterGenerationTrace`，前端可查看输入、动作、输出、错误。
- 失败要明确暴露，不允许 silent fallback 或 fake success。

## 非目标

- 不做旧数据迁移。
- 不保留旧接口的“生成完成即 successful”行为。
- 不引入独立 Draft 表或 FinalizeJob 表。
- 不做后台异步定稿队列；确认定稿必须同步等待。
- 不扩大到生产配置、密钥、计费、权限模型之外的改动。

## 状态模型

保留现有 `waiting_for_confirm` 作为草稿待确认状态，新增 `finalizing` 表示确认后的同步定稿处理中。

状态流转：

```text
not_generated
  -> generating
  -> evaluating / selecting
  -> waiting_for_confirm
  -> finalizing
  -> successful
```

失败流转：

```text
generating -> failed
evaluating -> evaluation_failed
finalizing -> waiting_for_confirm + finalization_error trace
```

定稿失败时章节保留草稿和候选版本，不进入 `successful`。错误通过 trace 和接口响应返回给前端，用户可修正文稿后再次确认定稿。

## 后端设计

### 生成只保存草稿

`PipelineOrchestrator._graph_persist_versions()` 不再向 `NovelService.replace_chapter_versions()` 传 `finalize_version_index`。`replace_chapter_versions()` 只负责替换本轮候选版本，把章节状态设为 `waiting_for_confirm`，不设置 `selected_version_id`，不写 `real_summary`，不跑后处理。

`persist_versions` trace 改名为 `save_draft` 或更新文案为“保存草稿”，输出候选版本 id、候选数量、推荐索引和字数指标。

### 确认定稿接口

新增或重构确认定稿接口，推荐路径：

```http
POST /api/writer/novels/{project_id}/chapters/{chapter_number}/confirm-finalize
```

请求体：

```json
{
  "selected_version_index": 0,
  "edited_content": "可选，用户手动修改后的最终正文",
  "skip_vector_update": false
}
```

响应体复用 `Chapter` 或返回包含章节与统计的结构：

```json
{
  "chapter": {
    "chapter_number": 1,
    "generation_status": "successful",
    "real_summary": "真实章节梳理",
    "content": "最终正文",
    "generation_traces": []
  },
  "finalize": {
    "summary_generated": true,
    "memory_updated": true,
    "vector_ingested": true,
    "foreshadowing_sync": {
      "created": 1,
      "developing": 0,
      "revealed": 2
    }
  }
}
```

接口执行顺序：

1. 校验项目归属、章节、候选版本和最终正文非空。
2. 设置章节状态为 `finalizing`，进度进入后处理区间。
3. 写入或更新最终 `ChapterVersion`，设置 `selected_version_id`。
4. 调用摘要模型生成 `Chapter.real_summary`，失败则定稿失败。
5. 调用 `FinalizeService.finalize_chapter()` 更新项目记忆和章节快照。
6. 调用 `ChapterIngestionService.ingest_chapter()` 写章节向量索引。
7. 调用 `_sync_foreshadowings_for_chapter()` 同步伏笔。
8. 全部成功后设置 `status = successful`、`generation_step = finalized`、`progress = 100`。
9. 返回最新章节数据和后处理统计。

### Trace 节点

确认定稿阶段新增 trace 节点：

| node_key | label | 类型 | 记录内容 |
| --- | --- | --- | --- |
| `confirm_finalize` | 确认定稿 | workflow | 选中版本、是否手动修改、最终字数 |
| `real_summary` | 生成章节梳理 | LLM | 摘要提示词、正文节选、原始返回、清洗结果 |
| `finalize_memory` | 更新记忆快照 | workflow/LLM | 全局摘要、角色状态、剧情线、快照结果 |
| `chapter_ingest` | 写入章节索引 | workflow/embedding | 标题、正文长度、summary、向量写入结果 |
| `foreshadowing_sync` | 同步伏笔 | workflow/LLM | 候选伏笔、历史活跃伏笔、created/developing/revealed |
| `finalized` | 定稿完成 | workflow | 最终状态、字数、后处理统计 |
| `finalization_error` | 定稿失败 | workflow | 失败节点、错误详情、回滚到草稿态 |

所有节点使用 `ChapterGenerationTraceService.record_success()` / `record_failure()`。LLM 节点必须写 `system_prompt`、`user_prompt`、`raw_response`、`cleaned_output`。非 LLM 节点必须写 `input_payload`、`output_payload`、`actions`、`data_reads`、`data_writes`。

## 前端设计

### 草稿确认页

`waiting_for_confirm` 进入草稿确认视图。现有 `VersionSelector` 可以继续承载，但文案需要改为“草稿确认”：

- 主按钮：`确认定稿`
- 次按钮：`编辑草稿`
- 保留：查看正文、候选对比、重新生成、继续润色。
- 用户编辑后不立即定稿，只更新本地编辑内容或保存为候选最终内容。

### 同步等待定稿

点击“确认定稿”后：

- 触发确认定稿接口。
- 前端切换到节点控制台。
- 状态展示为 `finalizing`。
- 控制台展示定稿后处理节点。
- 请求完成前不跳正文、不显示已完成。
- 请求成功后刷新章节并进入正文查看。
- 请求失败后保留草稿确认页，同时展示失败节点和错误详情。

### 节点详情

复用 `ChapterGenerating.vue` 的节点详情面板。该组件已经支持展示：

- 输入材料。
- 实际动作。
- 产出结果。
- LLM 调用状态。
- 系统耗时。

新增 `STEP_DETAILS` 与 label 映射即可覆盖定稿节点。`TRACE_CALL_TYPE_LABELS` 需要增加 `finalize_memory`、`foreshadowing_sync` 等后处理类型标签。

## API 给前端的契约

### 章节状态

`Chapter.generation_status` 新增：

```ts
type ChapterGenerationStatus =
  | 'not_generated'
  | 'generating'
  | 'evaluating'
  | 'selecting'
  | 'failed'
  | 'evaluation_failed'
  | 'waiting_for_confirm'
  | 'finalizing'
  | 'successful'
```

前端行为：

- `waiting_for_confirm`：显示草稿确认页。
- `finalizing`：显示节点控制台，禁用重新生成和编辑。
- `successful`：显示正文和章节梳理。

### 确认定稿请求

```ts
interface ConfirmFinalizeChapterRequest {
  selected_version_index: number
  edited_content?: string | null
  skip_vector_update?: boolean
}
```

### 确认定稿响应

```ts
interface ConfirmFinalizeChapterResponse {
  chapter: Chapter
  finalize: {
    summary_generated: boolean
    memory_updated: boolean
    vector_ingested: boolean
    foreshadowing_sync: {
      created: number
      developing: number
      revealed: number
    }
  }
}
```

## 错误处理

- 摘要生成失败：定稿失败，保留 `waiting_for_confirm`，trace 写 `real_summary` failed。
- 记忆更新失败：定稿失败，保留草稿态，trace 写 `finalize_memory` failed。
- 向量入库失败：定稿失败，除非用户显式传 `skip_vector_update=true`。
- 伏笔同步失败：定稿失败，保留草稿态，trace 写 `foreshadowing_sync` failed。
- 最终状态写入失败：返回 500，不显示成功。

不允许为了让章节显示完成而吞掉后处理错误。

## 测试策略

### 后端

- 生成流程测试：普通生成结束后状态为 `waiting_for_confirm`，没有 `selected_version_id`，没有 `real_summary`。
- 确认定稿成功测试：写入 selected version、real_summary、snapshot、ingest 调用、foreshadowing_sync，并最终 `successful`。
- 确认定稿失败测试：摘要/记忆/向量/伏笔任一失败时不进入 `successful`，保留草稿态并写失败 trace。
- Trace 测试：新增节点包含输入、动作、输出、LLM prompt/response。

### 前端

- `waiting_for_confirm` 显示草稿确认而非已完成。
- 点击确认后显示 `finalizing` 节点控制台并等待接口返回。
- 成功后显示正文和 `real_summary`。
- 失败后保留草稿确认，并能查看失败节点详情。

## 回滚方案

项目未上线，不保留旧行为回滚。代码层面的回滚方式是恢复本次提交。运行期如果确认定稿失败，章节保留草稿态，用户可修改后重试。

## 实施边界

本次实现只改写作台章节生命周期。不会修改登录、权限、生产配置、模型供应商配置、全局主题或其他页面结构。
