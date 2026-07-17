# 工程基线补齐（Alembic/分层门禁/鉴权收敛/并发）

## Goal

前后端工程纪律 + 可靠性补齐。从"单人能跑"过渡到"团队可维护、上线可靠"。前端数据层工业级但执行漂移（分层越界、鉴权重复、无 codegen）；后端缺迁移工具、并发与多进程兼容有坑。

来源：2026-07-12 多专家审查报告（`docs/mofeng-audit-report-2026-07-12.html`）字节前端、快手前端总监、阿里后端、滴滴架构师。

## Requirements

- 后端引入 Alembic，冻结当前 schema 为 baseline 迁移，废弃 `create_all` + 手写 ALTER。
- 章节并发安全：`(project_id, chapter_number)` 唯一约束 + 生成并发限流。
- 验证码/限频、SSE 状态、Celery engine 等"多进程/轮询 DB"问题下沉 Redis / 改 Pub/Sub / 复用 engine。
- 前端分层门禁：ESLint `no-restricted-imports` 禁止组件直连 `@/api` + 前端 CI（type-check/vitest/budget）。
- 鉴权 401 / Authorization 收敛到 `api/http.ts` 单一拦截器。
- 拆巨型组件、乐观更新规范化、删重复逻辑；补 i18n、前端监控、OpenAPI codegen；清 AIMETA。

## 子任务（追踪于会话 TaskList）

- 后端：#15 引入 Alembic；#16 章节并发安全（唯一约束+限流）；#17 验证码/限频下沉 Redis；#18 SSE 改 Pub/Sub + Celery engine 修复；#19 生产部署加固 + 代码卫生。
- 前端：#20 分层门禁 ESLint+CI；#21 鉴权收敛 http 层；#22 拆巨型组件 + 乐观更新规范化 + 删重复；#23 i18n + 监控 + codegen + 清 AIMETA；#24 性能/卫生/测试。

## Acceptance Criteria

- [ ] `alembic upgrade head` 可从空库建到当前 schema；`_ensure_schema_updates` 可废弃。  ⚠️ 实际：alembic baseline a53385d06521 已建(34表)✅；`_ensure_schema_updates`(init_db.py:124)过渡态未废弃(手动ALTER补goals/highlights/character_states等列)，待alembic覆盖后删
- [ ] CI 拦截 components/views 直连 `@/api`；全局 `status === 401` 仅 `http.ts` 一处。  ⚠️ 实际：status===401 已收敛仅 client.ts:8✅；components/views @/api value import 未完全拦截(AppShell.vue:19 TaskAPI value import，type import 预存warning放行)
- [ ] 并发生成同一章不产生重复行；验证码多 worker 一致；SSE 不再每秒查 DB。  ⚠️ 实际：并发 UniqueConstraint+get_or_create✅ / 验证码 Redis 下沉✅；SSE stream_chapter_status(novels.py:307) 仍 sleep(1.0) 轮询查DB，未改事件驱动(待Celery启用)
- [ ] 5 个最大前端组件拆至 <500 行；`cleanVersionContent` 仅 `utils` 一处定义。  ⚠️ 实际：4/5达成(PMR493/CG394/NDS432/WDW498)✅ + cleanVersionContent 去重✅；WritingDesk 619 收口不再抽象(用户决策,非过度抽象空间已穷尽)

## Notes

- 建议排在路线图**阶段一止血 + 阶段二工程化（2-4 周）**。
- 本任务为审查后的**整理产出，未进入实现**。属复杂任务，实现需 `task.py start` 后补 `design.md` / `implement.md`。
- 关联报表：第叁/肆章（前端）、第伍/陆章（后端）、第贰章 P0 看板·工程基线。

## Progress

已完成并落盘：#15 Alembic（`dd7c65e`）/ #16 章节并发唯一约束 / #17 验证码下沉 Redis / #18 Celery engine 复用 / #19 .gitignore / #20 ESLint 分层门禁+CI（`500741d`）/ #21 鉴权收敛 http.ts / #23 OpenAPI codegen / #24 client.spec。验证依据：后端 pytest 191 + 前端 vitest 120。

**#22 按风险切三 slice 推进（见 `design.md` / `implement.md`），任务已 `task.py start`（in_progress）**：
- ✅ **Slice A `cleanVersionContent` 去重**（已完成 + 验证绿）：删 5 处逐字副本（WritingDesk/WDWorkspace/WDVersionDetailModal/VersionSelector/ChapterContent），统一 `import { cleanVersionContent } from '@/utils/chapter'`。5 副本与权威版逐行等价（已比对）。验证：`vue-tsc --noEmit` exit 0 + `vitest run` 120/120 绿（含 uiAuditRegression 34 / wdWorkspaceLockedChapter 10 / chapterDraftFinalizeStatic 8）+ ESLint 0 error（7 warning 均为 pre-existing 分层越界，非本次引入）。diff +5/−204。**Acceptance 第 4 项后半句「cleanVersionContent 仅 utils 一处定义」已达成。**
- ✅ **Slice B** WDWorkspace composable 抽取（4 个全部完成）：`useEditChapterModal`(90 行) / `useVersionResolver`(145 行) / `useAiMenu`(214 行) / `useChapterStatus`(215 行) 已抽出，WDWorkspace 累计 2427→1980 行（−447），vue-tsc/vitest 120 绿 / eslint 0 新增。`useChapterStatus` 边界：`currentComponentProps`（数据装配）留组件，composable 只做「判定+分发」+ return 15 项；清理 5 个 orphan .vue import。
- 🔄 **Slice C** 乐观更新规范化：✅ (a) 删 `upsertChapter` 死代码（novel.ts，零风险）；⏳ (b) 三段式乐观更新（评估完成见 design.md，删除类最适合、生成类不适合，属对外行为增强需补测试，单独会话）。
- 🔄 **Slice D** WDWorkspace template 子组件抽取（2026-07-13 起，Slice B 抽完 composable 后的延续）：✅ 第 1 块 `EditChapterModal`（1980→1844）；✅ 第 2 块 `ChapterEvaluationPanel`——评审面板 template + 4 个纯展示符号（parsedEvaluation/sortedEvaluationEntries/getEvaluationVersionNumber/parseMarkdown）+ marked/DOMPurify import + scoped style 整段迁入子组件（props 收 evaluation/evaluatingChapter，emit evaluateChapter 透传），WDWorkspace 1844→1530（−314），vue-tsc exit 0 / vitest 124 绿（`chapterDraftFinalizeStatic` 测试源码指针已从 WDWorkspace 跟随至 ChapterEvaluationPanel）/ eslint 0 新增（1 pre-existing @/api warning）；✅ 第 3 块 `ChapterVersionsPanel`——历史版本预览 template + 6 个版本预览符号（previewVersionIndex/watch×2/3 computed/selectVersionFromTab/isCurrentVersion）+ scoped style 整段迁入子组件（props 收 availableVersions/selectedChapterNumber/resolvedContent；emit editChapter 透传 + switchToContent 替代 `activeTab='content'`；watch 1 拆分：activeTab 重置留父、previewIndex 重置迁子），WDWorkspace 1530→1380（−150），vue-tsc exit 0 / vitest 124 绿（版本标签指针已从 WDWorkspace 跟随至 ChapterVersionsPanel）/ eslint 0 error（1 新增 type-only @/api warning，与同级 VersionSelector 同型，属已知 P2 分层问题）；✅ 第 4a 块 `ChapterMeta`（WorkspaceHeader 子块 a）——chapter-meta 头部 template（标题/状态印章/inlineMeta/summary）+ Tooltip + scoped style（主块 + @media 响应式覆盖 + 末尾第二处 summary）迁入子组件，props 收 6 项状态（chapterNumber/chapterOutline/statusLabel/statusTone/inlineMeta/titleTooltipText），emit copyTitle/resetTitleTooltip 替代直接调复制（复制逻辑 copyText/copySelectedChapterTitle/resetChapterTitleTooltip 留父，toolbar 复制按钮共用；父 Tooltip orphan import 清理），WDWorkspace 1380→1209（−171），vue-tsc exit 0 / vitest 124 绿 / eslint 0 error（1 新增 type-only @/api warning，同型 P2）；✅ 第 4b 块 `ChapterToolbar`（WorkspaceHeader 子块 b）——toolbar（复制/导出/编辑草稿/确认定稿）+ ai-menu 整块 + useAiMenu 迁入子组件（bodyComponentRef 作 `Ref` prop 直传，isAiMenuDisabled/isChapterContentView computed 包装；emit copyContent/openEditModal/confirmVersionSelection，复制逻辑 copySelectedChapterContent 留父、editModalRef 跨区 emit；closeAiMenu watch(chapterNumber) 拆入子组件；ai-menu-panel 两处定义 + ink-menu-slide keyframes 随迁），WDWorkspace 1209→814（−395），vue-tsc exit 0 / vitest 137 绿（新增 useAiMenu.spec 13 项覆盖 toggle/close/4×handle/export/Escape/Tab/outsideClick，补 codegraph 指出的零测试缺口；`chapterDraftFinalizeStatic` toolbar 契约指针跟随至 ChapterToolbar）/ eslint 0 新增（ChapterToolbar 0 warning，未 import @/api）。WorkspaceHeader 整块抽完，仍 814>500，按 `design.md` 缺口继续找 ~315 行。

> Acceptance 第 4 项前半句「5 大组件 <500 行」维持原文标准，已拆为 parent + 4 child 协同达成（见下「子任务地图」）。

## 子任务地图（2026-07-14 拆分）

Acceptance 第 4 项「5 大组件 <500 行」按组件拆为 parent + 4 child 协同达成（维持原文 <500 标准）：

| 组件 | 行数 | 归属 | 状态 |
|---|---|---|---|
| PersonalModelRouting | 2684 | child `07-14-refactor-personal-model-routing` | planning（无测试，首块前补测试） |
| ChapterGenerating | 2261 | child `07-14-refactor-chapter-generating` | planning（有 `chapterGeneratingTiming` 测试） |
| WritingDesk | 2009 | child `07-14-refactor-writing-desk` | planning |
| NovelDetailShell | 1662 | child `07-14-refactor-novel-detail-shell` | planning（无测试） |
| WDWorkspace | 814 | **parent 直接完成** | in_progress（Slice A/B/C(a)/D(1-3,4a,4b) 已完成，WorkspaceHeader 整块抽完，仍 814>500 需继续找块至 <500） |

- 4 个 child 为 PRD-only lightweight，各自 `task.py start` 前补 `design.md` + `implement.md`。
- WDWorkspace 留 parent：已深度 in_progress（6 commit + 完整 design/implement），迁移无收益；当前 1844 行，Slice D 余 3 块（~863）拆完仍 ~981，需继续找块拆至 <500（见 `design.md`「WDWorkspace 拆至 <500 的缺口」）。
- 跨 child 验收：5 大组件全部 <500 行 + 各自三件套绿 + 行为等价，parent 方可归档。
