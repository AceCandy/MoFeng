# 修复润色后重复选版：技术设计

## Boundary

修复放在 `NovelService` 构造 `Chapter.version_selections` 的公开投影边界。持久化层继续保存全部版本，前端仍消费既有 `ChapterVersionSelection` 合同。

## Data Flow

1. AI 评审为每个版本写入 `metadata.ai_review.is_best`，并只润色优选版本。
2. 保存节点继续将全部版本写入 `chapter_versions`。
3. 查询章节详情时：
   - 章节为 `waiting_for_confirm`；
   - 当前加载版本中恰有一个 `is_best=true`；
   - 则 `version_selections` 只投影该版本。
4. 没有唯一优选标记时返回原有完整集合，兼容旧数据和其他生成入口。
5. `versions` 历史正文集合维持现状，不随待确认投影收敛。

## Contract Decision

不新增 `recommended` 字段，也不修改 OpenAPI。现有候选集合本身就是人工可选集合，后端负责保证其中只包含当前流程允许确认的结果。这样避免前端依赖内部 metadata，也避免刷新、不同客户端或其他消费者各自实现筛选。

## Compatibility And Rollback

- 无数据库迁移，回滚只需恢复投影筛选与前端文案。
- 旧数据缺少标记时自动保持原行为，不阻断确认。
- 若数据异常地出现零个或多个优选标记，也保持全量候选，避免静默选错版本。

## Risks

- `version_selections` 可能存在非写作桌消费者；筛选只在 `waiting_for_confirm` 状态生效，且 `versions` 历史集合不变，以限制行为范围。
- 必须测试优选版本并非数组首项的情况，防止误用顺序作为推荐依据。
