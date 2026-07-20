# P1 技术设计

## 策略
死代码清理，低风险高收益。逐项 `codegraph_callers` / `rg` 确认无引用（含 `__init__.py` `__all__`、动态调用、测试引用）后删除，连带清理 import / package.json 依赖 / vite 分包配置 / `__all__` 导出。

## 分类与处理
1. **backend 死 service（6 个）**：emotion_service / emotion_curve_service / cache_service / chapter_review_service / admin_setting_service / blueprint_service。`codegraph_callers` 确认零引用 → `git rm` + 清 `app/services/__init__.py` 的 `__all__` 与 import。
2. **backend 死路由**：foreshadowing 5 端点 P0 H1 已删（跳过）；updates/remote-version 死路由（与 P2 SSRF 协同：若 P2 修 SSRF 则保留补校验，否则删——P1 先确认引用情况决定）。
3. **backend 死配置/提示词**：LLMConfig 7 个 legacy 字段（llm_provider_*/embedding_provider_*）、openai_api_key 等系统配置种子、character_dna_guide.md 死提示词。
4. **frontend 死链路**：LLMSettings.vue(1027行)+legacy 配置查询、WorkspaceEntry.vue(603行)+updates 公开日志链路、WDHeader.vue(224行)、api/version.ts(136行)+RemoteVersionDebugEvent、chartLine.ts+chart.js 依赖+vite 分包、TypewriterEffect.vue、@fontsource/noto-sans-sc 依赖、gen:api 脚本+openapi-typescript devDep。
5. **入仓清理**：.dev-servers.json（gitignore+rm）、check_db.py（调试脚本）、goal-1/（已 git rm 待提交）。

## 验证
- 每类删除后跑相关测试 + `python -c "import app.main"`（backend）/ 前端四件套（frontend）
- 最终：后端全量 pytest + 前端四件套 + 独立复核
- 每类一个语义化 commit，可单独 revert

## 约束
- 不删测试（除非测试本身是死代码的回归测试且被删代码无其他引用）
- 删除连带清理：import、`__all__`、package.json 依赖、vite 分包配置
- 不可逆删除（git rm）前必须 codegraph_callers + rg 双重确认无引用

## 回滚
- 每类独立 commit，`git revert <hash>` 可单独回滚
