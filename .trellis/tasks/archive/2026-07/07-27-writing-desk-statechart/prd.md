# 重构 WritingDesk 为 Statechart

## Goal

把 WritingDesk 从“多个 composable、ref、watcher 和 Chapter 乐观状态共同猜测生命周期”切换为一个可恢复的章节工作流交互模型：服务端 workflow snapshot 是生命周期事实，Vue Query 是唯一 server cache，XState 只管理命令、关联身份和 transport 交互。

用户获得的结果是：刷新、切章、断线重连、重复点击、评审失败、人工选版、定稿和 projection pending 都能恢复到同一服务端事实，不再需要手动刷新，也不会由两套前端状态源重复提交副作用。

## Confirmed Facts

- `WritingDesk.vue:193-219` 同时持有 project/chapter query 与 `chapterGenerationResult`、`generatingChapter` 等本地状态；后两者复制或推断服务端生命周期。
- `useWritingDeskChapterGeneration.ts:84-200`、`useWritingDeskChapterOps.ts:32-85`、`useWritingDeskConfirm.ts:59-89` 会在本地写入 `generation_status` 或维护 lifecycle ref，并在 mutation 后重复 refresh/refetch。
- `useWritingDeskProject.ts:44-147` 自行拥有章节 SSE、AbortController、stream key、timer 和 cache upsert；`WDWorkspace.vue:347-377` 再通过 status/content watcher 推断是否应启动连接。
- durable Chapter workflow 已提供 start、run snapshot 和 command API，但 WritingDesk 路由只有 `project_id + chapter_number`，Chapter DTO 不含 active `run_id`；刷新后无法定位 waiting、projection pending 或 failed run。
- `ChapterWorkflowRun` 的 active 唯一约束包含 `base_revision`，因此同一章节的不同 revision 可能同时存在 active run；现有 repository 没有跨 revision 的 current lookup。
- generated transport 已覆盖现有 workflow DTO，但前端没有 workflow API/query adapter、snapshot runtime decoder、`events_url` 消费或按 run scope 的 statechart actor。
- backend `CHAPTER_WORKFLOW_START_ENABLED` 默认关闭，deploy 配置尚未显式传入；前端也没有可复用的 feature-flag/telemetry shadow 基础设施。
- 前端使用 npm、Vitest/jsdom 和现有 bundle budget；当前没有 XState、`@xstate/vue`、Playwright 或 WritingDesk 端到端浏览器测试。

## Requirements

### R1 - Recoverable Current Workflow Lookup

- 增加 owner-scoped 的只读 current lookup，以 `project_id + chapter_number` 返回可连接的 workflow snapshot 与 `events_url`；没有可见 run 时返回 `null`，不得通过 start API 探测。
- 选择规则必须确定且可测试：active run 优先；多个 active run 时按 `base_revision`、`updated_at`、`created_at`、`id` 降序；无 active 时返回最近的 `successful`、`failed` 或 `cancelled` terminal run。
- terminal fallback 必须排除 `superseded` 和 `successor_run_id` 非空的 run，避免恢复到已被后继替代的 lineage。
- lookup 路径不得与 run-id 路径歧义；foreign/missing scope 不得泄露其他用户的 run。

### R2 - Explicit State Ownership

- Vue Query 唯一拥有 Project、Chapter 和 ChapterWorkflow server cache；statechart、Pinia 和组件不得复制完整实体或项目章节列表。
- XState context 只保存恢复和命令关联所需的有界 interaction 数据，不保存完整 Project、Chapter、候选版本、评审正文或事件历史。
- `selectedChapterNumber`、drawer、modal、focus、版本详情和 sidebar scroll 等纯 UI 状态可继续使用 Vue ref；`generatingChapter`、`evaluatingChapter`、`chapterGenerationResult` 等 lifecycle mirror 必须删除。

### R3 - Explicit Workflow And Transport States

- 使用 XState 与官方 Vue binding，并精确锁定经源码与 peer dependency 核验的兼容版本；不手写平行 reducer。
- workflow phase 与 transport health 必须独立表达。断线或 polling 不能覆盖 running、waiting、finalizing、projection pending、failed 等业务阶段。
- workflow 至少覆盖 idle、submitting、running、waiting-for-selection、finalizing、projection-pending、succeeded、failed、cancelled、superseded；transport 至少覆盖 disconnected、connecting、connected、reconnecting、polling。
- 服务端 `allowed_commands` 是按钮和 command guard 的直接事实；除 idle start 外，不得从 status 猜测可执行命令。

### R4 - Snapshot Reconciliation And SSE Recovery

- workflow snapshot 必须在 API 边界从 `unknown` 运行时解码；未知 schema、非法字段或 scope mismatch 进入可见 contract failure，不得 cast 后继续。
- durable task SSE 只作为“事实可能变化”的唤醒信号；每个有效事件触发 current workflow snapshot refetch，machine 不从 `BackgroundTask` payload 推导 workflow phase。
- snapshot 按 scope、run id、`row_revision` 和连接 epoch 去重；旧 run、旧 revision、旧连接迟到回调和乱序 cursor 不得回退当前状态。
- cursor reset 必须停止旧连接，获取同一 scope 的新 snapshot/cursor pair，再建立新连接；持续断线时进入 polling fallback，业务 phase 保持不变。
- Chapter/project query 只在 `current_chapter_revision` 变化或 terminal/projection 边界需要刷新实体时 invalidate，禁止每个 SSE event 都全量刷新。

### R5 - Single Command Owner

- 新 WritingDesk 只调用 durable workflow start/command API；start、select、retry、retry_external、retry_projection、cancel 均带服务端要求的幂等和 expected revision 前置条件。
- command response 与 409 conflict 中携带的 snapshot 必须写入同一 Vue Query cache，再发送 reconciliation event；客户端不得凭 mutation 成功猜测终态。
- pending command 与 machine guard 阻止双击；服务端 command idempotency 是最终保护。
- 旧独立 generate/evaluate/finalize lifecycle 不再由 WritingDesk 调用。评审由 workflow 自动执行，评审失败通过 workflow retry 恢复；不保留任意已完成章节的独立 evaluate command。

### R6 - Direct Cutover And Release Gate

- 本任务直接完成前端 statechart cutover；不增加 frontend feature flag，不运行 shadow lifecycle，不保留两套 command owner。
- 保留 backend compatibility adapter 和旧 HTTP facade，供上一版本前端回滚；active workflow 的副作用仍只由 durable workflow owner 执行。
- backend Settings 默认继续为关闭；Docker release unit、环境示例、部署脚本和文档必须显式设置 `CHAPTER_WORKFLOW_START_ENABLED=true`，缺失配置应 fail closed，而不是静默发布一个无法工作的新前端。
- 回滚是原子发布回滚：部署上一版前端并关闭 backend gate；不得只关闭 gate 后继续运行仅支持 statechart 的新前端。

### R7 - UI Semantics And Quality Gate

- 状态、失败原因、重试和 projection pending 必须有文本与 ARIA 语义，不能只依赖颜色；保留 AppShell task reminder 契约。
- pure machine tests 必须覆盖所有服务端 status 映射、合法/非法 transition、allowed-command guard、stale snapshot、duplicate command 和 parallel transport 状态。
- actor/query tests 必须覆盖 refresh rehydrate、current lookup null、409 reconciliation、disconnect/replay/reset、scope switch 和 polling fallback。
- 增加可重复执行的 Chromium browser smoke，覆盖 waiting refresh、断线恢复、双击命令、stale event、projection retry 和用户可见/ARIA 状态。
- 完整门禁包含 backend focused tests、OpenAPI/generated artifact drift、frontend lint/type-check/Vitest/Playwright/build 和 XState 引入前后的真实 Vite gzip bundle 对比。

### R8 - User-visible State Semantics

| 状态 | 用户可见语义 | 可执行动作 |
| --- | --- | --- |
| idle | 尚未开始生成 | 开始生成 |
| submitting / running | 命令提交中或章节生成中 | 仅显示服务端允许的取消 |
| waiting-for-selection | 候选版本可供选择；若候选详情尚未同步则明确显示同步中 | 候选就绪后选择版本；服务端允许时可取消 |
| finalizing | 已接受选版，正在提交正文 | 仅显示服务端允许的取消 |
| projection-pending | 正文已提交，正在同步摘要、记忆、RAG 等派生数据 | 服务端允许时重试同步或取消 |
| failed / needs-attention | 显示服务端公开错误；可能重复的外部调用必须明确提示风险 | 只显示 `allowed_commands` 对应的重试、确认风险后重试或取消 |
| succeeded | 章节及 required projections 已完成 | 无 workflow 命令 |
| cancelled | 本轮已取消 | 重新开始新的 workflow |
| superseded | 本轮已被后继替代，正在切换到最新运行 | 禁止命令并自动重新 lookup |
| contract/auth fatal | 当前状态不可信或无权访问 | 禁止业务命令；提供重新同步，认证失败走现有登录恢复 |

## Acceptance Criteria

- [x] AC1：刷新或直接进入 WritingDesk 时，current lookup 能恢复 active、waiting-for-selection、projection-pending、failed 和最近 terminal run；无 run 时稳定进入 idle。
- [x] AC2：current lookup 的 owner scope、多 active revision 排序、terminal fallback、successor 排除和静态路由优先级均有 backend tests。
- [x] AC3：XState machine 使用 parallel workflow/transport regions；断线、重连和 polling 不改变已知业务 phase。
- [x] AC4：generated contract 中每个 workflow/root-job status、node key 与 command 都被测试矩阵穷尽；未知值 fail closed，`allowed_commands` 直接控制 UI，双击只产生一个有效 command。
- [x] AC5：SSE 重放、reset、重复/乱序 cursor、旧 scope 回调、旧 run 和 stale `row_revision` 均不导致状态倒退；持续断线可退化为 polling。
- [x] AC6：command 202 与 typed 409 都用服务端 snapshot 原子更新 workflow query cache；mutation 成功不直接宣告 completed。
- [x] AC7：Vue Query 是 Project、Chapter、Workflow 唯一 server cache；statechart 和 Pinia 未复制实体列表。
- [x] AC8：旧 lifecycle refs、本地 `generation_status` 写入、status/content SSE watcher、旧 reconnect timer 和重复 wait/refetch 链在 cutover 后删除或不再被 WritingDesk 调用。
- [x] AC9：新 WritingDesk 不调用旧 generate/evaluate/finalize endpoint；workflow 是生成、评审、选版、定稿和 projection 的唯一命令 owner。
- [x] AC10：OpenAPI 与 generated TypeScript 同一 release unit 更新，workflow HTTP/SSE payload 均经共享 decoder，`events_url` 不被前端重新硬编码。
- [x] AC11：release 配置显式启用 backend gate；兼容演练证明“上一版前端 + gate 开启”仍路由到同一 durable owner，回滚到“上一版前端 + gate 关闭”后 active run 继续 drain 且不产生第二个 legacy owner/outcome。
- [x] AC12：focused backend tests、`npm run api:check`、lint、type-check、Vitest、Playwright Chromium smoke 与 production build/bundle budget 全部通过。
- [x] AC13：idle/running/waiting/finalizing/projection/failed/succeeded/cancelled/superseded/fatal 的文本、ARIA 语义和动作矩阵均有 component 或 browser 断言；waiting 但候选尚未同步时不能提交空选版。

Acceptance evidence (2026-07-31): backend PostgreSQL tests, generated transport checks,
frontend static/unit/browser/build gates, rollout/rollback drill and desktop/mobile
browser review all pass. Detailed commands and counts are recorded in `implement.md` and
the task `research/` artifacts.

## Out Of Scope

- 不重做 WritingDesk 视觉设计、信息架构、编辑器、assistant panel 或无关响应式布局。
- 不把全站状态迁入 XState，也不把 AppShell task reminder 改造成 workflow UI。
- 不删除 backend compatibility adapter、旧 HTTP facade 或已持久化的 legacy data；contract 删除等待后续发布窗口。
- 不为任意历史/已完成章节保留独立 AI evaluate 命令；本任务只展示 workflow 评审结果并恢复 workflow 评审失败。
- 不修改 durable worker、workflow graph、projection 或 event-log 的业务执行语义，除 current lookup 与 release gate 所需的读契约。

## Blocking Questions

无。用户已授权以完整收敛优先，并接受 direct cutover 与相关发布风险；最终规划摘要仍需单独批准后才能开始实现。
