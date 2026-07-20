# P1 死代码清理

## Goal

批量清理审计确认的死代码/死文件/死配置，降低维护负担与误导风险。低风险高收益。

## Requirements（清理清单）

### backend 死 service 文件（6 个，零引用）
- emotion_service.py / emotion_curve_service.py / cache_service.py / chapter_review_service.py / admin_setting_service.py / blueprint_service.py

### backend 死路由
- foreshadowing 5 个前端无调用端点（create/resolve/reminders/dismiss/analysis）- 与 P0 H1 协同
- updates/remote-version 死路由（与 P2 SSRF 协同：P2 修则保留补校验，否则删）

### backend 死配置/死提示词
- LLMConfig 7 个 legacy 字段（llm_provider_*/embedding_provider_*）
- openai_api_key 等系统配置种子（与已清理 embedding 死配置同构）
- character_dna_guide.md 死提示词

### frontend 死链路
- LLMSettings.vue(1027行) + legacy LLM 配置查询/接口函数
- WorkspaceEntry.vue(603行) + queries/updates.ts + api/updates.ts 公开更新日志链路
- WDHeader.vue(224行)
- api/version.ts(136行) + RemoteVersionDebugEvent
- chartLine.ts + chart.js 依赖 + vite.config.ts chart-tools 分包
- TypewriterEffect.vue
- @fontsource/noto-sans-sc 依赖
- gen:api 脚本 + openapi-typescript devDep（产物 schema.d.ts 从未提交/引用）

### 入仓清理
- .dev-servers.json（dev_servers.py 运行态，应 gitignore）
- check_db.py（一次性调试脚本）
- goal-1/（已 git rm 待提交）

## 约束

- 每项删除前用 codegraph_callers / rg 确认无引用（含 __init__.py __all__、动态调用、测试引用）
- 删除连带清理：import、package.json 依赖、vite 分包配置、__all__ 导出
- 不删测试（除非测试本身是死代码的回归测试，且被删代码无其他引用）

## Acceptance Criteria

- [ ] 上述清单逐项验证无引用后删除
- [ ] 删除后后端 pytest 全绿 + 前端 vue-tsc/vitest/eslint/build 全绿
- [ ] package.json 移除未用依赖
- [ ] .gitignore 补 .dev-servers.json
- [ ] 独立语义化提交

## 来源

审计报告 `docs/audit-governance-2026-07-19.md` medium/low 死代码类
