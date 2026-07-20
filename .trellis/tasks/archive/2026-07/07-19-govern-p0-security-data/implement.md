# P0 执行计划

## 前置确认
- [ ] 确认 foreshadowing 功能启用状态（list 端点前端在用？5 死端点确认无前端调用）
- [ ] 确认 ensure_project_owner 签名（novel_service.py:200-207）与 ForeshadowingService 死方法引用

## H1 foreshadowing 越权
- [ ] codegraph_callers 确认 5 死端点 + 对应 service 方法无其他引用
- [ ] 删除 5 死端点 + 无引用的 service 方法
- [ ] list 端点补 `ensure_project_owner`
- [ ] 补越权测试（其他用户访问返回 404）
- [ ] 验证：pytest test_foreshadowing*
- [ ] commit: `fix(api): foreshadowing 越权修复，删 5 死端点 + list 补归属校验`

## H2 analytics_enhanced 删除
- [ ] git rm analytics_enhanced.py
- [ ] 验证：应用 import 正常（python -c "import app.main"）
- [ ] commit: `chore(api): 删除死路由 analytics_enhanced.py`

## H3 默认密码
- [ ] .env.example 改占位符
- [ ] docker-compose 改 :?
- [ ] config.py assert_production_security 校验 admin_default_password
- [ ] 清理 3 处泄露（env.example/deploy_docker.sh/DEPLOYMENT.md）
- [ ] 补测试：默认密码 assert 失败
- [ ] 验证：pytest test_config*/test_security*
- [ ] commit: `fix(security): 消除默认管理员密码硬编码，强制配置`

## H4 finalize 静默损坏
- [ ] 解耦 LLM 调用与 DB 事务（LLM 事务外）
- [ ] 内层 except 不静默，聚合失败
- [ ] success 严格语义 + partial_success
- [ ] 补测试：LLM 失败时 success=False/partial
- [ ] 验证：pytest test_finalize*
- [ ] commit: `fix(service): finalize_chapter 不静默 LLM 失败，解耦事务`

## H5 consistency async
- [ ] _get_check_context 改 await session.execute(select)
- [ ] 调用方传 AsyncSession
- [ ] 补 /api/review/consistency 集成测试
- [ ] 验证：pytest test_consistency*
- [ ] commit: `fix(service): consistency_service async 修复 MissingGreenlet 500`

## 最终验证
- [ ] 后端 pytest 全绿（cd backend + PYTHONPATH，绝对路径 python）
- [ ] 前端四件套（vue-tsc + vitest + eslint + build，cd frontend）
- [ ] 全量 check 复核（trellis-check Agent）

## review gates
- H1/H4/H5 涉及行为变更，实现后独立 check
- H3 涉及部署配置，需人工确认部署文档
