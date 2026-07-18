# PG 部署配置

## Goal

docker-compose 新增 postgres profile，env 新增 `POSTGRES_*` 配置，支持 `docker compose --profile postgres up` 拉起 PG + app。parent: `07-19-migrate-to-postgres`。

## Requirements

- `deploy/docker-compose.yml` 新增 postgres service（`profile: postgres`, `postgres:16-alpine`, 挂卷 `pg-data`, healthcheck `pg_isready`）
- app 环境变量加 `POSTGRES_HOST/PORT/USER/PASSWORD/DATABASE`
- volumes 加 `pg-data`
- `deploy/.env.example` + `backend/env.example` 加 `POSTGRES_*` 段，DB_PROVIDER 注释加 postgresql 选项

## Acceptance Criteria

- [ ] `docker compose --profile postgres up -d` 拉起 PG 容器，健康检查通过
- [ ] app 容器连通 PG（DB_PROVIDER=postgresql）
- [ ] mysql/sqlite 的 compose profile 不受影响（回归不破）
- [ ] env.example 含完整 POSTGRES_* 示例

## Notes

- 技术细节见 parent `design.md` 与 `research/models-vector-test-deploy.md` 第 4 节。
- 依赖：`01-pg-code-connect`（app 需先支持 PG 连通）。
- `task.py start` 前补 `design.md` + `implement.md`。
