# P2 风险加固 - 设计

## 范围

审计 medium 25 条 + P0 复核新发现 1 条（KnowledgeRetrievalService async）。分类处置：

- **真做 16 项**：安全 6 + 数据层 4 + 资源/并发 5 + 质量门 1
- **决策不删 2 项**：M6 LLMConfig legacy 字段、M11 openai 死配置（经核查在用，见下）
- **P1 已处理 8 项**：M1/M8/M12/M13/M14/M15/M16/M25（dead-code 类，P1 已删）

## 决策项（不删，附理由）

- **M6 LLMConfig legacy 字段**（llm_provider_*/embedding_provider_* 7 字段）：`schemas/llm_config.py` 仍定义、`routers/llm_config.py:77-78` 写回、`llm_service.py:795/802` 读取 `embedding_provider_format`。运行期有读取方，非死字段。保留。
- **M11 openai_api_key/openai_base_url/openai_model_name + llm.api_key 系统配置种子**：`db/system_config_defaults.py:28/33/38` 用 `value_getter=lambda config: config.openai_api_key` 作为 system_config 种子写入 DB，`llm_service._get_config_value("llm.api_key")` 从 DB 读取。是种子链路源，非死配置。保留。

## 修复模式

### 模式 A：SSRF 加固（M3/M10/M24）

`core/ssrf.py:assert_safe_base_url`：
- 现状：DNS 解析失败（`socket.gaierror`）直接 `return` 放行 → DNS rebinding 绕过（攻击者首次解析公网 IP 通过校验，实际请求时 DNS 返回内网 IP）。
- 修法：解析失败改 `raise ValueError("API URL 主机无法解析")`。堵 rebinding 一半（校验与请求仍独立解析，残余风险见注释）。
- `allow_loopback=True` 默认是有意的（本机 ollama 合法），保留，注释说明。
- 残余 rebinding（校验用 getaddrinfo、请求用 httpx 独立解析）需 pin IP 才能完全堵，但 LLM 调用层（AsyncOpenAI/httpx）不便 pin IP，P2 不做，注释标注残余风险。

`auth_service.handle_linuxdo_callback`（M24）：
- `token_url`/`user_info_url` 来自管理员 DB 配置，服务端发请求无 SSRF 校验。
- 修法：发请求前 `assert_safe_base_url(token_url, allow_private=settings.allow_private_llm_endpoints)` + 同样校验 `user_info_url`。
- `data['id']`/`data['username']` 直接下标 → `data.get('id')`/`data.get('username')` + 缺失抛 400。

### 模式 B：async 修复（KRService，H5 同模式）

`knowledge_retrieval_service.py`：
- `__init__`: `db: Session` → `db: AsyncSession`，`self.db` → `self.session`
- import: `from sqlalchemy.orm import Session` → `from sqlalchemy import select` + `from sqlalchemy.ext.asyncio import AsyncSession`
- 6 处 `self.db.query(X).filter(...).first()` → `(await self.session.execute(select(X).where(...))).scalars().first()`
- 6 处 `.all()` → `(await self.session.execute(select(X).where(...).order_by(...).limit(...))).scalars().all()`
- `_get_chapter_blueprint` sync def → async def（:382），3 处调用方（:203/:280/:336）加 `await`
- 调用方 `pipeline_orchestrator.py:1888-1889`：删 `sync_session = getattr(...)`，传 `self.session`

### 模式 C：alembic 迁移（M4/M5/M7）+ env 配置（M9）

一个迁移文件 `p2_risk_harden.py`：
- **M4 加 6 索引**：`chapter_versions.chapter_id`、`chapter_evaluations.chapter_id`、`blueprint_characters.project_id`、`blueprint_relationships.project_id`、`chapter_outlines.project_id`、`novel_conversations.project_id`（先确认模型未已建索引）
- **M5 RAG 表 project_id**：`rag_chunks.project_id`/`rag_summaries.project_id` `String(64)` → `String(36)` + 加 FK `→ novel_projects.id ondelete CASCADE`（删项目级联清孤儿向量）
- **M7 伏笔回收级联统一**：`foreshadowing_resolutions.resolved_at_chapter_id` `CASCADE` → `SET NULL` + `nullable=False` → `nullable=True`（与 `foreshadowings.resolved_chapter_id` SET NULL 一致，保留伏笔历史）
- 同步改 model：`rag.py` project_id String(36) + ForeignKey；`foreshadowing.py` resolved_at_chapter_id ondelete/nullable
- env.py（M9）：`context.configure(...)` 加 `compare_type=True, compare_server_default=True`（offline + online 两处）

验证：`alembic upgrade head` + `alembic downgrade -1` + `alembic upgrade head` 往返。

### 模式 D：AsyncOpenAI 资源释放（M19）

三处实例化：
- `llm_service.py:857`：局部 client（每次 embedding），改 `async with` 或 try-finally `await client.close()`
- `llm_config_service.py:601`：局部 client（测连通），try-finally close
- `llm_tool.py:46`：`self._client`（LLMTool 实例生命周期），加 `aclose()` 方法，调用方在结束时关闭。先确认 LLMTool 生命周期（是否每次请求新建）。

### 模式 E：usage 原子计数（M21）

`usage_service.increment`：现 `get_or_create` + `counter.value += 1` + `commit()` 非原子 + 共享 session commit 污染调用方事务。
- 修法：原子 `UPDATE usage_metrics SET value = value + 1 WHERE key = :key`（无则先 insert），用独立 session 或 `flush` 不 `commit`。
- 务实方案：`repo.increment_atomic(key)` 执行 `UPDATE ... SET value=value+1`（PG `INSERT ... ON CONFLICT DO UPDATE` 一条 SQL 原子 upsert + 计数），service 层不 commit（让调用方事务统一提交）。

### 模式 F：质量门不放行（M22）

`consistency_service.consistency_check` 异常时 `is_consistent=True` → 改 `is_consistent=False`（质量门失败应拦截，不放行）。

### 模式 G：vector_store re-raise（M23）

`upsert_chunks`/`upsert_summaries` 失败仅日志 → re-raise（与 `delete_by_chapters` 一致），调用方感知。

### 模式 H：nginx 加固（M17/M18）

- M17 加安全响应头：`X-Frame-Options DENY`、`X-Content-Type-Options nosniff`、`Referrer-Policy strict-origin-when-cross-origin`、HSTS（`Strict-Transport-Security`，63d）、CSP（`default-src 'self'`，按前端实际放宽）
- M18 JS/CSS：`no-store` → `public, max-age=31536000, immutable`（Vite 哈希资产，文件名带 hash，长期缓存安全）

### 模式 I：import 大小限制（M20）

`import_service._read_file_content`：`await file.read()` 一次性读全文无限制。
- 修法：读前校验 `file.size`（或读后 `len(content_bytes)`）≤ 限制（如 10MB，与 nginx `client_max_body_size 50M` 协调，应用层更严），超限抛 413。

### 模式 J：writer 归属校验（M2）

`writer.generate_chapter` 路由层补 `await novel_service.ensure_project_owner(project_id, current_user.id)`（OUTSIDE try，与 H1 list_foreshadowings 同模式，越权 404 不被 try 吞 500）。

### 模式 K：生产 debug 校验

`assert_production_security` 加 `if settings.debug: raise RuntimeError("生产环境不得开启 debug")`。

## 验证

- 后端 pytest 全绿（229+，新增迁移不改测试期望）
- `alembic upgrade head` + `alembic downgrade -1` + `alembic upgrade head` 往返
- 前端 vue-tsc/vitest/eslint/build 全绿（P2 不改前端，预期无影响，仍跑确认）
- 行为变更补测试（usage 原子、consistency 失败拦截）

## 提交拆分

按分组语义化提交：
1. SSRF 加固（ssrf.py + auth_service.py）
2. KRService async 修复
3. alembic 迁移 + env compare_type + model 同步
4. AsyncOpenAI close
5. usage 原子 + vector_store re-raise + consistency 质量门
6. nginx 加固
7. import 限制 + writer 归校 + debug 校验
