# 实施计划：正文节点模型路由展示

1. 抽取正文工作流节点静态定义，补充节点到 stage/capability 的映射，让 `ChapterGenerating` 复用该定义。
   - 验证：节点 key、顺序、分组、kind、optional 与 retryCommand 不变；新增映射单测试。
2. 将阶段路由定义分为正文工作流和其他功能，将 `rag_embedding` 纳入唯一 stage key 全集，并以 `chapter_writing_1/2`、`general_chat` 替换 `chapter_writing`。
   - 验证：21 个 chat stage 和 `rag_embedding` 均且仅出现一次于保存语义中，`general_chat` 只出现在其他功能。
3. 改造 `RoutingStagesPanel` 为节点分组展示，按 capability 选择模型，显示共用 stage、具体默认模型和无模型节点。
   - 验证：组件测试覆盖 chat/embedding 选项隔离、共用节点回写、无模型节点和 aria-label。
4. 更新 `PersonalModelRouting` / `useStageRoutes` 接线，保持现有 save/isDirty/saved 合同。
   - 验证：组合测试覆盖读取已存 `rag_embedding`、去重保存 payload 和共用 stage 同步。
5. 更新后端 stage 集合、通用默认 stage 和候选调用映射，使两个候选按 ordinal 使用独立路由，不保留旧 stage 回退。
   - 验证：聚焦 Pytest 覆盖 capability 和两个候选 stage，确认 API/数据库结构未变。
6. 执行独立复核，确认工作流拓扑、提示词、重试和生成参数未改变。
   - 验证：运行聚焦 Pytest、Vitest 与 `npm run type-check`；按 diff 点验 stage 映射、保存 payload 和正文节点列表。

## 风险文件与回滚点

- `frontend/src/components/writing-desk/workspace/ChapterGenerating.vue`：只允许把现有节点数组切换到共享定义，不改状态/重试逻辑。
- `frontend/src/components/llm-settings/useStageRoutes.ts`：保存 payload 必须以去重 stage key 生成，避免重复节点产生重复路由。
- `frontend/src/components/llm-settings/RoutingStagesPanel.vue`：保留原生 select、键盘行为和窄屏自适应。
- `backend/app/services/chapter_workflow_handler.py`：只按候选 ordinal 切换 stage，不改提示词、参数或工作流节点。
- 回滚点：整体回退本任务的前端 diff，无数据迁移或后端状态回滚。

## 预计验证命令

```bash
cd frontend
npx vitest run <新增或修改的聚焦 spec>
npm run type-check
```

不默认执行后端测试或全量 `npm run build`，因为计划不修改后端或发布产物。
