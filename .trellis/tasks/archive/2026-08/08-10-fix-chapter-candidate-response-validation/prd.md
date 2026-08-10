# 修复章节候选响应污染与截断漏检

## Goal

阻止章节候选和章节优化接口把无效结构化包装、错误版本标题或因模型长度限制截断的正文作为成功结果，确保用户看到的候选与优化结果都是可用的纯正文。

## Background

- 项目 `9f20a79c-280d-407f-b839-1fbdad5cae28` 第 4 章的版本 `188` 是评审后优化结果。其 JSON 因正文内未转义的 ASCII 双引号 `"左胸"` 无法解析，现有 `_content_from_response` 随后把原始 JSON 围栏当正文返回并持久化（`backend/app/services/chapter_workflow_handler.py:102-142`）。
- 同章版本 `189` 以 `# 版本一` 开头并在 `"那叫` 处结束，数据库内容本身已截断。`writing_v2` 明确禁止 JSON 和小标题，规划与评审结果也未包含该标题。
- Anthropic 客户端原样上送 `stop_reason`（`backend/app/utils/llm_tool.py:149-164`），服务层只拒绝 OpenAI 风格的 `finish_reason == "length"`（`backend/app/services/llm_service.py:845-855`），未覆盖 Anthropic 的长度停止值。
- 优化接口 `_parse_optimizer_response` 在 JSON、字段提取都失败后仍把原始模型响应作为 `optimized_content` 成功返回；数据库中的五个优化提示词均要求返回包含 `optimized_content` 的 JSON，因此该回退会把包装或异常响应继续传给可保存结果的前端。
- `PipelineOrchestrator` 的评审润色和分维度优化各自维护另一套解析逻辑，两处同样在 JSON 失败时把原始模型响应赋给正文，随后可能进入版本持久化。
- 修复响应边界后的一次 AI 评审失败先正确进入 `ambiguous_external_result`，随后 reconciler 又因 run 尚未复制最新 checkpoint id 将其覆盖为 `checkpoint_drift`，用户最终只看到泛化的“工作流持久状态不一致”。

## Requirements

- **R1 统一截断语义**：Anthropic 因输出长度停止时，必须被归一为服务层已有的截断语义，使流式和收集式调用都走现有失败路径，不得返回部分正文。
- **R2 安全解析优化结果**：章节候选解析应复用现有 JSON 修复能力，支持正文字符串内未转义双引号的结构化响应；修复后仍无法解析且明显是结构化包装的响应必须失败，不得把围栏、字段名或转义文本作为正文。
- **R3 清理违规版本标题**：候选纯正文开头的 Markdown 版本标记（如 `# 版本一`、`## 版本 2`）必须移除；普通正文和非版本标题保持不变。
- **R4 保持兼容**：合法 JSON、嵌套 JSON、转义围栏、普通纯正文以及字面量反斜杠的现有行为保持不变。
- **R5 聚焦回归覆盖**：新增测试必须分别覆盖 Anthropic 长度停止、未转义正文引号、不可修复的未闭合结构化响应、版本标题清理和普通正文保留。
- **R6 优化接口失败关闭**：优化响应仅在提取到非空 `optimized_content` 时成功；JSON 解析和字段提取均失败、缺少正文键或只返回纯文本时必须失败，不得把原始模型响应作为优化正文。
- **R7 共用优化解析契约**：优化路由、评审润色和 Pipeline 分维度优化必须共用同一结构化响应解析器；强制润色解析失败时终止生成，可选维度解析失败时保留上一版正文，任何路径都不得采用原始响应。
- **R8 覆盖全部正文转换路径**：Pipeline 初稿、guardrail 重写、补写、压缩、预览扩写及 enrichment 产生的章节正文必须经过同一完整响应边界；完整 JSON、完整 JSON 围栏和明确纯正文可以采用，未闭合包装或 JSON 前后带游离说明必须拒绝。初稿解析失败时终止该候选，可选转换解析失败时保留上一版合法正文。
- **R9 恢复只使用已验证正文**：从 trace 恢复候选版本时，仅允许使用成功节点明确记录的 `output_payload.full_content`；不得回退到可能仍含包装或定稿前内容的 `cleaned_output`。
- **R10 保留外部调用歧义根因**：root job 与 workflow run 均已进入 `needs_attention + ambiguous_external_result` 时，reconciler 必须保留原错误类别和公开消息，不得因 checkpoint 尚未同步而覆盖为持久状态错误；内部诊断日志不得包含异常消息、prompt、正文、provider request key 或密钥。
- **R11 从失败节点人工重试**：外部调用结果不确定时，用户确认可能重复调用后必须能够直接重试该节点；已持久化的前置节点结果必须复用，不得重新调用前置 provider。目标 run 尚无 checkpoint id 时仍可提交外部重试或取消，但普通 retry、select 与 projection retry 仍必须绑定 checkpoint。原 ambiguous 记录必须保留；人工重试再次处于 started 或 ambiguous 时不得自动重放。
- **R12 失败节点展示重试入口**：服务端允许 `retry_external` 且返回 `retry_activity_key` 时，全局失败恢复条不得与生成进度重复展示；用户显式选中当前失败节点后，节点上淡入“重试此节点”。提交中必须禁用，确认可能重复调用的风险后复用现有命令链提交该 activity key，历史失败节点不得误用当前 activity key；不支持节点级外部重试的失败类型继续保留原恢复面板。

## Acceptance Criteria

- [x] **AC1 / R1**：Anthropic `stop_reason=max_tokens` 不再产生成功的部分正文，聚焦测试可复现并通过。
- [x] **AC2 / R2**：包含未转义 `"左胸"` 的优化 JSON 被提取为纯正文，不包含 ` ```json`、`optimized_content` 或 `optimization_notes`。
- [x] **AC3 / R2**：缺少闭合引号、对象或围栏且无法可靠修复的结构化响应抛出错误，不创建候选版本。
- [x] **AC4 / R3**：`# 版本一`、`## 版本 2` 被移除；普通正文首行和其他 Markdown 标题不被删除。
- [x] **AC5 / R4-R5**：现有章节工作流解析测试和 LLM 协议测试通过，新增回归测试通过。
- [x] **AC6 / R6**：优化接口继续接受合法 JSON、围栏 JSON和可安全修复的正文引号；纯文本、残缺包装及缺少正文键的响应均明确失败。
- [x] **AC7 / R7**：Pipeline 评审润色对无效结构化响应记录失败并终止；分维度优化遇到同类响应时保留输入正文，且两者均不产生包含 JSON 包装的正文。
- [x] **AC8 / R8**：所有会成为章节版本正文的模型转换路径均复用共享解析器；混合文本、未闭合对象和未闭合围栏不会替换合法正文，初稿候选不会以异常包装成功。
- [x] **AC9 / R9**：trace 缺少 `output_payload.full_content` 时不从 `cleaned_output` 重建候选，并由上层使用更早的合法状态。
- [x] **AC10 / R10**：PostgreSQL 回归测试覆盖 run checkpoint id 为空、saver checkpoint 已存在的场景，reconciliation 返回 unchanged、不追加事件且保留 `ambiguous_external_result`；activity 日志仅暴露安全定位字段。
- [x] **AC11 / R11**：PostgreSQL 端到端回归覆盖 checkpoint id 为空的 ambiguous 模型节点：`retry_external` 提交后在同一事务内应用并重新排队，恢复执行只再次调用目标 provider 一次，使用 command 派生 activity 记录结果且保留原 ambiguous 审计记录；成功结果可重放，started/ambiguous 的人工 activity 均禁止自动重放。前端允许无 checkpoint 的外部重试/取消，同时继续拒绝无 checkpoint 的确定性恢复命令。
- [x] **AC12 / R12**：组件回归覆盖外部重试场景不渲染重复失败面板、按钮仅在显式选中当前失败节点后淡入并归属于该节点，以及缺少授权/key 时隐藏、提交中禁用、稳定 activity key 事件和普通 retry 面板保留；点击确认后沿 `WDWorkspace` 现有 `workflowRetryExternal` 事件提交，不新增 API 或状态源。

## Out of Scope

- 不自动修改、删除或选择数据库中现有的版本 `188`、`189`。
- 不调整模型路由、模型参数、章节字数目标或提示词内容。
- 不修改与失败节点重试入口无关的前端展示逻辑、API 契约或数据库结构。
- 不为任意残缺 JSON 猜测正文；无法可靠恢复时明确失败并允许工作流重试。

## Risks and Deferred Items

- 历史调用未持久化原始 `finish_reason`，无法证明版本 `189` 当次停止值；代码修复以已确认的协议映射缺口和可复现测试为准。
- 现有脏版本仍会保留在数据库中，需在代码修复后重新生成，或另行批准数据修复。
