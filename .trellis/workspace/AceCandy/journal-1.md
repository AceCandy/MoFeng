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
