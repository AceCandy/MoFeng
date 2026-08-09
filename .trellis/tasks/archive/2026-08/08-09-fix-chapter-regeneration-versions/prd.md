# 修复章节重生成与多版本生成

## Goal

让章节生成界面只保留一处进度信息；取消后当前轮次的未确认草稿彻底退出展示与持久化结果；系统设置为两个版本时，新的章节工作流稳定生成并展示两个候选版本。

## Background

- `ChapterWorkflowPanel.vue:11-80` 在生成期间重复展示“章节生成中”状态和取消按钮，而下方已有完整生成进度。
- `WDWorkspace.vue:464-480` 在当前 run 中仍把 `selectedChapterResolvedContent` 作为实时草稿，可能读取取消前的章节缓存；现有 trace 已按 `run_id` 过滤，但正文预览未按 run 隔离。
- `job_service.py:1683-1848,2204-2253,2634-2673,3119-3148` 的取消路径只终止 root job/run，没有清理当前 run 的候选版本、评估和生成轨迹。
- `chapter_workflow_start.py:116-138` 没有像旧 pipeline 一样解析 `writer.chapter_versions`；`chapter_workflow_handler.py:418-425` 因 `versions is None` 回退为一个版本。
- 当前工作树已有 workflow trace、actor 防旧快照、候选正文解包等未提交改动；本任务必须保留并在其上增量修复。

## Requirements

### R1 生成中界面去重

- 在生成进度已经可见的阶段，不再展示独立的“章节生成中/正在提交/正在同步”等大状态行。
- 将“取消本轮”放入生成进度区域；按钮仍由服务端 `allowed_commands` 控制，并保留 pending/disabled 与键盘可达状态。
- 待开始、待选版本、失败恢复、已取消等仍需用户决策的面板内容保持可用。

### R2 取消后从空白重新开始

- 取消命令进入终态后，删除该 run 产生且未被正式章节或历史修订引用的候选版本及其评估，清理该 run 的可删除生成轨迹，并将无正式正文的章节恢复为生成前空状态。
- running、waiting、ambiguous 三类取消路径必须收敛到同一清理语义；清理需幂等，并遵守 root job fencing/锁顺序，迟到 worker 不得重新写回已取消草稿。
- 已确认的 `selected_version_id`、正式正文、ChapterRevision、投影产物、JobEvent、命令/活动审计和 workflow 身份不得删除。
- 前端当前 run 的实时草稿只能来自该 run 的候选；新 run 尚无候选时显示空预览，不得回退到上一轮章节缓存。
- 点击取消时立即清空本地候选描红/落墨快照；服务端取消完成后刷新章节与项目缓存。

### R3 两版本配置生效

- 新章节工作流未显式传入 `flow_config.versions` 时，后端使用现有版本数解析契约读取 `writer.chapter_versions`，并把解析值冻结进 `runtime_inputs.flow_config`。
- 显式请求值优先于系统配置；已存在的 active run 保持其冻结配置，不因设置变化而改写。
- 配置为 2 时，候选生成、持久化和前端当前 run 过滤后均得到两个候选；仍保持现有最大两个版本的产品限制。

## Acceptance Criteria

- [x] 生成进度可见时，页面不再出现重复的“章节生成中”大状态行，“取消本轮”位于生成进度区域且权限、禁用和无障碍行为正确。
- [x] 取消包含未确认候选的 waiting run 后，该 run 的未保护版本、评估和生成轨迹被清理，章节不再返回旧草稿。
- [x] 取消 running/ambiguous run 后，在取消终态得到同样清理结果；重复取消或重复清理不报错、不误删。
- [x] 取消已有正式正文的重生成 run 时，正式正文、选中版本、历史修订和投影数据保持不变，只移除本轮未确认草稿。
- [x] 取消后立即启动新 run，在新候选到达前实时草稿为空；到达后只显示新 run 内容，不闪现旧 run 文本。
- [x] `writer.chapter_versions=2` 且请求未显式传 versions 时，冻结配置为 2，并产生、持久化、展示两个当前 run 候选。
- [x] 显式 `versions=1` 能覆盖系统配置 2；已有 active run 不被新配置改变。
- [x] 相关后端聚焦测试、前端组件/状态测试、TypeScript 类型检查通过；桌面与移动视口无重叠或操作丢失。

## Out of Scope

- 不删除已确认章节正文、修订历史、投影产物或 durable 审计事件。
- 不把“取消本轮”改成自动重新生成；用户仍需主动点击开始生成。
- 不提高两个版本的现有上限，不调整模型提示词、版本文风或评审策略。
- 不重构整个工作流面板、Vue Query 架构或 durable job 框架。

## Risks

- running cancel 早于 worker 真正停下时清理会被迟到写入覆盖，因此只能在持有有效 fence 的取消终态执行持久化清理。
- 版本删除必须按当前 run provenance 和正式/历史引用双重保护，不能按 chapter 全量删除。
- generation trace 是可重建投影视图；清理当前 run trace 不能删除 JobEvent 或改变全局 projector cursor。
- 当前工作树已有相关未提交改动，实施时必须保留其 run 过滤、stale snapshot 防护和候选正文清洗行为。
