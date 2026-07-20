# MoFeng 代码库治理审计报告

> 日期：2026-07-19 ｜ 方法：6 模块并行审查 + 每条发现独立对抗验证过滤误报
> 审查范围：backend（api/services/data/core-config-utils）+ frontend 全量 + 配置/文件/文档

## 概览

- **确认发现**：49 条（high 5 / medium 25 / low 19）
- **误报剔除**：12 条（对抗验证判定为理论风险/误读代码/已被 .gitignore 覆盖/正常框架行为）
- **按模块**：{'backend-api': 8, 'backend-core-config-utils': 7, 'config-files': 5, 'backend-services': 11, 'backend-data': 8, 'frontend': 10}
- **按类别**：{'security': 7, 'unused-file': 3, 'risk': 22, 'dead-code': 12, 'deprecated-config': 5}

## P0 实施状态（2026-07-20）

H1-H5 全部实施完成，独立复核通过（基于真实磁盘代码 + codegraph/rg 交叉验证），后端全量 pytest 229 passed + 前端四件套（vue-tsc/vitest 154 tests/eslint/build）全绿。

| H | 状态 | commit | 验证 |
|---|---|---|---|
| H1 foreshadowing IDOR 越权 | ✅ | 48a3fd3 | test_foreshadowing_router 越权 404 + owner 正常 |
| H2 analytics_enhanced 删除 | ✅ | 1963d61 | import 验证 + rg 无残留 |
| H3 默认管理员密码 | ✅ | 68e8eff | test_config_security 5 测试（默认/弱/短/强/非生产）|
| H4 finalize 静默损坏 | ✅ | cbbb76f | test_finalize 4 测试（含全失败不写快照/部分 partial_success）|
| H5 consistency async 500 | ✅ | 68b8d58 | test_consistency 2 测试（_get_check_context + 端到端）|

**新发现（P2 候选，H5 范围外）**：`knowledge_retrieval_service.py` 与 H5 同类 MissingGreenlet 风险--async 方法（`retrieve_and_filter`/`get_chapter_context`/`_get_recent_chapter_summaries` 等）内部 6 处 `self.db.query`（同步，:221/:271/:382/:565/:587/:611），经 `pipeline_orchestrator.py:1888` 传 `sync_session` 调用。`/api/review/consistency` 已修（H5），但两层 RAG 链路的 KnowledgeRetrievalService 未修；retrieve_and_filter 在 pipeline_orchestrator:1882 的 try/except 外（该 try 只包 VectorStoreService 初始化），MissingGreenlet 会传播，可能导致两层 RAG 静默降级或生成流程异常。P2 risk-harden 时按 H5 同模式修复（self.db.query -> await self.session.execute(select)）。

## P2 实施状态（2026-07-20）

medium 25 项 + KRService async（新发现）全部处置完成（16 项真做 + 2 项决策不删 + 1 项 CSP 决策不加 + 8 项 P1 已处理）。独立复核通过，后端 pytest 226 passed + alembic upgrade/downgrade 往返 + 前端四件套全绿。

| 项 | 状态 | commit | 说明 |
|---|---|---|---|
| M2 writer generate_chapter 归校 | ✅ | 28cfebd | ensure_project_owner OUTSIDE try |
| M3/M10 SSRF DNS rebinding | ✅ | 1172e0c | 解析失败 fail-closed raise |
| M4 6 索引 | ✅ | 45b6cfc | alembic 迁移 17a89f18291c |
| M5 RAG FK/长度 | ✅ | 45b6cfc | String(36) + FK ondelete CASCADE |
| M6 LLMConfig legacy 字段 | ⏸ 决策不删 | - | schemas/routers/llm_service 在用，非死字段 |
| M7 伏笔级联统一 | ✅ | 45b6cfc | resolved_at_chapter_id CASCADE->SET NULL |
| M9 alembic compare_type | ✅ | 45b6cfc | env.py compare_type/compare_server_default |
| M11 openai 死配置 | ⏸ 决策不删 | - | system_config_defaults 种子链路在用 |
| M17 nginx 安全头 | ✅ | f64db88 | X-Frame-Options/X-Content-Type-Options/Referrer-Policy/HSTS |
| M18 nginx 缓存 | ✅ | f64db88 | JS/CSS no-store -> immutable long-cache |
| M19 AsyncOpenAI close | ✅ | 58ca7cd | LLMClient.aclose + 4 处 finally close |
| M20 import 大小限制 | ✅ | 28cfebd | 10MB 限制抛 413 |
| M21 usage 原子 | ✅ | c948e87 | increment_atomic + 独立 session |
| M22 consistency 质量门 | ✅ | c948e87 | is_consistent=False 不放行 |
| M23 vector re-raise | ✅ | c948e87 | upsert 失败 re-raise |
| M24 auth linuxdo SSRF | ✅ | 1172e0c | token_url/user_info_url 校验 + data.get |
| KRService async（新发现） | ✅ | 263c761 | 6 处 query + _get_chapter_blueprint async |
| CSP | ⏸ 决策不加 | - | 需前端浏览器测试评估，P3 或单独 task |
| M1/M8/M12/M13/M14/M15/M16/M25 | ✅ P1 已处理 | - | dead-code 类，P1 删除/确认误报 |

## 治理分批建议

### P0 — 安全与数据完整性（立即修，hotfix 级）
- H1 foreshadowing 6 端点 IDOR 越权（读他人伏笔 + 跨项目篡改状态）
- H3 默认管理员密码 `ChangeMe123!` 三处硬编码 + 3 处泄露
- H4 `finalize_chapter` 静默数据损坏（success=True 但记忆/状态/快照全空）+ 连接池独占
- H5 `consistency_service` async 用 sync Session.query -> `/api/review/consistency` 必 500
- H2 `analytics_enhanced.py` 删除（509 行死文件 + import 不存在模块，注册即崩）

### P1 — 死代码清理（批量删除，低风险高收益）
- 6 个死 service 文件：emotion_service / emotion_curve_service / cache_service / chapter_review_service / admin_setting_service / blueprint_service
- 前端死链路：LLMSettings.vue(1027行)+legacy 配置查询、WorkspaceEntry.vue(603行)+updates 公开日志链路、WDHeader.vue(224行)、api/version.ts(136行)、chartLine.ts+chart.js 依赖、TypewriterEffect.vue、@fontsource/noto-sans-sc 依赖、gen:api 脚本+openapi-typescript
- backend 死路由：foreshadowing 5 个前端无调用端点、updates/remote-version
- 死配置/死提示词：LLMConfig 7 个 legacy 字段、openai_api_key 等系统配置种子、character_dna_guide.md
- 入仓清理：.dev-servers.json（运行态）、check_db.py（调试脚本）、goal-1/（已 git rm 待提交）

### P2 — 风险加固（中风险，分批修）
- SSRF DNS rebinding（core/ssrf.py 解析失败放行 + 独立二次解析，2 条）
- 缺索引（6 处高频 FK 列）+ RAG 表 project_id 无 FK 孤儿数据 + 伏笔回收级联不对称
- alembic 未启用 compare_type/compare_server_default（漏检类型漂移）
- AsyncOpenAI 客户端三处未 close（连接池泄漏）
- import 文件无大小限制（OOM）
- usage_service 非原子计数 + 共享 session commit 污染调用方事务
- consistency_check 异常返回 is_consistent=True（质量门静默放行）
- vector_store upsert 失败仅日志不 re-raise（与 delete 行为不一致）
- auth linuxdo callback SSRF（向管理员配置 URL 发请求无校验）
- nginx 缺安全响应头 + 哈希资产强制 no-store 损害缓存
- writer generate_chapter 未显式校验归属 + assert_production_security 未校验 debug=False

### P3 — 小项（low，择机）
- debug 默认 True、datetime.utcnow 改 timezone.utc、memory_layer 时间戳 nullable、ProjectMemory.version 乐观锁未生效、analytics.py 情感分析函数复制分叉、append_conversation seq 并发、AppShell matchMedia 监听泄漏 等

---

## High 详述与修法

### H1 [security] backend/app/api/routers/foreshadowing.py:84
**模块**：backend-api
**问题**：foreshadowing 路由全部 6 个端点未校验项目归属，登录用户可越权读写任意他人项目的伏笔/提醒/分析（IDOR）

**详情**：foreshadowing.py 的全部 6 个端点（create/list/resolve/reminders/dismiss/analysis）只依赖 get_current_user 校验登录态，均未调用 novel_service.ensure_project_owner(project_id, current_user.id)。ForeshadowingService 内部所有方法（create_foreshadowing/get_foreshadowings/resolve_foreshadowing/get_active_reminders/dismiss_reminder/analyze_foreshadowings）也完全不接收 user_id 参数，纯按 project_id/foreshadowing_id/reminder_id 操作数据库。这是上轮审计『越权 403->404』（service 层 ensure_project_owner 统一）的明显遗漏路径。其中 list_foreshadowings 前端在用（src/api/novel.ts:698 `${NOVELS_BASE}/${projectId}/foreshadowings?limit=500`），意味着任意登录用户枚举他人 project_id 即可读取对方全部伏笔内容；resolve_foreshadowing/dismiss_reminder 直接按 id 操作，连路径里的 project_id 都未参与校验，可跨项目篡改任意伏笔/提醒状态。

**修法**：
1. 先确认 foreshadowing 功能启用状态——`list` 端点前端 `novel.ts:698` 在用，说明部分启用；但 celery 未集成，emotion/foreshadowing 生成链路整体未启用。
2. 5 个前端无调用的死端点（create/resolve/reminders/dismiss/analysis）直接删除（归入 P1 死代码）。
3. 保留的 `list_foreshadowings` 端点补 `await novel_service.ensure_project_owner(project_id, current_user.id)`，越权统一抛 404（与审计 #14 一致）。
4. `ForeshadowingService` 方法补 user_id 参数，或在路由层先校验归属再调用 service。
5. 若确认整块未启用，可整块删除，但需先确认 list 端点是否真在用。

<details><summary>验证依据</summary>

```
发现属实，是一处真实的 IDOR 越权漏洞，且是上轮审计「越权 403->404 / service 层 ensure_project_owner 统一」的明确遗漏路径。

已核查的证据链：
1. foreshadowing.py 全部 6 个端点（create/list/resolve/reminders/dismiss/analysis）签名仅有 `current_user = Depends(get_current_user)`，未调用任何项目归属校验。get_current_user (core/dependencies.py:15-28) 只做 token 解析+取用户，不做项目归属判断。
2. ensure_project_owner 是项目标准模式（novel_service.py:200-207，越权统一抛 404，注释明确标注「审计 #14」），全仓 33 处调用（projects.py/review.py/novels.py/optimizer.py/writer.py + 多个 service），唯独 foreshadowing 路由与 ForeshadowingService 完全缺失等价校验。
3. ForeshadowingService 所有方法均不接收 user_id（rg 'user_id|ensure_project_owner|owner' foreshadowing_service.py 无任何匹配），create_foreshadowing/get_foreshadowings/get_active_reminders/analyze_foreshadowings 纯按 project_id 查询；resolve_foreshadowing(foreshadowing_id,...) 直接 session.get(Foreshadowing, foreshadowing_id)（service.py:101），dismiss_reminder(reminder_id,...) 直接 session.get(ForeshadowingReminder, reminder_id)（service.py:202）——路径里的 project_id 参数在这两个端点中完全未参与校验，可跨项目篡改任意伏笔/提醒状态。
4. 路由已注册且活跃：routers/__init__.py:14 `api_router.include_router(foreshadowing.router)` → main.py:95 `app.include_router(api_router)`，非死代码。
5. 前端在用：frontend/src/api/novel.ts:698 `${NOVELS_BASE}/${projectId}/fore
```

</details>

### H2 [unused-file] backend/app/api/routers/analytics_enhanced.py:18
**模块**：backend-core-config-utils
**问题**：analytics_enhanced.py 整文件为死路由且已损坏：未在 routers/__init__.py 注册，且 import 三个不存在的 service 模块

**详情**：该路由文件定义了 APIRouter 与 6 个端点，但 backend/app/api/routers/__init__.py 的 include_router 列表（auth/novels/writer/admin/updates/llm_config/optimizer/analytics/foreshadowing/projects/review/tasks/tts）从未包含 analytics_enhanced，全仓 rg 也无任何 `import analytics_enhanced`。更严重的是文件顶部 from ...services.emotion_analyzer_enhanced / story_trajectory_analyzer / creative_guidance_system 导入的三个模块在 app/services/ 下根本不存在（ls 确认只有 emotion_curve_service.py 与 emotion_service.py）。因此这 509 行不仅是死代码，且一旦被人加入 __init__ 会直接 ImportError 崩溃。整文件应删除。

**修法**：整文件删除（509 行）。未在 `routers/__init__.py` 注册、全仓零引用、import 三个不存在的 service 模块（`emotion_analyzer_enhanced`/`story_trajectory_analyzer`/`creative_guidance_system`）。保留无价值，且一旦被人注册即 ImportError 启动崩溃。

<details><summary>验证依据</summary>

```
发现真实，已通过多重独立核实确认。1) 文件确实存在且为 509 行（wc -l 确认）。2) backend/app/api/routers/__init__.py 第 3 行 import 与第 6-18 行 include_router 列表均无 analytics_enhanced（直接 Read 确认），只有普通 analytics。3) 全仓无引用：rg "analytics_enhanced" 与 git grep 均返回 exit 1（无匹配），git ls-files 仅返回文件自身；文件内容甚至不含 "analytics_enhanced" 字符串，证明无任何 import/动态加载/测试引用。4) 三个被导入 service 模块确实不存在：ls app/services/ 中 emotion|story|creative 仅匹配 emotion_curve_service.py、emotion_service.py；emotion_analyzer_enhanced / story_trajectory_analyzer / creative_guidance_system 全部缺失。5) 三个被导入符号全仓仅自引用：rg 搜索 analyze_multidimensional_emotion|analyze_story_trajectory|generate_creative_guidance 仅在 analytics_enhanced.py 自身（行 18-20、195、292、392）出现，无外部定义或调用方。无任何缓解措施：文件既未注册也无引用，且 import 三个不存在的模块——一旦被人加入 __init__.py 会立即 ImportError 导致应用启动崩溃。属高价值清理项（死代码 + 已损坏 + 误导读者 + 潜在引爆点），severity=high 合理，无需修正。
```

</details>

### H3 [security] deploy/.env.example:77
**模块**：config-files
**问题**：默认管理员密码 ChangeMe123! 在 .env.example 模板里直接写出字面值，并经 docker-compose.yml 与 config.py 三重兜底，未设环境变量即以已知弱口令上线

**详情**：默认管理员密码在三处同时硬编码为 ChangeMe123!：(1) deploy/.env.example:77 作为模板直接写出该值（而非 your-password-change-me 这类占位符），用户照抄 .env.example 即得到已知弱口令；(2) deploy/docker-compose.yml:23 用 ${ADMIN_DEFAULT_PASSWORD:-ChangeMe123!} 给出兜底默认值，且未像 SECRET_KEY/POSTGRES_PASSWORD 那样用 :? 强制要求设置；(3) backend/app/core/config.py:71 Field(default="ChangeMe123!") 是代码层兜底。三者叠加导致首次部署若漏配环境变量，系统会用已知口令初始化管理员账号，构成默认凭据风险。

**修法**（默认管理员密码 `ChangeMe123!` 三处硬编码 + 3 处泄露点）：
1. `deploy/.env.example:77` 改占位符 `ADMIN_DEFAULT_PASSWORD=your-admin-password-change-me`。
2. `deploy/docker-compose.yml:23` 改强制 `${ADMIN_DEFAULT_PASSWORD:?ADMIN_DEFAULT_PASSWORD must be set}`（与 SECRET_KEY/POSTGRES_PASSWORD 一致）。
3. `backend/app/core/config.py:71` 去掉 `default="ChangeMe123!"`，或在 `assert_production_security` 里校验非默认值（扩展现有 `_WEAK_SECRET_KEYS` 机制到 admin_default_password）。
4. 同步清理泄露点：`backend/env.example:37`、`deploy/scripts/deploy_docker.sh:155`、`docs/DEPLOYMENT.md:223`。

<details><summary>验证依据</summary>

```
发现属实，三处硬编码均已核实：

1. deploy/.env.example:77 直接写出字面值 ADMIN_DEFAULT_PASSWORD=ChangeMe123!，且与同文件其他敏感字段形成鲜明对比——SECRET_KEY(第25行)用 your-secret-key-change-me-to-random-string、POSTGRES_PASSWORD(第60行)用 your-database-password-change-me 占位符，唯独此字段给出真实可用口令。用户照抄 .env.example 即得到已知弱口令。

2. deploy/docker-compose.yml:23 用 ${ADMIN_DEFAULT_PASSWORD:-ChangeMe123!}（:- 兜底默认值），而 SECRET_KEY(第11行)、POSTGRES_PASSWORD(第19、75行)均用 :? 强制必填。对比成立——漏配此变量不会报错而是静默使用弱口令。

3. backend/app/core/config.py:71 admin_default_password: str = Field(default="ChangeMe123!") 是代码层兜底。

攻击路径已确认可行：backend/app/db/init_db.py:51 在首次启动且无管理员时，用 hash_password(settings.admin_default_password) 创建管理员，即已知口令直接生效。

缓解措施存在但不充分：auth_service.py:425-431 的 requires_password_reset() 仅在管理员登录后才触发强制改密，change_password()(第444-445行)只禁止把新密码改回默认字面值。这留下「首次启动到管理员首次登录」之间的窗口期，攻击者可先用公开的默认口令登录并改为自己的口令（检查只拦默认字面值，不拦攻击者自定口令），从而接管管理员。config.py:235 的 assert_production_security() 只校验 secret_key——_WEAK_SECRET_KEYS(第228行)虽含 ChangeMe123!，却从未用于校验 admin_default_password，启动时无任何拦截。

补充：还有 backend/env.example:37、deploy/scripts/deploy_docker.sh:155、docs/DEPLOYMENT.md:223 同样泄露该值，进一步扩大暴露面。

此问题不在任务简报「已修项」清单内（清单列出的已修项不含默认口令），不构成重复报告。严重度 high 恰当（CWE-798/1392 默认凭据，面向公网部署即成立）。
```

</details>

### H4 [risk] backend/app/services/finalize_service.py:158
**模块**：backend-services
**问题**：finalize_chapter 持有 DB 会话跨多次 LLM 调用且 LLM 异常被静默吞掉，导致定稿可标 success=True 但记忆/状态/快照全为空

**详情**：finalize_chapter 在单个 try 块内串行调用 5 次长耗时 LLM（_update_global_summary、_update_character_state、_update_plot_arcs、_generate_chapter_summary，每次 timeout 默认 180-300s），全部跑完才执行 await self.db.commit()。这意味着：(1) 整个定稿流程期间（典型 2-5 分钟，最长可近 10 分钟）一个数据库连接被独占持有，连接池在高并发定稿时极易耗尽，新请求阻塞。(2) 内层 _update_global_summary/_update_character_state/_update_plot_arcs/_generate_chapter_summary 都用 `except Exception: return None` 吞掉 LLMService 抛出的 HTTPException(503 超时/502 网关)，导致章节快照写入 global_summary=None、character_states=None、plot_arcs=None，但外层仍走 `await self.db.commit()` 并把 result['success'] 置为 True。最终前端拿到 success=True，但章节记忆/状态/伏笔全部为空，且无任何告警。

**修法**（静默数据损坏 + 连接池独占）：
1. LLM 调用期间不持有 DB 写事务：先完成必要的 DB 读/写并 commit 释放，LLM 调用用独立短生命周期 session，或 LLM 结果拿到后再开事务写入快照。
2. 内层 `_update_*` 的 `except Exception: return None` 不要静默：要么 re-raise 让外层标 `success=False`，要么记录部分失败但 result 明确反映哪些未更新。
3. `success=True` 必须保证核心字段（global_summary/character_states/plot_arcs/chapter_summary）已写入，否则前端误导用户以为定稿成功。
4. 缩短 DB session 持有时间，避免高并发定稿时连接池（默认 5+10=15）耗尽。

<details><summary>验证依据</summary>

```
已逐项核实,发现真实。

1. DB session 跨多次 LLM 调用独占持有:finalize_service.py:187-256 的 try 块内串行调用 4 次 LLM(_update_global_summary L192、_update_character_state L203、_update_plot_arcs L213、_generate_chapter_summary L233),L256 才 await self.db.commit()。LLMService.generate 默认 timeout=300.0(llm_service.py:374),最坏 ~20 分钟。该 session 即 FastAPI 请求 session(writer.py:1036 FinalizeService(session,...) 来自 Depends(get_session)),engine(session.py:9-14)未显式设 pool_size/max_overflow,SQLAlchemy QueuePool 默认 5+10=15,长连接独占下高并发定稿确有连接池耗尽风险。

2. LLM 异常被静默吞掉:4 个 helper 均用 `except Exception` 捕获并 return None(L302-313、L365-376、L481-501、L535-545)。LLMService.generate 在超时/网关错误时 raise HTTPException(503)(llm_service.py:171/187/198/209),HTTPException 继承 Exception 故被吞掉。

3. success=True 但记忆/状态/快照为空:result["success"] 在 L182 初始化为 True,内层吞异常后外层 except(L259-263)永不触发,success 保持 True。L256 commit 照常执行。L238-246 创建快照时:new_summary=None(用 fallback project_memory.global_summary,可能为空)、new_state=None(L562 `character_states_snapshot={"raw_text":character_states} if character_states else None` 写 None)、new_plot_arcs=None(fallback 可能空 {})、chapter_summary=None。快照被创建但核心字段为空。

4. 调用方无兜底:_confirm_finalize_chapter_sync(writer.py:1037-1049)仅检查 finalize_resul
```

</details>

### H5 [risk] backend/app/services/consistency_service.py:347
**模块**：backend-services
**问题**：ConsistencyService 在 async 路径用 sync Session.query 阻塞事件循环

**详情**：调用方用 `sync_session = getattr(self.session, 'sync_session', self.session)` 拿到 AsyncSession 的底层 sync Session，然后 _get_check_context 内全部用 `self.db.query(...).first()/.all()` 同步 API 查询 4 张表（NovelBlueprint、ProjectMemory、CharacterState、Foreshadowing）。这些同步调用在 async 路径上直接阻塞事件循环；sync_session 与 async session 共享同一连接，混用还可能触发事务状态混乱。pipeline 一章生成会调用一次，高并发时事件循环被多次短暂卡顿累计放大。正确做法是把 query 改写为 `await self.session.execute(select(...))`。

**修法**（async 路径用 sync Session.query -> MissingGreenlet -> `/api/review/consistency` 必 500）：
1. `_get_check_context` 的 4 处 `self.db.query(...).first()/.all()` 改写为 `await self.session.execute(select(...))` + `.scalars().first()/.all()`。
2. 或整个同步查询块包 `await self.session.run_sync(...)`。
3. 加 `POST /api/review/consistency` 路由集成测试（当前无覆盖，CI 未捕获此 500）。
4. 注意：pipeline 的 `_run_consistency_check` 默认 `enable_consistency=False` 不触发，但 `review.py:69` 公开路由每次必 500。

<details><summary>验证依据</summary>

```
代码缺陷真实存在，但发现对「影响机制」的描述有误，且实际后果比所述更严重。

【已核实的事实】
1. consistency_service.py:347-401 的 `_get_check_context` 确实用同步 `self.db.query(...)` 查 4 张表（NovelBlueprint/ProjectMemory/CharacterState/Foreshadowing），方法虽声明 `async def` 但内部无任何 `await`/`run_sync`，是「假异步」。
2. `self.db` 来源已确认：两处调用方 pipeline_orchestrator.py:3162 与 review.py:78 均用 `sync_session = getattr(session, "sync_session", session)` 从 AsyncSession 取底层 sync Session 后传入。pipeline_orchestrator 的 session 类型在 191-192 行明确为 `AsyncSession`；review.py:72 为 `session: AsyncSession = Depends(get_session)`。
3. db/session.py 确认全库仅 `create_async_engine`(asyncpg)，无任何同步 engine/session 回退；get_session 只 yield AsyncSession。
4. 实测验证：用 aiosqlite async engine 复现，`sync_session.query(Model).first()` 直接调用（未包 `await session.run_sync(...)`）抛出 `sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called`。该错误源自 SQLAlchemy 异步层（await_only），与驱动无关，asyncpg 下同样会抛。

【发现描述错误之处】
- 发现称「直接阻塞事件循环」「sync_session 与 async session 共享同一连接，混用还可能触发事务状态混乱」——这是误判。实际行为不是阻塞，而是立即抛 MissingGreenlet 运行时异常，根本不会执行到 I/O，更无「事务状态混乱」。
- 发现称 pipeline「一章生成会调用一次」——不准确。pipeline 的 `_run_consistency_check` 受 `enable_consistency` 控制，默认 False，且 ultimate preset 强制 False；只有用户显式开启才会触发。真正必然触发的是 review.py:
```

</details>

---

## Medium 清单

| # | 位置 | 类别 | 问题 |
|---|---|---|---|
| 1 | backend/app/api/routers/foreshadowing.py:83 | dead-code | foreshadowing 路由 5 个端点（create/resolve/reminders/dismiss/analysis）前端无调用，属死路由且叠加越权 |
| 2 | backend/app/api/routers/writer.py:1264 | risk | generate_chapter 路由层未显式校验 ensure_project_owner，依赖 orchestrator 内部防护 |
| 3 | backend/app/core/ssrf.py:39 | security | assert_safe_base_url 在 DNS 解析失败时直接放行，存在 DNS rebinding 绕过 SSRF 防护的风险 |
| 4 | backend/alembic/versions/a53385d06521_baseline.py:161 | risk | selectinload 高频加载的 FK 列缺失索引：chapter_versions.chapter_id、chapter_evaluations.chapter_id、blueprint_characters.project_id、blueprint_relationships.project_id、chapter_outlines.project_id、novel_conversations.project_id |
| 5 | backend/app/models/rag.py:29 | risk | RAG 表 project_id 无 FK 且长度 String(64) 与 novel_projects.id String(36) 不一致，删项目产生孤儿向量数据 |
| 6 | backend/app/models/llm_config.py:14 | deprecated-config | LLMConfig 表 llm_provider_*/embedding_provider_* 共 7 个字段在运行期已无读取方，仅 API 写回 legacy 展示 |
| 7 | backend/app/models/foreshadowing.py:35 | risk | 伏笔回收章节级联不对称：foreshadowings.resolved_chapter_id=SET NULL 而 foreshadowing_resolutions.resolved_at_chapter_id=CASCADE |
| 8 | backend/app/services/blueprint_service.py:17 | dead-code | BlueprintService 使用同步 Session API 且全仓库无实例化，与 async 架构不兼容的死代码 |
| 9 | backend/alembic/env.py:39 | risk | alembic env.py 未启用 compare_type/compare_server_default，autogenerate 漏检类型与默认值漂移 |
| 10 | backend/app/core/ssrf.py:38 | risk | SSRF 校验与实际请求分别独立 DNS 解析，存在 DNS rebinding 绕过；且 allow_loopback 默认始终放行 |
| 11 | backend/app/core/config.py:75 | deprecated-config | openai_api_key/openai_base_url/openai_model_name 配置 + llm.api_key/llm.base_url/llm.model 系统配置种子 + LLMService._get_config_value 全链路无消费者（与已清理的 embedding 死配置同构） |
| 12 | backend/app/services/emotion_service.py:12 | dead-code | EmotionService 整类零调用方，连带 utils/emotion_analyzer.py 仅被它 import，二者均为死代码 |
| 13 | frontend/src/components/LLMSettings.vue:1 | dead-code | LLMSettings.vue(1027 行)及配套 legacy LLM 配置查询/接口函数整条链路无任何引用,属于死代码 |
| 14 | frontend/src/views/WorkspaceEntry.vue:1 | dead-code | WorkspaceEntry.vue(603 行)未在 router 注册(/ 已改为 redirect 到 /workspace 用 NovelWorkspace.vue),连带 queries/updates.ts、api/updates.ts 整条公开更新日志链路全部死代码 |
| 15 | frontend/src/components/writing-desk/WDHeader.vue:1 | dead-code | WDHeader.vue(224 行)零引用,写作台头部已改用 AppShell 顶栏 + WDProjectStatus |
| 16 | frontend/src/api/version.ts:81 | dead-code | api/version.ts(136 行,含 getRemoteVersion + RemoteVersionDebugEvent 调试机制)无任何 import,远程版本检查已被 queries/admin.ts 内联实现取代 |
| 17 | deploy/nginx.conf:1 | security | 生产 nginx.conf 缺少 X-Frame-Options/X-Content-Type-Options/CSP/HSTS/Referrer-Policy 等安全响应头 |
| 18 | deploy/nginx.conf:50 | risk | 生产 nginx 对所有 .js/.css 强制 no-store，Vite 哈希资产无法被浏览器长缓存，性能受损 |
| 19 | backend/app/services/llm_service.py:857 | risk | AsyncOpenAI 客户端在三处实例化后从未 close，连接池泄漏可致 fd/连接耗尽 |
| 20 | backend/app/services/import_service.py:157 | risk | import_novel_from_file 用 await file.read() 一次性读全文且无任何大小限制，可被超大文件 OOM |
| 21 | backend/app/services/usage_service.py:14 | risk | UsageService.increment 非原子读改写且在共享 session 上 commit，污染调用方事务并丢失并发计数 |
| 22 | backend/app/services/consistency_service.py:213 | risk | consistency_check 异常时返回 is_consistent=True，质量门在 LLM 失败时静默放行 |
| 23 | backend/app/services/vector_store_service.py:186 | risk | upsert_chunks/upsert_summaries 写失败仅日志不 re-raise，调用方无感知；与 delete_by_chapters 的 re-raise 行为不一致 |
| 24 | backend/app/services/auth_service.py:337 | security | handle_linuxdo_callback 向管理员配置的 token_url/user_info_url 发起服务端请求且未做 SSRF 校验，data['id']/['username'] 直接下标访问 |
| 25 | backend/app/services/emotion_service.py:12 | unused-file | 六个 service 文件为完全死代码（无任何导入引用）：emotion_service.py、emotion_curve_service.py、cache_service.py、chapter_review_service.py、admin_setting_service.py、blueprint_service.py |

## Low 清单

| # | 位置 | 类别 | 问题 |
|---|---|---|---|
| 1 | backend/app/api/routers/updates.py:121 | security | /api/updates/remote-version 未鉴权且服务端外部请求无 SSRF 防护 |
| 2 | backend/app/api/routers/analytics_enhanced.py:127 | unused-file | analytics_enhanced.py 整个文件 5 个端点前端与后端均无调用，属死路由 |
| 3 | backend/app/core/config.py:235 | risk | assert_production_security 未校验生产环境 debug=False，debug 默认 True 可能暴露错误栈 |
| 4 | backend/app/api/routers/optimizer.py:397 | risk | apply_optimization 同时接受 body 和 query 参数，optimized_content 可经 query 传入大文本 |
| 5 | backend/app/models/memory_layer.py:83 | risk | memory_layer 4 表 created_at/updated_at 仍 nullable=True 且无 server_default，模型用已弃用的 datetime.utcnow Python 端默认 |
| 6 | backend/app/models/project_memory.py:61 | risk | ProjectMemory.version 注释称用于乐观锁，实际只自增、从无 WHERE version=? 守卫 |
| 7 | backend/app/core/config.py:16 | security | debug 默认 True 且 assert_production_security 不强制生产关闭 debug，导致 FastAPI 调试模式 + SQLAlchemy echo(SQL 含参数) 在生产泄漏 |
| 8 | backend/app/api/routers/analytics.py:72 | risk | analytics.py 本地复制了 emotion_analyzer 的情感分析函数，且两份关键词表已分叉，修一处不会同步另一处 |
| 9 | backend/prompts/character_dna_guide.md:1 | dead-code | character_dna_guide.md 被 init_db 灌入 DB 但全仓无任何 get_prompt 引用，是死提示词 |
| 10 | frontend/src/lib/chartLine.ts:14 | dead-code | chartLine.ts 零引用(仅被一条断言它不该被引入的回归测试提到),连带 chart.js 依赖与 vite.config.ts 的 chart-tools 手动分包全部失效 |
| 11 | frontend/package.json:20 | deprecated-config | gen:api 脚本 + openapi-typescript devDep 配置了 OpenAPI 类型生成管线,但产物 schema.d.ts 从未提交也无人 import,实际类型全手写 |
| 12 | frontend/src/components/TypewriterEffect.vue:17 | dead-code | TypewriterEffect.vue 仅被自身回归测试引用,无业务代码使用,且实现已退化为 displayedText=props.text 无动画效果 |
| 13 | frontend/package.json:24 | deprecated-config | @fontsource/noto-sans-sc 依赖从未被 import(回归测试还显式断言 main.ts 不引入它),全站字体走 noto-serif-sc |
| 14 | frontend/src/stores/novel.ts:6 | dead-code | novel store 的 currentConversationState / resetConversationState 从未被外部访问,InspirationMode.vue 用的是本地 ref |
| 15 | frontend/src/components/shared/AppShell.vue:282 | risk | AppShell.vue 在 onMounted 注册 matchMedia('change') 监听但 onUnmounted 未移除,登出再登录会重复挂载导致监听器累积泄漏 |
| 16 | .dev-servers.json:2 | risk | .dev-servers.json 是 dev_servers.py 写出的本地运行态（PID/端口/启动时间），却被 git 追踪入仓 |
| 17 | check_db.py:8 | dead-code | check_db.py 是硬编码“查询第6章”的一次性调试脚本，全仓零引用却被追踪入仓 |
| 18 | backend/app/services/novel_service.py:342 | risk | append_conversation 用 select(max(seq))+1 生成下一序号，并发追加会产生重复 seq |
| 19 | backend/app/services/foreshadowing_service.py:207 | deprecated-config | foreshadowing_service.py 多处使用已废弃的 datetime.utcnow()，应改为 datetime.now(timezone.utc) |

## 误报剔除记录（对抗验证质量证明）

| 位置 | 声称问题 | 剔除理由 |
|---|---|---|
| backend/app/api/routers/auth.py | register_with_linuxdo 将 token JSON 直接拼入 <script> 内 JS 字符串字面量，存在 latent XSS/解析破坏风 | 代码描述属实但不是真实漏洞，是潜伏/理论风险。已核实：auth.py:88,96 确实将 token.model_dump_json() 直接插值进 <script> 内 JSON.parse('...') 单引号字面量。但 Token s |
| backend/app/repositories/base.py | BaseRepository.update_fields 静默跳过 None 值，无法通过它清空可空字段 | 误报。代码机制描述属实（base.py:41 `if value is None: continue` 确实跳过 None，update_user_admin/patch_config 用 exclude_unset=True 透传显式 n |
| backend/app/models/chapter_generation_trace.py | ChapterGenerationTrace.project_id/chapter_number 为冗余列无 FK，仅靠应用层保证与 chapter 一致 | 结构性事实准确（chapter_id 有 FK+CASCADE；project_id/chapter_number 无 FK，仅作复合索引列），但所声称的"应用层一旦写错无法被发现"风险在实际代码中不成立：  1. 唯一生产构造点 chap |
| backend/app/db/init_db.py | _ensure_database_exists 用 f-string 拼接 CREATE DATABASE SQL，非参数化 | 代码事实部分准确（init_db.py:121 确实用 f-string 拼 CREATE DATABASE），但不构成真实安全漏洞，应判为误报：1) PostgreSQL 协议层不支持对 CREATE DATABASE 等 DDL 做参数 |
| backend/app/models/faction.py | Faction/FactionRelationship/FactionMember/FactionRelationshipHistory/WriterPerso | 发现的核心技术主张错误，属误读代码 + 虚构类型不匹配。  1. FK 目标误读：发现称 `faction_members.character_id` (BigInteger) FK 到 `factions.id` (Integer) 类型 |
| backend/pytest.ini | backend/pytest.ini 与根 pytest.ini 冲突：loop_scope=function vs 根的 session，从 backend/ | 误报：发现把两个 pytest.ini 的内容对调了。实际值（已 cat -n 确认，且 git 未列为改动）：根 pytest.ini:4 = asyncio_default_fixture_loop_scope = function；b |
| frontend/src/stores/auth.ts | 登录令牌(Bearer access token)直接持久化在 localStorage,任一 XSS 即可窃取会话 | 代码描述属实但属理论风险，不满足审计"攻击路径可行，非理论风险"标准。核实结果：(1) auth.ts:7/18/20 token 确存 localStorage，client.ts:28 从中读取拼 Bearer 头，auth.py:98 |
| pytest.ini | 根 pytest.ini 的 asyncio_default_fixture_loop_scope=function 与 backend/pytest.ini  | 误报。发现描述的代码事实属实（根 pytest.ini 是 function、backend/pytest.ini 是 session），但核心论点"function 与 session-scoped fixture 冲突，导致 async |
| integration_design.md | integration_design.md 的“文件修改清单”与实现脱节：列出的多个文件不存在却标 ✅ | 误报。核实发现该 finding 存在三类问题：(1) 分类错误——integration_design.md 不是 "deprecated-config"，而是一份设计提案文档（标题"AI小说创作提示词体系集成方案"，含集成原则/功能模块 |
| deploy/supervisord.conf | supervisord 中 nginx 进程以 root 运行，但监听 6100(>1024) 无需 root，与 Dockerfile 声称的“降权运行各进程 | 事实描述准确（supervisord.conf:23 nginx user=root，端口 6100>1024，Dockerfile:109 注释提及降权），但发现误判了安全暴露面，属于"正常框架行为"。  关键反驳点： 1. deploy |
| goal-1/ | goal-1/ 为上轮审计临时产物，工作树已删但删除状态混合（1 个 staged + 4 个 unstaged）且未提交 | 误报。发现的核心证据与实际 git 状态不符，且该事项已在审计上下文中被明确记录为已知待处理项。  1. 证据事实错误：发现声称 goal-1/ 处于"1 staged + 4 unstaged"混合状态，并 specifically 说  |
| .gitignore | .gitignore 未覆盖 .mindfs/，其下 session-list.db（二进制 sqlite）未被忽略，存在误提交风险 | 误报。发现声称 .mindfs/sessions/session-list.db（二进制 sqlite）"未被忽略，存在误提交风险"，但实际已被 .gitignore 第 29 行的全局规则 *.db 覆盖。git check-ignore |
