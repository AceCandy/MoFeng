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
