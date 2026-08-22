# 全仓技术债治理集成复核计划

1. 激活父任务，复核 8 个归档子任务的顺序、材料、提交与已记录风险。
2. 依据既有 validation/journal 证据，补勾 `08-22-converge-auth-http-client` 与 `08-22-tighten-frontend-boundary-types` 遗漏的 PRD 验收框；不改写其他历史材料。
3. 在当前产品 HEAD 执行后端集成门禁：
   - `cd backend && .venv/bin/python -m pytest -m "not postgres" --strict-markers`
   - `cd backend && .venv/bin/python -m pytest -m postgres --strict-markers`
   - `cd backend && .venv/bin/ruff check app tests`
   - Pydantic v2 目标测试使用 `PydanticDeprecatedSince20` warnings-as-error。
4. 复用最后一个子任务后、同一产品 HEAD 上已通过的前端证据：`npm run type-check`、`npm run test:unit`、`npm run lint`、`npm run build`；若产品文件发生变化则全部重跑。
5. 精确扫描已治理的 Pydantic v1 写法、目标前端 `any`、认证 HTTP 重复边界、提醒死链与 `base.css` 失效引用。
6. 将命令结果和剩余风险写入 `research/integration-validation.md`，完成独立只读复核。
7. 勾选父 PRD 验收项，运行 Trellis 校验与 `git diff --check`，按提交计划提交、归档并记录 journal。

## Rollback Point

父任务不修改产品代码；若集成复核不能通过，只撤销本任务的文档/验收状态修改并保留 8 个已归档子任务。
