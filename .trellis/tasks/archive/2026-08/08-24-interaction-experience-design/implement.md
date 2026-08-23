# 整体创作交互体验实施计划

## Success Criteria

- 跨设备恢复最近项目、页面、章节、写作台分区与同轮次未发送灵感草稿；同字段最后写入覆盖。
- 六个核心页面形成无断链的前进/返回路径，并保持唯一主动作。
- 后台任务可回到安全成果位置，失败恢复复用写作台现有命令。
- 合同、迁移、响应式、键盘、减少动态效果与回归门禁通过。

## Execution

1. **建立持久化合同**
   - 新增 creation context ORM、复合键/检查约束和 Alembic 迁移。
   - 新增 schema、repository、service、鉴权 router；实现列表读取与字段级 PostgreSQL upsert。
   - 覆盖项目归属、空 PATCH、枚举/数值校验、级联删除、同轮次后写覆盖、旧轮次静默丢弃和不同字段不互相擦除。
   - verify：聚焦 API/service 测试 + PostgreSQL 并发/迁移测试。

2. **生成并接入前端合同**
   - 更新 `backend/openapi.json` 与生成的 `frontend/src/api/generated/schema.d.ts`。
   - 新增 creation context API aliases、Vue Query key/query/mutation；不新增 Pinia store。
   - verify：OpenAPI check、`npm run api:check`、API/query 单测。

3. **接入最近工作位置**
   - 工作台优先按 contexts 的 `updated_at` 构造继续动作，缺失时回退现有 `last_edited`。
   - 修正项目卡标题进入档案；项目档案继续创作使用最近章节。
   - AppShell 在 inspiration query 下识别项目，并展示稳定阶段签。
   - verify：工作台三态、档案/写作/灵感路由单测和桌面/移动 E2E。

4. **接入写作台语义恢复**
   - 显式 `chapter_number` query 优先于远端上下文；选择章节后同步 URL 与服务端。
   - 将 `WDWorkspace` 分区变为受控值，恢复有效分区，无效时回 `content`。
   - verify：显式 URL 优先、远端恢复、删除章节/无内容分区回退单测。

5. **接入灵感草稿同步与蓝图返回**
   - `ConversationInput` 支持草稿 v-model；`InspirationMode` 在恢复对话后按 `inspiration_turn` 注入草稿。
   - 实现 24 小时本地短期保护、短防抖同步、失败提示、重试、发送成功清理、过期清理与账号身份变化清理。
   - 蓝图确认态补返回对话动作，并更新退出提示文案。
   - verify：刷新/聚焦、离线/重新联网、轮次漂移、同轮次最后写入覆盖、TTL/账号清理、返回对话与键盘焦点测试。

6. **让后台任务可行动**
   - 在任务 schema/public projection/前端 decoder 中加入可空 `chapter_number`，严格限定三个正文任务类型。
   - TaskLogPanel 按任务类型和状态提供“返回创作 / 查看结果 / 回去处理”；无安全目标不显示动作。
   - 明示离开页面不影响运行；失败动作只导航，不伪造通用重试。
   - verify：列表/snapshot/SSE 均隐藏 payload，章节号白名单、路由映射与失败恢复单测。

7. **统一交互与视觉收尾**
   - 使用既有 token 完成阶段签、同步状态与任务动作；不新增视觉系统或装饰动画。
   - 完成后只运行一次 Impeccable detector；桌面和 Pixel 7 同批截图检查，集中修正一轮，最多再确认一轮。
   - verify：axe、焦点、44px 触控、无横向溢出、普通/减少动态效果场景。

8. **独立复核与质量门禁**
   - 先复核 diff 是否只覆盖 PRD，检查生成文件、迁移链、敏感本地草稿与临时产物。
   - 运行聚焦测试后再跑批准范围内的全量门禁；记录未执行项和已有基线失败。

## Validation Commands

后端非 Java，本任务允许执行聚焦测试与静态合同检查：

```bash
cd backend
pytest tests/test_creation_context.py tests/test_tasks_api.py --strict-markers
python -m app.openapi_export --check --output openapi.json
```

需要真实 PostgreSQL 的迁移、upsert 并发和级联行为：

```bash
cd backend
TEST_POSTGRES_URL="<isolated-postgres-url>" pytest -m postgres --strict-markers
python -m app.db.cli db-check
```

前端聚焦与合同检查：

```bash
cd frontend
npm run api:check
npm run type-check
npm run test:unit -- src/api/__tests__ src/queries/__tests__ src/components/__tests__
npm run test:e2e -- e2e/creation-continuity.spec.ts e2e/global-modal-accessibility.spec.ts
npm run lint
npm run build
```

关键 E2E 分别运行 `desktop-chromium` 与 `mobile-chromium`，并增加 `reducedMotion: 'reduce'` 场景。

## Review Gates

- API route 不直接操作 session；service 拥有事务，repository 只 flush/upsert。
- creation context 查询严格按当前用户隔离，项目越权与不存在统一 404。
- 本地草稿 key 包含 user/project/saved_at，成功、过期、账号身份变化与退出后移除；测试、日志和提交内容不出现真实草稿。
- 显式 route query 高于远端上下文；旧轮次草稿不能进入新轮次。
- 同一轮次最后写入覆盖；低于权威轮次的草稿静默丢弃，高于权威轮次的输入拒绝。
- 任务 payload/result 继续遵守公开投影合同，章节号只从 `chapter_workflow`、`chapter_finalize`、`chapter_edit_postprocess` 与正整数白名单生成。
- 无新增依赖、主题、实时协同、通用 retry/cancel 或单用途设计系统组件。

## Risk And Rollback Points

- **并发首次写入**：必须由 PostgreSQL upsert 处理，不允许“先查后插”的竞态。
- **草稿错位**：服务端用已持久化对话轮次校验；旧轮次写入不落库，并清除过期本地备份。
- **路由循环**：恢复只在初始化应用一次；后续由用户动作更新，不 watch 后反向强制导航。
- **旧任务事件**：`chapter_number` 可空；无字段时退回项目级导航。
- **回滚**：先关闭前端上下文消费，再移除 API/迁移；上下文表不含项目正文，回滚不损伤创作数据。
