# Journal - AceCandy (Part 1)

> AI development session journal
> Started: 2026-07-05

---



## Session 1: 章节朗读与 TTS 模型接入及供应商能力隔离

**Date**: 2026-07-10
**Task**: 章节朗读与 TTS 模型接入及供应商能力隔离
**Branch**: `main`

### Summary

接入章节朗读与 TTS（MiMo Chat Audio + OpenAI Speech 两协议）；乾坤万象中枢新增语音朗读 Tab，并将供应商按 tts 能力隔离，修复 TTS Tab 获取全部供应商的问题；trellis-check 全量复核 15/15 验收项通过，自修回退通知补失败原因摘要与取消模型预取；新建 pipeline 静态测试修复跟踪任务。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `c37ee24` | (see git log) |
| `07b6442` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 2: 修复 pipeline 静态测试 node_key 断言

**Date**: 2026-07-10
**Task**: 修复 pipeline 静态测试 node_key 断言
**Branch**: `main`

### Summary

修复 test_pipeline_langgraph_refactor_static 两个预存失败：_graph_persist_versions 的 trace node_key 已从 save_draft 重构为 persist_versions（旧 key 经 TRACE_KEY_TO_GRAPH_NODE 映射保留兼容），更新静态断言对齐现状；动态行为不变，仍持久化为草稿（WAITING_FOR_CONFIRM）。后端全套 184 passed。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `b3924ce` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 3: 章节朗读悬浮控件与浏览器首字修复

**Date**: 2026-07-11
**Task**: 章节朗读悬浮控件与浏览器首字修复
**Branch**: `main`

### Summary

把章节朗读从工具栏行内按钮改造为正文区右上的独立悬浮控件（国风样式）：主按钮（入口/暂停/继续/停止）+ 状态文字 + 音色选择（仅列在线 Natural 中文语音并显示中文名，支持试听）+ 倍速选择 + 重置；音色与倍速偏好持久化到 localStorage。正文当前段加粗+石青变色+蓝色波浪线高亮并自动滚动居中；抽共享分段 util 让朗读与正文展示段落对齐；tabs 切换栏移出正文滚动区，滚动正文时纹丝不动。修复浏览器朗读首字被吞：speechSynthesis.cancel + 段间延时 + 前置静音填充 + 优先选 zh-CN Online (Natural) 神经语音（规避 Windows 本地微软桌面语音的裁首字 bug）。vue-tsc 0 错误，全量 111 测试通过。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `1a8a4c0` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 4: TTS 朗读：Web Audio 播放 + 短段合并区间高亮 + 后端 wav 标准化

**Date**: 2026-07-12
**Task**: TTS 朗读：Web Audio 播放 + 短段合并区间高亮 + 后端 wav 标准化
**Branch**: `main`

### Summary

朗读播放层由 HTMLAudioElement 改为 Web Audio（decodeAudioData + AudioBufferSourceNode），修复部分标准 wav 静音无法播放；buildPlayback 相邻短段落按完整段落合并到约 400 字减少请求往返、播放时区间内全部高亮；段间停顿 120→400ms；后端 wav 标准化为 16-bit PCM + data chunk 完整性/静音校验与一次重试。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `8f6e79c` | (see git log) |
| `6f23c48` | (see git log) |
| `6d03d62` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 5: TTS 朗读：回退短段合并为逐段 + 流式评估后弃

**Date**: 2026-07-12
**Task**: TTS 朗读：回退短段合并为逐段 + 流式评估后弃
**Branch**: `main`

### Summary

短段合并虽减请求数，但合并段只能区间高亮、无法精确到单段，按需回退为逐段合成（每段独立请求+独立高亮，移除 MERGE_TARGET，保留 Web Audio+段间停顿+预热并发）。流式合成（端到端首段秒播）实现完成但浏览器实测卡顿 + 逐段下边际收益不值前后端协议与播放层重写的复杂度，评估后放弃，代码已 stash drop，design 保留参考。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `e831569` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 6: TTS 朗读语气优化：有声书主播提示词 + 去模型侧变速

**Date**: 2026-07-13
**Task**: TTS 朗读语气优化：有声书主播提示词 + 去模型侧变速
**Branch**: `main`

### Summary

MiMo 朗读链路改造：(1) _synthesize_mimo 删除 speed 形参与「正常语速 X 倍朗读」prompt 变速分支，倍速统一交给前端 AudioBufferSourceNode.playbackRate，消除前后端双重变速隐患；(2) messages 改为 [system 有声书主播提示词(方案B), assistant 原文]，引导声情并茂、忠实原文的演播风格。openai_speech 协议、前端、schema 均未触碰。验证：backend/tests/test_tts_service.py 12 passed。未验证：真实 MiMo 端到端合成（需上游凭证）。顺带调研并记录了 AudioBufferSourceNode 变调问题（独立后续）。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `6e98eef` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 7: 朗读变速保调：audio 元素替换 Web Audio 主路径

**Date**: 2026-07-13
**Task**: 朗读变速保调：audio 元素替换 Web Audio 主路径
**Branch**: `main`

### Summary

模型段朗读主路径改用 <audio> 元素（preservesPitch 保调，变速不变调），<audio> error 时兜底 Web Audio（能出声但变调），再失败切浏览器 speechSynthesis；三级兜底链 audio→webaudio→浏览器。pause/resume/stop 按 activeBackend 分派。根因：后端已把上游 wav 标准化为 16-bit PCM，<audio> 不再静音，故从 Web Audio 切回 <audio>（AudioBufferSourceNode.playbackRate 无法保调，Web Audio 规范层面不支持）。trellis-check 独立复核修复试听 objectURL 泄漏 + 补 webaudio 兜底路径 pause/resume/stop 测试。vue-tsc 通过、16 测试绿。保调效果待人工实测。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `ec98988` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 8: ChapterGenerating 拆分完成（Slice 8-9，2261→394 达成 <500）

**Date**: 2026-07-15
**Task**: ChapterGenerating 拆分完成（Slice 8-9，2261→394 达成 <500）
**Branch**: `main`

### Summary

Slice 8 抽 useChapterGenerationTrace composable（trace 组装三 computed activeStepTraces/activeTrace/activeStepDetails，977→900，3 用例指针跟随）；Slice 9 抽 ChapterPipeline 子组件（pipeline 进度卡 article+style+keyframes+@media，解决 scoped 只读覆写内部元素难题：根级覆写留父靠子根继承 data-v + 3 条内部元素级迁子组件收 readOnly prop 自绑 is-read-only 类，未用 :deep），900→394，acceptance <500 达成。9-slice 完成，child task 归档。验证 vue-tsc 0 / timing 7+7 / 全量 vitest 141 / eslint 0 新增。剩余人工目视：只读模式 pipeline 样式（timing 不覆盖样式）。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `9c86955` | (see git log) |
| `df9ce7c` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 9: NovelDetailShell Slice 10：抽 ShellContent 子组件（达标 <500）

**Date**: 2026-07-16
**Task**: NovelDetailShell Slice 10：抽 ShellContent 子组件（达标 <500）
**Branch**: `main`

### Summary

NovelDetailShell Slice 10：抽 novel-detail/ShellContent.vue 子组件（content 区 main→content-wrap→content-frame→content-surface + loading/error/component 三分支 template + content-surface 系 style 连续块 + 3 个 @media content 部分 + classical :deep 覆写 5 条逐字迁子）。父透传 6 props（useShellSectionContent 返回值 currentComponent/isSectionLoading/currentError/componentProps/contentCardClass/componentContainerClass）+ emit edit/add/retry（retry 无参父侧 ()=>reloadSection(activeSection,true) 内联）。componentProps 用 Record<string,unknown>（动态 component v-bind 不强校验）。父 script 零改动无 orphan。scoped 跨组件：content-surface 系内部元素规则全迁子，:deep 对动态 <component> 覆写靠 DOM 祖孙等价（区别 Slice2 子根留父）。@media 拆分（drawer-collapsed/body height/根变量留父，content-wrap/content-surface padding 迁子）。uiAuditRegression content-surface classical/flat 断言重定向 ShellContent.vue。action-btn 预存死代码留父。613→432（−181，<500 达标）。10-slice 完成，NovelDetailShell acceptance 达成，parent #22 进度 3/5（ChapterGenerating 394 + WDWorkspace 498 + NovelDetailShell 432）。vue-tsc 0 / vitest 141 绿 / eslint 0 新增。归档 child task。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `2ace11b` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 10: WritingDesk 拆分收口（Slice 11-15，2009→619）

**Date**: 2026-07-16
**Task**: WritingDesk 拆分收口（Slice 11-15，2009→619）
**Branch**: `main`

### Summary

WritingDesk.vue 拆分 Slice 11-15：useWritingDeskNavigation(章节定位状态机)/WDProjectStatus(加载错误展示子组件)/useWritingDeskConfirm(翻案 Slice5 3c 不抽决定，定稿流程 composable)/dead code 清理(progress群+line-clamp+utils dead imports)/ink-backdrop-fade 死 keyframes 收口清理。2009→619(-69%)。未达 <500 硬指标，用户 A 决策按「已尽力+不过度抽象」收口：layout grid 拆分=17props+17emits 纯透传过度抽象否决，mobile-actions/backdrop 边际不拆，script 已极限。每 slice 三件套绿(vue-tsc 0/vitest 141/eslint 0 新增)。子任务归档，parent #22 仍 in_progress(3/5 达标，PersonalModelRouting 未开始)。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `fa9a3ba` | (see git log) |
| `3ebd274` | (see git log) |
| `2acc53a` | (see git log) |
| `0d9c201` | (see git log) |
| `2f55914` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 11: PersonalModelRouting Slice 14-15 收口 <500

**Date**: 2026-07-16
**Task**: PersonalModelRouting Slice 14-15 收口 <500
**Branch**: `main`

### Summary

PMR 2684->493 <500 达标（15-slice 完成）。Slice 14 抽 ReadinessPanel 子组件 + 清理 dead CSS（616->514）；Slice 15 抽 FeedbackPanel 子组件收口（514->493 <500）；补 8 子组件 AIMETA 首行；prd AC 全勾选。三件套绿（vue-tsc 0 / vitest 151 / eslint 0 error + 11 同类 warning）。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `589d17a` | (see git log) |
| `5f3e2c1` | (see git log) |
| `e825d7a` | (see git log) |
| `c19c04e` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 12: 前端基线修复

**Date**: 2026-07-17
**Task**: 前端基线修复
**Branch**: `main`

### Summary

修复前端基线破损：build 失败（PMR import 无 .vue + 具名 import SFC）+ vue-tsc 34->0 error + :global warning。四件套绿（vue-tsc 0 / vitest 152 / build 绿无 warning / eslint 0 error）。暴露历史 PMR/NovelDetailShell/WDWorkspace 收口三件套绿假绿（漏 cd 跑 tsc help + 未跑 build），沉淀 memory 四件套验证流程。#28 Phase 1 暂停待续。

### Main Changes

(Add details)

### Git Commits

(No commits - planning session)

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 13: #28 main.css 按域拆分（Phase 3 + 真机验证）

**Date**: 2026-07-17
**Task**: #28 main.css 按域拆分（Phase 3 + 真机验证）
**Branch**: `main`

### Summary

main.css 4966->34 行（减 99.3%），拆为入口 + 30 partial（1 base + 3 elements + 26 components + 1 tokens，共 4954 行）。Phase 3 Slice 5-23 共 19 slice，每 slice 四件套绿 + commit + push。关键决策：dark 覆写随域迁移 / App Shell 响应式段补抽 / base.css @import 最后保持 cascade / readCssBlock lookbehind 修复。AC 5 真机验证通过：登录页/workspace/写作台 light/dark 视觉等价 + 375px 窄屏响应式 + dark token cascade 等价，无视觉回归。6 项 AC 全部达成。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `ac12e0e` | (see git log) |
| `466c17a` | (see git log) |
| `2dfa37b` | (see git log) |
| `1a1f136` | (see git log) |
| `f6165e5` | (see git log) |
| `b174845` | (see git log) |
| `b1489ca` | (see git log) |
| `070490b` | (see git log) |
| `fe21efb` | (see git log) |
| `5ce84cf` | (see git log) |
| `461df24` | (see git log) |
| `6d3a803` | (see git log) |
| `1b28862` | (see git log) |
| `86260e6` | (see git log) |
| `fa0f2d7` | (see git log) |
| `33e9882` | (see git log) |
| `ef3c88c` | (see git log) |
| `ab49760` | (see git log) |
| `285ba7d` | (see git log) |
| `539fd7e` | (see git log) |
| `a7e0902` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 14: L27 SSE 章节状态事件驱动实施 + 真机验证

**Date**: 2026-07-17
**Task**: L27 SSE 章节状态事件驱动实施 + 真机验证
**Branch**: `main`

### Summary

L27 SSE 章节状态改事件驱动（Redis pub-sub，方案 A/A/A）：新增 event_bus（publish fire-and-forget 不阻塞生成 + subscribe 失败返回 None 供降级）；pipeline 三处状态变更 commit 后 publish 轻量通知；stream_chapter_status 去 sleep(1.0) 轮询改 subscribe+get_message+DB 初始态兜底+降级 poll_loop（启动不可用/运行中断连均回退 5s）；前端零适配。真实 Redis 端到端验证 publish<->subscribe 管道 + HTTP SSE 真机验证通过（not_generated->generating->successful 推送序列 + 终态 final 关闭），后端 208 passed（+13 test_event_bus）。修复 novels.py 行尾 CRLF 被 Edit 误转 LF 问题。stream_background_tasks 可选未做。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `9dc6054` | (see git log) |
| `5851647` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 15: L27B 后台任务 SSE 事件驱动 + 工程基线父 task 归档

**Date**: 2026-07-17
**Task**: L27B 后台任务 SSE 事件驱动 + 工程基线父 task 归档
**Branch**: `main`

### Summary

后台任务 SSE 改事件驱动：stream_background_tasks 去固定 1.5s 轮询，改 subscribe+初始态快照+get_message 事件驱动+Redis 断连降级 poll_loop；BackgroundTaskService 5 个写方法 commit 后 publish 通知；复用 L27 event_bus 范式，前端零适配。后端 220 passed（+12 test_event_bus）+ 真机 SSE 验证通过（queued->running->succeeded 推送序列）。AC3「SSE 不再每秒查 DB」完全达成。工程基线父 task 8 子任务全归档，AC 全达成。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `f5b83a3` | (see git log) |
| `5afaa20` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 16: 修复 memory_layer FK 类型与 DateTime 时区 + PG 迁移立项

**Date**: 2026-07-19
**Task**: 修复 memory_layer FK 类型与 DateTime 时区 + PG 迁移立项
**Branch**: `main`

### Summary

修复 memory_layer 4 表 project_id FK String(255)->String(36)（H6，与 novel_projects.id 对齐）+ 7 处 DateTime 加 timezone=True（M1）。新增跨方言 alembic migration 03bb4c218e9e（batch_alter_table + FK drop/recreate reflect 名称 + postgresql_using）。mysql 往返 + sqlite migration 往返 + pytest 220 passed 验证绿（trellis-check 独立复跑）。同步修正 database-guidelines L118-131 过时的 schema 初始化描述（生产纯 alembic，create_all test-only）。完成 PG 迁移 parent task 树立项（07-19-migrate-to-postgres: prd/design/implement + research×3 + 4 child prd）。pg 实测留 child 01；baseline sqlite use_alter 预存问题 + L134 Celery 失效引用留 follow-up。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `71df072` | (see git log) |
| `38f817a` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 17: PG 入口层连通 PostgreSQL（DB_PROVIDER=postgresql + asyncpg + alembic upgrade head 建全表）

**Date**: 2026-07-19
**Task**: PG 入口层连通 PostgreSQL（DB_PROVIDER=postgresql + asyncpg + alembic upgrade head 建全表）
**Branch**: `main`

### Summary

(Add summary)

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `540d980` | (see git log) |
| `c644ee5` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 18: PG 部署配置（compose postgres profile + app POSTGRES_* env + pg-data volume + 两处 env.example）

**Date**: 2026-07-19
**Task**: PG 部署配置（compose postgres profile + app POSTGRES_* env + pg-data volume + 两处 env.example）
**Branch**: `main`

### Summary

(Add summary)

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `31e62e7` | (see git log) |
| `4e792f5` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 19: 升级 Trellis 至 0.6.8

**Date**: 2026-07-23
**Task**: 升级 Trellis 至 0.6.8
**Branch**: `main`

### Summary

升级 Trellis 项目模板与 Claude/Codex 集成至 0.6.8，采用官方最新版 skill，并完成版本、模板状态及配置解析验证。

### Main Changes

- Detailed change bullets were not supplied; see the summary above.

### Git Commits

| Hash | Message |
|------|---------|
| `7137108` | (see git log) |

### Testing

- Validation was not recorded for this session.

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 20: 任务状态提醒

**Date**: 2026-07-23
**Task**: 任务状态提醒
**Branch**: `main`

### Summary

实现导航栏后台任务状态聚合与按用户持久化的终态已读提醒，补充行为测试和前端可执行规范。

### Main Changes

- Detailed change bullets were not supplied; see the summary above.

### Git Commits

| Hash | Message |
|------|---------|
| `017823f` | (see git log) |

### Testing

- Validation was not recorded for this session.

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 21: 统一章节上下文契约

**Date**: 2026-07-28
**Task**: 统一章节上下文契约
**Branch**: `main`

### Summary

规划章节生命周期架构收敛，并完成生成、评审与一致性检查的 canonical Chapter Context 统一、恢复契约和测试覆盖。

### Main Changes

- Detailed change bullets were not supplied; see the summary above.

### Git Commits

| Hash | Message |
|------|---------|
| `2516ada` | (see git log) |
| `edebafb` | (see git log) |

### Testing

- Validation was not recorded for this session.

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 22: 显式数据库生命周期

**Date**: 2026-07-28
**Task**: 显式数据库生命周期
**Branch**: `main`

### Summary

拆分数据库 migration、versioned bootstrap、readiness 与 runtime，增加旧库显式认领和部署顺序契约。

### Main Changes

- Detailed change bullets were not supplied; see the summary above.

### Git Commits

| Hash | Message |
|------|---------|
| `00afc02` | (see git log) |
| `afa3c16` | (see git log) |
| `2f62c06` | (see git log) |

### Testing

- Validation was not recorded for this session.

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 23: 收敛 durable job 与 event log

**Date**: 2026-07-28
**Task**: 收敛 durable job 与 event log
**Branch**: `main`

### Summary

建立 PostgreSQL durable job、独立 worker lease/fencing、可重放 SSE cursor，并迁移章节长任务、补齐部署与恢复测试契约。

### Main Changes

- Detailed change bullets were not supplied; see the summary above.

### Git Commits

| Hash | Message |
|------|---------|
| `8dbed8e` | (see git log) |
| `918b151` | (see git log) |

### Testing

- Validation was not recorded for this session.

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 24: 完成可重放章节投影

**Date**: 2026-07-29
**Task**: 完成可重放章节投影
**Branch**: `main`

### Summary

完成 transactional outbox 驱动的章节投影、重放与 rollout fencing，补齐 AI 用量成本、retention、告警和发布契约，并以真实 PostgreSQL 全量测试及随机 schema 隔离验证收敛并发与清理风险。

### Main Changes

- Detailed change bullets were not supplied; see the summary above.

### Git Commits

| Hash | Message |
|------|---------|
| `b28be70` | (see git log) |
| `3a7f203` | (see git log) |

### Testing

- Validation was not recorded for this session.

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 25: 完成持久化章节工作流

**Date**: 2026-07-30
**Task**: 完成持久化章节工作流
**Branch**: `main`

### Summary

建立 PostgreSQL 持久化 Chapter workflow，收敛 checkpoint、command、activity、finalize、projection、trace、恢复与测试隔离契约，并完成全量质量门禁。

### Main Changes

- Detailed change bullets were not supplied; see the summary above.

### Git Commits

| Hash | Message |
|------|---------|
| `e82423c` | (see git log) |
| `794c9bc` | (see git log) |

### Testing

- Validation was not recorded for this session.

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 26: 生成 Transport Contracts

**Date**: 2026-07-30
**Task**: 生成 Transport Contracts
**Branch**: `main`

### Summary

建立确定性 FastAPI OpenAPI 导出、generated TypeScript ownership、版本化 task SSE decoder 与跨层 CI 门禁，并固化可执行 transport contract 规范。

### Main Changes

- Detailed change bullets were not supplied; see the summary above.

### Git Commits

| Hash | Message |
|------|---------|
| `529490e` | (see git log) |
| `cc28aad` | (see git log) |

### Testing

- Validation was not recorded for this session.

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 27: 完成 WritingDesk statechart 收敛

**Date**: 2026-07-31
**Task**: 完成 WritingDesk statechart 收敛
**Branch**: `main`

### Summary

建立章节工作流 current/release 契约，将 WritingDesk 切换到 fail-closed statechart，补齐前后端回归、E2E、发布回滚和 bundle 预算证据，并同步可执行规范。

### Main Changes

- Detailed change bullets were not supplied; see the summary above.

### Git Commits

| Hash | Message |
|------|---------|
| `49963ba` | (see git log) |
| `b429ac9` | (see git log) |
| `6e39d24` | (see git log) |

### Testing

- Validation was not recorded for this session.

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 28: 收敛数据库启动回归并完成架构任务收尾

**Date**: 2026-07-31
**Task**: 收敛数据库启动回归并完成架构任务收尾
**Branch**: `main`

### Summary

修复 c8 generation trace projection migration 对 ORM create_all 预建表的精确接管，保留 cursor；结构漂移、offline SQL 和破坏性 downgrade 均 fail closed。补齐 PostgreSQL 回归测试、alembic check 与数据库规范，验证 db-check ready。AC11 的真实 provider/生产发布窗口验收仍为后续风险。

### Main Changes

- Detailed change bullets were not supplied; see the summary above.

### Git Commits

| Hash | Message |
|------|---------|
| `b4c9e8d` | (see git log) |

### Testing

- Validation was not recorded for this session.

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 29: 修复候选描红稿重复展示

**Date**: 2026-08-09
**Task**: 修复候选描红稿重复展示
**Branch**: `main`

### Summary

首次生成且尚无正式正文时仅展示一份描红候选；保留已定稿正文对照与历史版本兜底，并补充回归测试。

### Git Commits

| Hash | Message |
|------|---------|
| `97a51c6` | (see git log) |

### Status

[OK] **Completed**


## Session 30: 修复章节重生成与多版本生成

**Date**: 2026-08-09
**Task**: 修复章节重生成与多版本生成
**Branch**: `main`

### Summary

修复生成界面重复状态与取消入口，统一清理取消轮次草稿和轨迹，贯通双版本配置；同时提交既有章节工作流进度、正文清洗、Trellis 工具与视觉检查产物。

### Git Commits

| Hash | Message |
|------|---------|
| `d1c3350` | (see git log) |
| `296c15f` | (see git log) |

### Status

[OK] **Completed**


## Session 31: 修复章节实时进度停滞

**Date**: 2026-08-10
**Task**: 修复章节实时进度停滞
**Branch**: `main`

### Summary

串行化同 scope 的 SSE 唤醒查询，合并在途期间的新 cursor，并在旧快照完成后补查最新状态；补充回归测试和前端 SSE hook 规范。

### Git Commits

| Hash | Message |
|------|---------|
| `76f29e8` | (see git log) |

### Status

[OK] **Completed**


## Session 32: 修复章节生成响应与失败节点恢复

**Date**: 2026-08-10
**Task**: 修复章节生成响应与失败节点恢复
**Branch**: `main`

### Summary

收紧模型响应边界，修复截断与工作流歧义恢复，并完善失败节点重试和生成进度动效。

### Git Commits

| Hash | Message |
|------|---------|
| `b797165c74bd52abec80cfc8cf080dd0417cac55` | (see git log) |

### Status

[OK] **Completed**


## Session 33: 恢复后端、前端与 E2E 质量基线

**Date**: 2026-08-11
**Task**: 恢复后端、前端与 E2E 质量基线
**Branch**: `main`

### Summary

修复注册与 OAuth 契约、日志测试隔离、静态检查与格式漂移、OpenAPI 工具链和写作台浏览器契约；最终后端 707/707、前端单测 291/291、Playwright 20/20，所有质量门退出 0。

### Git Commits

| Hash | Message |
|------|---------|
| `bc43e84` | (see git log) |
| `0f249b4` | (see git log) |
| `f4c5167` | (see git log) |
| `6a69c2b` | (see git log) |
| `62e59a0` | (see git log) |
| `6b33235` | (see git log) |
| `b8767f5` | (see git log) |
| `478f7b0` | (see git log) |
| `5f410bb` | (see git log) |
| `b2e4e91` | (see git log) |

### Status

[OK] **Completed**


## Session 34: 完成依赖治理与发布状态机

**Date**: 2026-08-12
**Task**: 完成依赖治理与发布状态机
**Branch**: `main`

### Summary

完成 Python 与前端依赖治理、PyJWT 兼容迁移和 hash lock；将 Docker 发布重构为质量门、双架构候选扫描、真实 smoke、digest promotion 与可恢复 metadata 状态机。正式 run 31596457677 全绿发布 v0.1.35，version/latest/candidate 均指向 sha256:e070890176ede70114781d858f598b287ea6216c164a5d92e6975cb0ac446230，Git tag 与 metadata 均绑定 source 82b2311；DOCKERHUB_TOKEN 已确认为该 workflow 专用。

### Git Commits

| Hash | Message |
|------|---------|
| `69c1e87` | (see git log) |
| `d7c1070` | (see git log) |
| `cfd1e82` | (see git log) |
| `f54d18e` | (see git log) |
| `1ee4849` | (see git log) |
| `c582696` | (see git log) |
| `cbee73b` | (see git log) |
| `cb63508` | (see git log) |
| `82b2311` | (see git log) |
| `f909723` | (see git log) |

### Status

[OK] **Completed**


## Session 35: 完成通用弹窗与写作台无障碍整改

**Date**: 2026-08-12
**Task**: 完成通用弹窗与写作台无障碍整改
**Branch**: `main`

### Summary

完成 U1 无障碍整改：通用弹窗接入统一焦点管理，写作台 pipeline 使用原生按钮并补齐键盘/触控语义，助手滚动区可聚焦，新增 axe Playwright 验收与 focused tests，更新 frontend component spec。lint、type-check、unit 296/296、build、生产依赖 audit、完整 Playwright 26/26 全部通过；U1 已提交 d1a0abf 并归档。D1/T1 仍待实施。

### Git Commits

| Hash | Message |
|------|---------|
| `d1a0abf` | (see git log) |

### Status

[OK] **Completed**


## Session 36: 补全 durable worker 部署摘要

**Date**: 2026-08-12
**Task**: 补全 durable worker 部署摘要
**Branch**: `main`

### Summary

完成 D1：README 更新为 migrate → bootstrap → app + worker，明确 one-shot 门禁、app/worker 同一发布单元、HTTP readiness 与 worker 健康区别、health/metrics 检查命令，并链接 docs/DEPLOYMENT.md。仅修改 README，契约检查与 git diff --check 通过；已提交 c587ed8 并归档 D1。

### Git Commits

| Hash | Message |
|------|---------|
| `c587ed8` | (see git log) |

### Status

[OK] **Completed**


## Session 37: 补齐 scoped task SSE 纵深校验

**Date**: 2026-08-12
**Task**: 补齐 scoped task SSE 纵深校验
**Branch**: `main`

### Summary

完成 T1：task SSE decoder 复核嵌套 task 的 expected stream scope，scope 漂移以 malformed/scope 拒绝且不调用 onTask；保留全局任务流兼容性和原 snapshot scope 规则。同步 transport contract，focused 18/18、完整 unit 298/298、lint、type-check、diff check 通过；已提交 5cb3c20 并归档 T1。

### Git Commits

| Hash | Message |
|------|---------|
| `5cb3c20` | (see git log) |

### Status

[OK] **Completed**


## Session 38: 完成增量审计整改

**Date**: 2026-08-12
**Task**: 完成增量审计整改
**Branch**: `main`

### Summary

完成 A1、A2、Q1、R1、U1、D1、T1 七个工作包；全量后端与前端质量门通过，Playwright 26/26；正式发布 run 31596457677 成功，Git tag、版本镜像、latest、metadata 均绑定 source 82b2311 和 digest sha256:e070890176ede70114781d858f598b287ea6216c164a5d92e6975cb0ac446230；清理测试生成物并归档父任务。

### Git Commits

| Hash | Message |
|------|---------|
| `bc43e84` | (see git log) |
| `0f249b4` | (see git log) |
| `f4c5167` | (see git log) |
| `6a69c2b` | (see git log) |
| `62e59a0` | (see git log) |
| `6b33235` | (see git log) |
| `b8767f5` | (see git log) |
| `478f7b0` | (see git log) |
| `5f410bb` | (see git log) |
| `b2e4e91` | (see git log) |
| `69c1e87` | (see git log) |
| `d7c1070` | (see git log) |
| `cfd1e82` | (see git log) |
| `f54d18e` | (see git log) |
| `1ee4849` | (see git log) |
| `c582696` | (see git log) |
| `cbee73b` | (see git log) |
| `cb63508` | (see git log) |
| `82b2311` | (see git log) |
| `f909723` | (see git log) |
| `d1a0abf` | (see git log) |
| `c587ed8` | (see git log) |
| `5cb3c20` | (see git log) |

### Status

[OK] **Completed**


## Session 39: 修复润色后重复选版

**Date**: 2026-08-13
**Task**: 修复润色后重复选版
**Branch**: `main`

### Summary

人工确认阶段只投影并确认 AI 优选且完成润色的章节版本；保留旧数据兼容回退，并补充后端与前端回归测试。

### Git Commits

| Hash | Message |
|------|---------|
| `e862e92` | (see git log) |

### Status

[OK] **Completed**


## Session 40: 修复 durable 优选版本投影

**Date**: 2026-08-13
**Task**: 修复 durable 优选版本投影
**Branch**: `main`

### Summary

从 durable review.best_ordinal 持久化唯一优选标记，补充主链回归测试与跨层规范，确保人工确认仅展示润色后的优选版本。

### Git Commits

| Hash | Message |
|------|---------|
| `a789429` | (see git log) |

### Status

[OK] **Completed**


## Session 41: Retire PipelineOrchestrator

**Date**: 2026-08-13
**Task**: Retire PipelineOrchestrator
**Branch**: `main`

### Summary

Retired the legacy chapter generation pipeline, routed every generation entry through the durable Chapter workflow, removed the start gate and legacy job registration, migrated contracts/tests/docs, and verified targeted backend/frontend checks plus independent review.

### Git Commits

| Hash | Message |
|------|---------|
| `5b42ce8` | (see git log) |

### Status

[OK] **Completed**


## Session 42: 完成章节工作流节点重构

**Date**: 2026-08-16
**Task**: 完成章节工作流节点重构
**Branch**: `main`

### Summary

完成章节未成功工作流重置、投影进度展示与完成态界面精简，补充聚焦回归测试并归档任务。

### Git Commits

| Hash | Message |
|------|---------|
| `4c65b96` | (see git log) |

### Status

[OK] **Completed**


## Session 43: 正文节点模型路由

**Date**: 2026-08-20
**Task**: 正文节点模型路由
**Branch**: `main`

### Summary

统一正文 DAG 路由展示，拆分两个候选写作模型路由，并增加 general_chat 通用路由。

### Git Commits

| Hash | Message |
|------|---------|
| `4f81041` | (see git log) |

### Status

[OK] **Completed**


## Session 44: 提高章节正文输出上限

**Date**: 2026-08-20
**Task**: 提高章节正文输出上限
**Branch**: `main`

### Summary

将正文候选、修订与压缩调用的输出上限统一为 20000，并补充参数回归断言；聚焦测试通过。

### Git Commits

| Hash | Message |
|------|---------|
| `2882fe7` | (see git log) |

### Status

[OK] **Completed**


## Session 45: 收敛章节人工确认节点

**Date**: 2026-08-20
**Task**: 收敛章节人工确认节点
**Branch**: `main`

### Summary

将单候选人工确认合并到流程节点悬停操作，保留多候选选版，并完善失败节点重试与针对性验证。

### Git Commits

| Hash | Message |
|------|---------|
| `5ab31b6` | (see git log) |

### Status

[OK] **Completed**


## Session 46: 统一节点重试反馈

**Date**: 2026-08-20
**Task**: 统一节点重试反馈
**Branch**: `main`

### Summary

移除失败节点重试的黄色整节点强调，使其与人工确认节点一致，仅在悬停或聚焦时切换操作文案。

### Git Commits

| Hash | Message |
|------|---------|
| `cdb85b0` | (see git log) |

### Status

[OK] **Completed**


## Session 47: Tighten blueprint transport boundaries

**Date**: 2026-08-21
**Task**: Tighten blueprint transport boundaries
**Branch**: `main`

### Summary

Reused generated blueprint and conversation DTOs, centralized unknown-field parsing with a focused regression test, simplified admin request delegation, and passed frontend quality gates.

### Git Commits

| Hash | Message |
|------|---------|
| `0172809` | (see git log) |

### Status

[OK] **Completed**


## Session 48: 替换脆弱前端静态测试

**Date**: 2026-08-21
**Task**: 替换脆弱前端静态测试
**Branch**: `main`

### Summary

将 Vite、概念对话刷新、SSE final 与 HTTP payload 的源码字符串断言替换为运行时测试；保留其余架构静态门禁，并记录 Node 侧 Vite 配置测试约定。

### Git Commits

| Hash | Message |
|------|---------|
| `349bd97` | (see git log) |

### Status

[OK] **Completed**


## Session 49: 后端测试分层与技术债任务树

**Date**: 2026-08-22
**Task**: 后端测试分层与技术债任务树
**Branch**: `main`

### Summary

创建全仓技术债父任务及八个有序子任务；完成后端 pytest PostgreSQL marker 分层、Testcontainers 延迟导入、双入口验证与规范沉淀。

### Git Commits

| Hash | Message |
|------|---------|
| `10f8762` | (see git log) |
| `1fd145f` | (see git log) |

### Status

[OK] **Completed**


## Session 50: 收敛认证 HTTP 客户端

**Date**: 2026-08-22
**Task**: 收敛认证 HTTP 客户端
**Branch**: `main`

### Summary

认证 API 删除独立 fetch/超时/错误解析边界，复用 requestJson/requestRaw；保留刷新令牌与页面提示契约，补齐认证和取消测试并同步前端规范。

### Git Commits

| Hash | Message |
|------|---------|
| `b8deb1e` | (see git log) |

### Status

[OK] **Completed**


## Session 51: Modernize Pydantic v2 configuration

**Date**: 2026-08-22
**Task**: Modernize Pydantic v2 configuration
**Branch**: `main`

### Summary

Migrated deprecated Pydantic validators and class-based schema configs to v2 APIs, added focused contract coverage, synchronized backend quality guidance, and recorded the existing OpenAPI inventory baseline failure.

### Git Commits

| Hash | Message |
|------|---------|
| `8247ca5` | (see git log) |

### Status

[OK] **Completed**


## Session 52: 收敛前端边界类型逃逸

**Date**: 2026-08-22
**Task**: 收敛前端边界类型逃逸
**Branch**: `main`

### Summary

清理前端动态边界中的显式 any，补齐 JSON、metadata、编辑事件和展示读取守卫，并通过类型检查、Scoped ESLint、65 项聚焦测试与 344 项完整单测。

### Git Commits

| Hash | Message |
|------|---------|
| `3926162` | (see git log) |

### Status

[OK] **Completed**


## Session 53: 收敛遗留编辑器组件契约

**Date**: 2026-08-22
**Task**: 收敛遗留编辑器组件契约
**Branch**: `main`

### Summary

迁移七个蓝图编辑相关组件的类型化 props/emits，修复 reactive Proxy 克隆回退并补充保存契约回归测试。

### Git Commits

| Hash | Message |
|------|---------|
| `9d8f7b6` | (see git log) |

### Status

[OK] **Completed**


## Session 54: 审计模型迁移默认值

**Date**: 2026-08-22
**Task**: 审计模型迁移默认值
**Branch**: `main`

### Summary

完成 memory-layer 四表模型、Alembic 与实际 PostgreSQL schema 三方审计，验证临时库生命周期和 ORM 路径，确认无需新增迁移。

### Git Commits

| Hash | Message |
|------|---------|
| `26c68e2` | (see git log) |

### Status

[OK] **Completed**


## Session 55: 删除伏笔提醒死链

**Date**: 2026-08-22
**Task**: 删除伏笔提醒死链
**Branch**: `main`

### Summary

删除 ForeshadowingService 中无生产调用的旧提醒闭环、专属常量与测试，保留活跃 tracker、模型、迁移和列表 API。

### Git Commits

| Hash | Message |
|------|---------|
| `7c99a41` | (see git log) |

### Status

[OK] **Completed**


## Session 56: 删除无引用 base.css 兼容壳

**Date**: 2026-08-22
**Task**: 删除无引用 base.css 兼容壳
**Branch**: `main`

### Summary

删除前端无引用 base.css 兼容壳，同步活跃前端规范；类型检查、347 项单测、lint、生产构建与独立复核通过。

### Git Commits

| Hash | Message |
|------|---------|
| `1ac9cd6` | (see git log) |

### Status

[OK] **Completed**


## Session 57: 全仓技术债治理集成复核

**Date**: 2026-08-22
**Task**: 全仓技术债治理集成复核
**Branch**: `main`

### Summary

完成 8 个技术债子任务的跨任务集成复核并归档父任务；前端四项门禁、后端 Ruff/Pydantic 门禁及计划内回归扫描通过，明确记录两个既有测试基线漂移、passlib crypt 弃用预警与 bundle 软预警。

### Git Commits

| Hash | Message |
|------|---------|
| `4a5d7bf` | (see git log) |

### Status

[OK] **Completed**


## Session 58: 校准 OpenAPI 契约基线

**Date**: 2026-08-22
**Task**: 校准 OpenAPI 契约基线
**Branch**: `main`

### Summary

校准 OpenAPI 库存测试至当前已提交契约，恢复后端快速 profile；导出、前端 API gate 与独立复核通过。

### Main Changes

- 更新 paths、operations 与 operation-id hash 基线

### Git Commits

| Hash | Message |
|------|---------|
| `47af7d8` | (see git log) |

### Testing

- [OK] OpenAPI 目标测试 10 passed；后端快速 profile 468 passed
- [OK] exporter check、前端 api:check、Ruff 与 Trellis validate 通过

### Status

[OK] **Completed**

### Next Steps

- 规划 durable job activity.ambiguous 事件对齐


## Session 59: 校准 durable job 歧义事件测试

**Date**: 2026-08-22
**Task**: 校准 durable job 歧义事件测试
**Branch**: `main`

### Summary

补齐 activity.ambiguous 正式审计事件顺序与公开 payload 边界，恢复完整 PostgreSQL profile。

### Main Changes

- 保留 workflow revision、activity attempt/fencing 与终态断言，新增歧义事件序列和防泄露校验

### Git Commits

| Hash | Message |
|------|---------|
| `50379b1` | (see git log) |

### Testing

- [OK] 聚焦测试 1 passed；durable-job runtime 24 passed
- [OK] PostgreSQL profile 237 passed；Ruff、Trellis validate 与独立复核通过

### Status

[OK] **Completed**

### Next Steps

- 规划移除 passlib crypt 弃用警告


## Session 60: 移除 passlib crypt 弃用依赖

**Date**: 2026-08-22
**Task**: 移除 passlib crypt 弃用依赖
**Branch**: `main`

### Summary

直接使用 bcrypt 4.3，保持既有密码兼容并消除 crypt 弃用预警。

### Git Commits

| Hash | Message |
|------|---------|
| `c83b134` | (see git log) |

### Status

[OK] **Completed**


## Session 61: 收敛前端 bundle 软预警

**Date**: 2026-08-22
**Task**: 收敛前端 bundle 软预警
**Branch**: `main`

### Summary

通过 TipTap 显式扩展和不可达自有 CSS 清理，将 JS 总 gzip 与最大 CSS gzip 降至软线内，并完成全量门禁和浏览器验证。

### Git Commits

| Hash | Message |
|------|---------|
| `c5d1be9` | (see git log) |

### Status

[OK] **Completed**


## Session 62: 完成质量门禁遗留债务治理

**Date**: 2026-08-22
**Task**: 完成质量门禁遗留债务治理
**Branch**: `main`

### Summary

完成四个技术债子任务的跨任务集成复核：后端快速与 PostgreSQL profile、OpenAPI 与弃用门禁、前端完整质量门禁和 bundle 预算均通过，并归档父任务。

### Git Commits

| Hash | Message |
|------|---------|
| `3559f6e` | (see git log) |

### Status

[OK] **Completed**


## Session 63: 完成前端依赖现代化

**Date**: 2026-08-22
**Task**: 完成前端依赖现代化
**Branch**: `main`

### Summary

分四批修复前端依赖漏洞、升级兼容依赖、统一 Node 24 工具链并迁移 Vue Router 5、Pinia 4 与 marked 18；完成完整门禁、浏览器冒烟和父任务集成复核。

### Git Commits

| Hash | Message |
|------|---------|
| `b208300` | (see git log) |
| `fd5aea6` | (see git log) |
| `ed23eee` | (see git log) |
| `029e918` | (see git log) |

### Status

[OK] **Completed**
