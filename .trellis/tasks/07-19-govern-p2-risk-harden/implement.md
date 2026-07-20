# P2 风险加固 - 实施

## 前置确认（实现前 rg 验证）

- [ ] M4 6 列确认无现存索引：`rg "index=True|Index\(" models/{chapter,blueprint,novel}.py` 对应列
- [ ] M5 确认 `novel_projects.id` 是 `String(36)`（FK 目标长度匹配）
- [ ] M19 `llm_tool.py` LLMTool 生命周期：`rg "LLMTool\("` 确认是否每次请求新建（决定 aclose 策略）
- [ ] M7 `resolved_at_chapter_id` 读取方：`rg "resolved_at_chapter_id"` 确认改 nullable 不破坏代码

## 实施顺序（按提交分组）

### Commit 1: SSRF 加固（M3/M10/M24）

- [ ] `core/ssrf.py:39-41`：`except socket.gaierror: return` -> `raise ValueError("API URL 主机无法解析")`；`if not infos: return` 同样改 raise；注释标注 rebinding 残余风险
- [ ] `services/auth_service.py:handle_linuxdo_callback`：token_url/user_info_url 发请求前 `assert_safe_base_url(...)` 校验；`data['id']`/`data['username']` -> `data.get(...)` + 缺失抛 400
- [ ] 验证：`pytest tests/` 相关 ssrf/auth 用例

### Commit 2: KRService async（新发现）

- [ ] `services/knowledge_retrieval_service.py`：
  - import `Session` -> `select` + `AsyncSession`
  - `__init__` `db: Session` -> `db: AsyncSession`，`self.db` -> `self.session`
  - 6 处 `self.db.query` -> `await self.session.execute(select(...))`（:221/:271/:382/:565/:587/:611）
  - `_get_chapter_blueprint` `def` -> `async def`，:203/:280/:336 调用加 `await`
- [ ] `services/pipeline_orchestrator.py:1888-1889`：删 `sync_session = getattr(...)`，传 `self.session`
- [ ] 验证：`pytest` 全绿（KRService 经两层 RAG 链路被 generate_chapter 覆盖）

### Commit 3: alembic 迁移 + env + model（M4/M5/M7/M9）

- [ ] 改 model：`models/rag.py` project_id `String(64)`->`String(36)` + `ForeignKey("novel_projects.id", ondelete="CASCADE")`；`models/foreshadowing.py:81` resolved_at_chapter_id `ondelete="CASCADE"`->`"SET NULL"` + `nullable=False`->`nullable=True`
- [ ] 生成迁移：`cd backend && alembic revision --autogenerate -m "p2 risk harden indexes fk cascade"`（需 env compare_type 先启用？先改 env 再生成）
- [ ] 改 `alembic/env.py`：offline(:28) + online(:39) `context.configure(...)` 加 `compare_type=True, compare_server_default=True`
- [ ] 手工补迁移文件：6 索引 `op.create_index` + RAG FK/长度 `op.alter_column`/`op.create_foreign_key` + 伏笔级联 `op.alter_column`/`op.drop_constraint`/`op.create_constraint`；downgrade 反向
- [ ] 验证：`alembic upgrade head` && `alembic downgrade -1` && `alembic upgrade head`

### Commit 4: AsyncOpenAI close（M19）

- [ ] `services/llm_service.py:857`：局部 client 改 try-finally `await client.close()`
- [ ] `services/llm_config_service.py:601`：try-finally `await client.close()`
- [ ] `utils/llm_tool.py:46`：加 `async def aclose(self)` 关闭 `self._client`；调用方（确认生命周期后）在结束调 `await tool.aclose()`
- [ ] 验证：`pytest` 全绿

### Commit 5: usage 原子 + vector re-raise + consistency 质量门（M21/M23/M22）

- [ ] `repositories/usage_metric_repository.py`：加 `increment_atomic(key)` 执行 PG `INSERT ... ON CONFLICT(key) DO UPDATE SET value=value+1`（一条 SQL 原子）
- [ ] `services/usage_service.py:increment`：改调 `repo.increment_atomic(key)`，**不 commit**（让调用方事务统一）；`get_value` 同理不 commit
- [ ] `services/vector_store_service.py:upsert_chunks/upsert_summaries`：失败 re-raise（删 `except` 吞错，保留 rollback 后 raise）
- [ ] `services/consistency_service.py:214-221`：异常 `is_consistent=True` -> `is_consistent=False`
- [ ] 验证：`pytest` + 新增 usage 原子/consistency 失败拦截测试

### Commit 6: nginx 加固（M17/M18）

- [ ] `deploy/nginx.conf`：server 块加 5 安全响应头；JS/CSS location `no-store` -> `public, max-age=31536000, immutable`
- [ ] 验证：`nginx -t`（如有 nginx；否则人工 review 配置语法）

### Commit 7: import 限制 + writer 归校 + debug 校验（M20/M2/K）

- [ ] `services/import_service.py:_read_file_content`：读后校验 `len(content_bytes) <= 10*1024*1024`，超限抛 413
- [ ] `api/routers/writer.py:generate_chapter`：try 前 `await novel_service.ensure_project_owner(project_id, current_user.id)`
- [ ] `core/config.py:assert_production_security`：加 `if settings.debug: raise RuntimeError("生产环境不得开启 debug")`
- [ ] 验证：`pytest` 全绿

## 全量验证

- [ ] `cd backend && python -m pytest` 全绿
- [ ] `cd backend && alembic upgrade head` && `alembic downgrade -1` && `alembic upgrade head` 往返
- [ ] `cd frontend && npx vue-tsc --build && npx vitest run && npx eslint . && npx vite build` 全绿
- [ ] 独立复核（Agent 读磁盘代码验证 16 项 + 决策项）

## 决策项记录

- M6/M11 决策不删（design.md 已述理由），在 audit-governance doc 标注

## P1 已处理项

M1/M8/M12/M13/M14/M15/M16/M25 已在 P1 删除/确认误报，audit-governance doc 已记录
