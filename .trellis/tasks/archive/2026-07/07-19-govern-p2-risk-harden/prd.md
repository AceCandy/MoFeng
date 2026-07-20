# P2 风险加固

## Goal

修复审计确认的 25 条 medium 风险：SSRF、缺索引、资源泄漏、并发、质量门、nginx 加固等。

## Requirements（分组）

### 安全
- SSRF DNS rebinding（core/ssrf.py 解析失败放行 + 独立二次解析，2 条）
- auth linuxdo callback SSRF（向管理员配置 URL 发请求无校验）
- nginx 缺安全响应头（X-Frame-Options/CSP/HSTS 等）+ 哈希资产 no-store 损害缓存
- writer generate_chapter 未显式校验归属
- assert_production_security 未校验 debug=False

### 数据层
- 6 处高频 FK 列缺索引（chapter_versions/chapter_evaluations.chapter_id 等）
- RAG 表 project_id 无 FK + 长度不一致 -> 孤儿向量
- 伏笔回收级联不对称（SET NULL vs CASCADE）
- alembic 未启用 compare_type/compare_server_default

### 资源/并发
- AsyncOpenAI 客户端三处未 close（连接池泄漏）
- import 文件无大小限制（OOM）
- usage_service 非原子计数 + 共享 session commit 污染
- vector_store upsert 失败仅日志不 re-raise

### 质量门
- consistency_check 异常返回 is_consistent=True（静默放行）
- analytics.py 情感分析函数复制分叉（两份关键词表）

## 约束

- 索引/迁移改动需生成 alembic 迁移并验证正向+回滚
- 行为变更补测试
- 涉及多文件协同的（如 SSRF）统一 design

## Acceptance Criteria

- [ ] 25 条 medium 逐项修复或明确决策（含理由）
- [ ] 新增 alembic 迁移可正向+回滚
- [ ] 后端 pytest 全绿 + 前端 vue-tsc/vitest/eslint/build 全绿
- [ ] 独立语义化提交（可按分组拆多个 commit）

## 来源

审计报告 `docs/audit-governance-2026-07-19.md` medium 清单
