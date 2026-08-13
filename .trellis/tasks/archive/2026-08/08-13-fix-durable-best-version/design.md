# 修复主工作流优选版本投影：技术设计

## Root Cause

问题属于跨层合同与测试覆盖缺口：durable workflow 的优选事实停留在私有 review activity 中，公开候选行没有携带该事实；读侧却依赖兼容流水线使用的 `metadata.ai_review.is_best`。

## Data Flow

1. `_load_inputs` 已验证 review activity 绑定当前候选集合，且 `best_ordinal` 属于候选 ordinals。
2. `_write_candidates` 为每个 draft 写入 `metadata.ai_review.is_best = (draft.ordinal == review.best_ordinal)`；无 review 时不制造标记。
3. 该 metadata、候选正文、evaluation 和 workflow 状态共享现有 transactional outcome writer。
4. `NovelService` 继续按唯一严格布尔标记收敛 `version_selections`，完整 `versions` 不变。

## Test Boundary

扩展现有 `test_persist_candidates_is_atomic_private_and_replayable`：该测试已经创建真实 candidate/review/post-review activities 并执行 durable persistence。持久化后用实际加载的 Chapter/Outline 调用 `NovelService._build_chapter_schema_from_entities`，同时验证存储标记和公开投影。

## Legacy Pipeline Decision

`PipelineOrchestrator` 暂不删除。当前仍有以下生产依赖：

- `chapter_generation_task_runner` 直接调用；
- worker registry 注册 `chapter_generation` v1；
- writer 旧端点在 durable start 开关关闭、无活动 run 或旧恢复场景下回退；
- 历史 `from_node_key`、generation trace 和 context snapshot 恢复。

删除需要独立退役计划：强制新流量进入 durable workflow、处理存量 queued/running job、替换旧恢复语义、移除兼容回退和前端旧入口，最后再删除 orchestrator。

## Rollback

无 schema migration。回滚 metadata 写入和对应测试即可；旧数据兼容行为不变。
