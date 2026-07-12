# 安全基线加固（CORS/API Key 加密/SSRF/认证）

## Goal

让 MoFeng 从"默认可启动"达到"生产可暴露"的安全基线。

来源：2026-07-12 多专家审查报告（`docs/mofeng-audit-report-2026-07-12.html`）滴滴后端架构师 P0 + 阿里后端专家。

## Requirements

- CORS 收敛为前端域名白名单；生产环境关闭通配 `*` 与 `allow_credentials` 组合。
- 用户上游 API Key 落库为密文（Fernet/AES-GCM，密钥从 SECRET_KEY 派生），应用层透明加解密。
- LLM/TTS `base_url` 增加 SSRF 防护：协议白名单（https）+ 私有/环回/链路本地 IP 黑名单 + DNS 解析后二次校验。
- 认证加固：SECRET_KEY 启动熵值校验；默认管理员口令强制改密覆盖所有 `is_admin`（不按用户名匹配）；越权统一 404；OAuth 注册受 `allow_registration` 约束 + username 唯一预检；验证码用 `secrets.compare_digest`。

## 子任务（追踪于会话 TaskList）

- #11 CORS 收敛为域名白名单（`backend/app/main.py:86-92`）
- #12 用户 API Key 改为加密存储（`llm_config_service.py:320,356`）
- #13 为 LLM/TTS base_url 增加 SSRF 防护（`llm_config_service.py:319,354` + `llm_service.py:848,874`）
- #14 认证安全加固（默认口令/JWT refresh/越权 404/OAuth/`compare_digest`）

## Acceptance Criteria

- [x] 全仓不再出现 `allow_origins=["*"]`；跨域仅白名单域名通过预检。
- [x] DB 中 API Key 字段为密文；前端仅见 `api_key_preview`。
- [x] 配置内网/localhost/云元数据地址的 `base_url` 被拒绝并给出明确错误。
- [x] 默认管理员首登强制改密；OAuth 受注册开关约束。
- [ ] 越权请求返回 404（**已知偏差**：`ensure_project_owner` 实现为不归属→403 / 不存在→404；审计建议越权统一 404 避免泄露存在性，未对齐，待确认是否单列修复）。

## Notes

- 建议排在路线图**阶段一（1-2 周，止血）**最前。
- 本任务为审查后的**整理产出，未进入实现**。实现需 `task.py start` 后补 `design.md` / `implement.md`（如涉及加密密钥派生、SSRF 策略等需明确技术方案）。
- 关联报表：第陆章 滴滴后端架构师、第贰章 P0 看板·安全基线。

## Completion

全部子任务（#11 CORS / #12 API Key 加密 / #13 SSRF / #14 认证加固）已实现并落盘 `0287c2e`。验证依据：审计会话后端 pytest 191 全绿。spec 沉淀见 `backend/security-guidelines.md`。

**已知偏差**：#14 越权返回码验收要求 404，实现为 403（`NovelService.ensure_project_owner`：不存在→404、不归属→403）。安全语义上 403 会泄露资源存在性，未对齐审计建议。是否统一为 404 待用户确认；不阻塞本任务归档。
