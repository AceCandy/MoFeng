# 修复主工作流优选版本投影：实施计划

1. 扩展 durable 持久化主链测试，先复现公开投影仍返回两个候选。
2. 在 `ChapterWorkflowCandidatePersistenceService._write_candidates` 写入由已验证 review 派生的严格布尔优选标记。
3. 验证持久化 metadata、evaluation 绑定、完整版本集合和待确认公开投影。
4. 运行 durable persistence 目标测试、NovelService 目标测试、前端组件测试、Ruff、类型检查与 ESLint。
5. 独立复核全量 diff；更新 durable workflow 规范与跨层思考指南，记录本次假阳性原因。

## Rollback Point

产品代码仅增加候选 metadata。若验证失败，恢复该写入并保留现有兼容回退，不涉及数据迁移。
