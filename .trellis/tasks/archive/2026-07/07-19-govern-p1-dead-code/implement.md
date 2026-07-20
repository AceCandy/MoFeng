# P1 执行计划

## backend 死 service（6 个）
- [ ] codegraph_callers 确认 6 service 零引用（emotion_service/emotion_curve_service/cache_service/chapter_review_service/admin_setting_service/blueprint_service）
- [ ] 确认 `app/services/__init__.py` 的 import + `__all__`
- [ ] git rm 6 service + 清 __init__.py
- [ ] 验证：`python -c "import app.main"`
- [ ] commit: `chore(api): 删除 6 个零引用死 service`

## backend 死路由
- [ ] foreshadowing 5 端点（P0 H1 已删，跳过）
- [ ] updates/remote-version：rg 确认引用 + 决定删/留（与 P2 SSRF 协同）
- [ ] commit（如删）: `chore(api): 删除死路由 updates/remote-version`

## backend 死配置/提示词
- [ ] LLMConfig 7 legacy 字段：rg 确认无引用 + 删 model 字段 + migration
- [ ] openai_api_key 等系统配置种子：确认 + 删
- [ ] character_dna_guide.md：git rm
- [ ] commit: `chore(config): 清理死配置/死提示词`

## frontend 死链路
- [ ] LLMSettings.vue + legacy 配置查询/接口函数：确认 + 删
- [ ] WorkspaceEntry.vue + queries/updates.ts + api/updates.ts：确认 + 删
- [ ] WDHeader.vue / api/version.ts+RemoteVersionDebugEvent / chartLine.ts / TypewriterEffect.vue：确认 + 删
- [ ] @fontsource/noto-sans-sc：package.json 移除 + node_modules 清理
- [ ] gen:api 脚本 + openapi-typescript devDep：移除
- [ ] vite.config.ts chart-tools 分包：移除
- [ ] 验证：前端四件套（vue-tsc + vitest + eslint + build）
- [ ] commit: `chore(frontend): 清理死链路与未用依赖`

## 入仓清理
- [ ] .dev-servers.json：.gitignore 补 + git rm --cached
- [ ] check_db.py：git rm
- [ ] goal-1/：确认 git rm
- [ ] commit: `chore: 清理入仓调试产物`

## 最终验证
- [ ] 后端 pytest 全绿（cd backend）
- [ ] 前端四件套全绿（cd frontend）
- [ ] 全量 check 复核（trellis-check Agent）

## review gates
- backend 死 service 删除前必须 codegraph_callers + rg 双重确认
- frontend 死链路删除前必须 rg 确认无组件/路由引用
- LLMConfig legacy 字段删除需 alembic migration（如字段已建表）
