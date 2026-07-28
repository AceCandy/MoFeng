# Workspace Index - AceCandy

> Journal tracking for AI development sessions.

---

## Current Status

<!-- @@@auto:current-status -->
- **Active File**: `journal-1.md`
- **Total Sessions**: 24
- **Last Active**: 2026-07-29
<!-- @@@/auto:current-status -->

---

## Active Documents

<!-- @@@auto:active-documents -->
| File | Lines | Status |
|------|-------|--------|
| `journal-1.md` | ~838 | Active |
<!-- @@@/auto:active-documents -->

---

## Session History

<!-- @@@auto:session-history -->
| # | Date | Title | Commits | Branch |
|---|------|-------|---------|--------|
| 24 | 2026-07-29 | 完成可重放章节投影 | `b28be70`, `3a7f203` | `main` |
| 23 | 2026-07-28 | 收敛 durable job 与 event log | `8dbed8e`, `918b151` | `main` |
| 22 | 2026-07-28 | 显式数据库生命周期 | `00afc02`, `afa3c16`, `2f62c06` | `main` |
| 21 | 2026-07-28 | 统一章节上下文契约 | `2516ada`, `edebafb` | `main` |
| 20 | 2026-07-23 | 任务状态提醒 | `017823f` | `main` |
| 19 | 2026-07-23 | 升级 Trellis 至 0.6.8 | `7137108` | `main` |
| 18 | 2026-07-19 | PG 部署配置（compose postgres profile + app POSTGRES_* env + pg-data volume + 两处 env.example） | `31e62e7`, `4e792f5` | `main` |
| 17 | 2026-07-19 | PG 入口层连通 PostgreSQL（DB_PROVIDER=postgresql + asyncpg + alembic upgrade head 建全表） | `540d980`, `c644ee5` | `main` |
| 16 | 2026-07-19 | 修复 memory_layer FK 类型与 DateTime 时区 + PG 迁移立项 | `71df072`, `38f817a` | `main` |
| 15 | 2026-07-17 | L27B 后台任务 SSE 事件驱动 + 工程基线父 task 归档 | `f5b83a3`, `5afaa20` | `main` |
| 14 | 2026-07-17 | L27 SSE 章节状态事件驱动实施 + 真机验证 | `9dc6054`, `5851647` | `main` |
| 13 | 2026-07-17 | #28 main.css 按域拆分（Phase 3 + 真机验证） | `ac12e0e`, `466c17a`, `2dfa37b`, `1a1f136`, `f6165e5`, `b174845`, `b1489ca`, `070490b`, `fe21efb`, `5ce84cf`, `461df24`, `6d3a803`, `1b28862`, `86260e6`, `fa0f2d7`, `33e9882`, `ef3c88c`, `ab49760`, `285ba7d`, `539fd7e`, `a7e0902` | `main` |
| 12 | 2026-07-17 | 前端基线修复 | - | `main` |
| 11 | 2026-07-16 | PersonalModelRouting Slice 14-15 收口 <500 | `589d17a`, `5f3e2c1`, `e825d7a`, `c19c04e` | `main` |
| 10 | 2026-07-16 | WritingDesk 拆分收口（Slice 11-15，2009→619） | `fa9a3ba`, `3ebd274`, `2acc53a`, `0d9c201`, `2f55914` | `main` |
| 9 | 2026-07-16 | NovelDetailShell Slice 10：抽 ShellContent 子组件（达标 <500） | `2ace11b` | `main` |
| 8 | 2026-07-15 | ChapterGenerating 拆分完成（Slice 8-9，2261→394 达成 <500） | `9c86955`, `df9ce7c` | `main` |
| 7 | 2026-07-13 | 朗读变速保调：audio 元素替换 Web Audio 主路径 | `ec98988` | `main` |
| 6 | 2026-07-13 | TTS 朗读语气优化：有声书主播提示词 + 去模型侧变速 | `6e98eef` | `main` |
| 5 | 2026-07-12 | TTS 朗读：回退短段合并为逐段 + 流式评估后弃 | `e831569` | `main` |
| 4 | 2026-07-12 | TTS 朗读：Web Audio 播放 + 短段合并区间高亮 + 后端 wav 标准化 | `8f6e79c`, `6f23c48`, `6d03d62` | `main` |
| 3 | 2026-07-11 | 章节朗读悬浮控件与浏览器首字修复 | `1a8a4c0` | `main` |
| 2 | 2026-07-10 | 修复 pipeline 静态测试 node_key 断言 | `b3924ce` | `main` |
| 1 | 2026-07-10 | 章节朗读与 TTS 模型接入及供应商能力隔离 | `c37ee24`, `07b6442` | `main` |
<!-- @@@/auto:session-history -->

---

## Notes

- Sessions are appended to journal files
- New journal file created when current exceeds 2000 lines
- Use `add_session.py` to record sessions