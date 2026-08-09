# 修复章节重生成与多版本生成 - 实施计划

## 1. 前端界面与预览隔离

- 调整 `ChapterWorkflowPanel` 和 `WDWorkspace` 的阶段渲染，去除生成期间重复状态行。
- 在生成进度组件内加入受 `allowedCommands` 控制的取消入口，统一清理本地预览后发出取消事件。
- 当前 run 的实时草稿改为只读取当前 run 候选，禁止回退旧章节缓存。
- 更新组件单测与取消后重启 E2E/集成断言。

验证：聚焦运行 `ChapterWorkflowPanel`、`ChapterGenerating`、`WDWorkspace`/workflow actor 相关 Vitest；断言旧文本不出现在新 run 预览。

## 2. 取消终态持久化清理

- 在现有 JobService/workflow 取消终态增加共享清理逻辑，覆盖 waiting、ambiguous 与 worker 完成取消。
- 按 run provenance 删除未保护候选/评估和当前 run trace，必要时重置无正式正文的章节生成字段。
- 保持 job/run/event 原子性、锁顺序、fencing 与幂等。
- 补充 waiting/running/ambiguous、正式版本保护、重复清理测试。

验证：聚焦运行 chapter workflow command、persistence、durable runtime 相关 Pytest；数据库测试若环境无 PostgreSQL则明确记录未验证项。

## 3. 多版本配置贯通

- 复用旧 pipeline 的版本数解析契约，并让 ChapterWorkflowStartService 在冻结 runtime inputs 前解析。
- 保持显式请求优先、active run 冻结和 idempotency 一致性。
- 补充系统配置 2、显式覆盖 1、生成/持久化两个候选测试。

验证：聚焦运行 start service、activities、persistence 测试，确认 provider ordinal 为 1/2 且 candidate ids 数量为 2。

## 4. 独立复核与质量门

- 运行 `trellis-check`，独立检查 spec、取消并发边界、正式版本保护、跨层数据流和工作树污染。
- 运行前端类型检查、相关 Vitest 与 Impeccable detector。
- 用桌面和移动视口各检查一次生成进度、取消按钮、实时草稿空态和两候选布局；调试服务与浏览器在结束前关闭。
- 检查 `git diff`，确认只改任务相关行，未覆盖现有用户改动，未新增缓存、截图、密钥或本地调试产物。

## 5. 回滚点

- 前端显示错误：回滚 UI/预览隔离改动，不影响后端数据。
- 取消清理保护测试失败：停止交付并回滚持久化清理，不以仅前端隐藏代替。
- 版本解析回归：回滚共享解析接线，保留旧 pipeline 行为并继续定位，不改变 API schema。

## 6. 验证记录

- 前端相关 Vitest：108 项通过；取消与工作区聚焦回归：23 项通过。
- 前端 `type-check`、相关 ESLint、Impeccable detector 与 `git diff --check` 通过。
- 后端扩大回归：72 项通过；任务相关 Ruff 通过，基线文件仅保留 HEAD 已存在的告警豁免。
- 浏览器检查覆盖 1440x1000 与 390x844：进度区单一取消入口、空实时草稿、两候选响应式布局及无横向溢出均符合预期。
- 独立只读复核未发现阻断缺陷；未执行全量仓库测试、真实 PostgreSQL 并发/迟到 worker 集成测试或真实模型端到端生成。
