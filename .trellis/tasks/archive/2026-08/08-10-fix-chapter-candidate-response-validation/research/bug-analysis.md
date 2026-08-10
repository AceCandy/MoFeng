# Bug Analysis: 章节候选响应污染与截断漏检

## 1. Root Cause Category

- **Category**: B - Cross-Layer Contract
- **Specific Cause**: Anthropic 终止原因没有归一到服务层的 `length`，候选正文解析又在结构化解包失败后回退原文。通用 `unwrap_markdown_json` 还会从混合文本中截取对象，使未闭合围栏或带前后说明的响应看似合法。传输层、收集层和 durable activity 对“完整且可持久化的正文”没有统一失败契约。
- **Secondary Causes**: D - 测试仅覆盖成功解包且缺少 ambiguous/reconciler 组合状态；E - 隐含假设模型总会返回可解析 JSON 或纯正文，并假设 checkpoint 差异总比已确认的外部调用歧义更权威。

## 2. Why Fixes Failed

1. 早期解包修复只覆盖合法围栏、嵌套 JSON 和转义文本，没有覆盖未转义正文引号及不可修复包装。
2. 服务层已有 `finish_reason == "length"` 防线，但 Anthropic 的 `max_tokens` 没有在协议边界映射，导致同一语义走出不同结果。
3. 第一次收紧失败判断时仅看首字符，误伤 `[注]`、`{旁白}` 等合法正文；独立复核后改为识别围栏或实际 JSON 键形状。
4. 第一次统一优化解析器仍保留字段正则兜底；它能提取已闭合的字符串字段，却无法证明外层对象完整，导致残缺 JSON 仍被误判为成功。
5. Pipeline 的 guardrail 重写、补写、压缩、预览扩写和 enrichment 原本直接采用 raw/cleaned 响应；即使优化入口失败关闭，同类包装仍能从这些正文转换路径进入候选。
6. trace 恢复在缺少已定稿 `output_payload.full_content` 时回退 `cleaned_output`，会把初稿阶段尚未验证或尚未完成后处理的内容重新暴露为候选。
7. AI 评审正确进入 `ambiguous_external_result` 后，reconciler 仍继续比较 checkpoint id，把尚未同步的 checkpoint 当作 `checkpoint_drift`，覆盖了真正需要人工判断的原始错误。

## 3. Prevention Mechanisms

| Priority | Mechanism | Specific Action | Status |
|----------|-----------|-----------------|--------|
| P0 | Architecture | 在供应商协议边界归一停止原因，在 activity 成功前验证正文 | DONE |
| P0 | Test Coverage | 覆盖截断、未转义引号、残缺/缺字段包装、普通括号正文和版本标题 | DONE |
| P0 | Systematic Scan | 修复优化路由、全部章节正文转换及 trace 恢复中的原响应回退，并扫描剩余结构化模型路径 | DONE |
| P0 | Parser Contract | 仅接受可完整解析的 JSON object；禁止用单字段正则绕过外层结构校验 | DONE |
| P0 | Reconciliation Contract | 对 root/run 一致的 `needs_attention + ambiguous_external_result` 保持稳定，不让 checkpoint 维护逻辑重新分类 | DONE |
| P0 | Safe Diagnostics | activity 异常日志只记录阶段、内容寻址标识和异常类型，不记录异常消息或 traceback | DONE |
| P1 | Documentation | 将模型响应 fail-closed 契约写入 durable workflow spec | DONE |

## 4. Systematic Expansion

- **Similar Issues**: 优化路由、Pipeline 评审润色和 Pipeline 分维度优化原有三套解析逻辑，其中三处原文成功回退均已移除。Pipeline 初稿、guardrail 重写、补写、压缩、预览扩写及 enrichment 现统一调用 `parse_chapter_content_response`；初稿失败终止候选，可选转换失败保留上一版。trace 恢复只接受已验证的 `output_payload.full_content`，不再使用 `cleaned_output`。reconciler 的其它 `needs_attention` 类别仍按 checkpoint 证据收敛，仅外部调用结果未知这一不可自动裁决的类别保持稳定。
- **Design Improvement**: 供应商差异只留在 transport adapter；服务和工作流只消费统一结束语义与已验证输出。维护任务先尊重已经持久化的不可自动裁决事实，再处理派生 checkpoint 差异。
- **Process Improvement**: 修改解析启发式时，同时添加“应拒绝”和“必须保留”的成对测试，并由独立审查者核验兼容边界。

## 5. Knowledge Capture

- [x] 更新 `.trellis/spec/backend/durable-job-guidelines.md`
- [x] 新增聚焦回归测试
- [ ] 合并前由维护者提交代码与 spec 更新
