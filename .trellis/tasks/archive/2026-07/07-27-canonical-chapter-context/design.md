# Canonical Chapter Context Design

## Boundaries

建议模块边界：

```text
ChapterContextResolver (I/O + policy)
  +--> repositories / blueprint visibility / RAG adapter
  +--> ChapterContext (versioned serializable contract)

ChapterContext
  +--> GenerationContextAdapter (pure)
  +--> ReviewContextAdapter (pure)
  +--> ConsistencyContextAdapter (pure)
```

resolver 是唯一允许读取 Chapter 上下文依赖的入口。adapter 是纯函数，只选择、格式化和预算已有字段，不补查数据。

## Contract Shape

contract 使用显式 section wrapper，而不是裸 dict：

```text
ContextSection[T]
  value: T
  source: enum
  source_revision: string | int | null
  truncated: bool
  fallback: enum | null
```

顶层记录 `schema_version`、`policy_version`、`created_at`、`source_revision` 与 `input_hash`。`created_at` 不参与确定性 hash。

RAG results 必须先归一化和稳定排序，再进入 snapshot。snapshot 不保存 SQLAlchemy model、service、session 或 lazy relationship。

## Source Revision

`source_revision` 只由 canonical 数据版本组成，至少覆盖 blueprint、目标 chapter outline 和前序 successful Chapter revision。它不包含会在 finalize 后变化的 projection checkpoint，避免 context 与 projection 互相定义。

memory/RAG 等派生来源在各自 section provenance 中记录 `projection_revision` 或显式 `missing/unknown` sentinel；section 的归一化内容和 retrieval snapshot id 参与 `input_hash`。`source_revision_schema_version` 固定组合规则，后续切换显式 Chapter revision 时提升版本，禁止让“无 checkpoint”静默等同普通 revision。

## Policy

- writer visibility 在 blueprint 进入 contract 前执行。
- budget 以 section 优先级和确定性截断执行；不能按数据库未排序结果截断。
- 缺少可选数据使用空 typed value + fallback reason。
- RAG unavailable 与 RAG empty 必须区分。
- prompt adapters 不能重新决定数据来源，只能决定呈现。

## Migration

1. 新 resolver 与独立纯映射的旧视图在测试和 shadow 模式中生成可比较输出。
2. 用结构化 diff 对比共享字段并为有意差异建立映射。
3. pipeline/writer 通过旧视图 shadow 对比，consistency/generation 通过共享 section contract 与 wiring tests 后，在一个原子变更中切到 canonical context。
4. 同一变更删除私有旧 DB builder，保留不执行 I/O 的 compatibility mapping 与 contract tests，避免形成双读取事实源。

## Risks

- 统一后 prompt token 体积上涨：section budget 与 adapter selection 控制。
- RAG 查询具有时间变化：durable run 冻结 snapshot；新 run 才刷新。
- blueprint visibility 回归：以禁止角色 fixture 做负向测试。
- ORM lazy load 导致 async 错误：resolver repository 显式 eager load，contract 构造后与 session 脱离。
