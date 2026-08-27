# Journal - AceCandy (Part 2)

> Continuation from `journal-1.md` (archived at ~2000 lines)
> Started: 2026-08-25

---



## Session 74: 减少章节页重复请求

**Date**: 2026-08-25
**Task**: 减少章节页重复请求
**Branch**: `main`

### Summary

修复项目缓存前缀失效、首次工作流与任务快照重复刷新；SSE 在线暂停轮询且断线回退；延迟 TTS 配置并跳过无变化创作上下文写入。完整前端单测、类型检查和 lint 均通过。

### Git Commits

| Hash | Message |
|------|---------|
| `782c5e4` | (see git log) |

### Status

[OK] **Completed**


## Session 75: 优化写作台章节导航

**Date**: 2026-08-25
**Task**: 优化写作台章节导航
**Branch**: `main`

### Summary

重构章节导航层级与状态样式，固定底部生成操作，完善桌面和窄屏删除入口；类型检查、Lint、55项测试及浏览器验收通过。

### Git Commits

| Hash | Message |
|------|---------|
| `5ef97f3` | (see git log) |

### Status

[OK] **Completed**


## Session 76: 优化写作台加载与紧凑操作

**Date**: 2026-08-26
**Task**: 优化写作台加载与紧凑操作
**Branch**: `main`

### Summary

为项目详情增加轻量章节载荷并按章补取正文，收敛写作台工具栏与朗读控件，保留未定稿状态的辅助面板入口；前端契约、类型、Lint、392 项单测、构建预算及双视口 E2E 验证通过。

### Git Commits

| Hash | Message |
|------|---------|
| `03f11b3` | (see git log) |

### Status

[OK] **Completed**


## Session 77: 精简写作台章节侧栏

**Date**: 2026-08-26
**Task**: 精简写作台章节侧栏
**Branch**: `main`

### Summary

收紧章节号与标题间距，缩小搜索框并移除跳转按钮，删除入口改为纯图标；定向测试、ESLint、类型检查与界面审计通过。

### Git Commits

| Hash | Message |
|------|---------|
| `5810032` | (see git log) |

### Status

[OK] **Completed**


## Session 78: 优化登录页视觉层次

**Date**: 2026-08-27
**Task**: 优化登录页视觉层次
**Branch**: `main`

### Summary

调整登录页群青分舞台、品牌文字层级与流程栏收口，并完成桌面、移动端、无障碍及前端质量验证。

### Git Commits

| Hash | Message |
|------|---------|
| `198d41f` | (see git log) |

### Status

[OK] **Completed**
