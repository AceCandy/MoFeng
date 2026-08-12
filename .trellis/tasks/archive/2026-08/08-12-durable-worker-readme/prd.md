# 补全 durable worker 部署摘要

## Goal

完成增量审计 D1，让 README 准确说明当前 Compose 的 app + durable worker 发布拓扑、
启动门禁和健康检查，并把完整运维细节链接到权威部署文档。

## Requirements

- 将 Compose 顺序从 `migrate -> bootstrap -> app` 更新为
  `migrate -> bootstrap -> app + worker`。
- 明确 `CHAPTER_WORKFLOW_START_ENABLED=true` 时 app 与独立 durable worker 是同一发布
  单元，HTTP readiness 不代表 worker 健康。
- 给出 `python -m app.worker health` 和 `python -m app.worker metrics` 两个发布后检查命令。
- 明确 migrate/bootstrap 是 one-shot，任一失败时 app 和 worker 都不得启动。
- 修正“单容器 supervisord”摘要与当前 Compose 独立 worker 的矛盾，并链接
  `docs/DEPLOYMENT.md`，不复制完整运维手册。

## Out Of Scope

- 不修改 Compose、Dockerfile、worker 实现或 `docs/DEPLOYMENT.md`。
- 不新增部署模式、健康接口或配置项。

## Acceptance Criteria

- [ ] README 的技术架构、Docker 部署和 workflow 开关说明与 `deploy/docker-compose.yml`
  当前 app/worker 依赖图一致。
- [ ] README 明确 one-shot 失败门禁、HTTP/worker 健康区别和 health/metrics 命令。
- [ ] README 链接权威部署文档且没有复制迁移/回滚长篇内容。
- [ ] Markdown 链接、命令和 `git diff --check` 通过人工/机械校验。

