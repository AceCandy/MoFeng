# 恢复质量基线

## Goal

把当前后端与前端的测试、静态检查、格式检查和浏览器测试恢复为可重复的零失败基线，
使后续 R1 能把同一组命令升级为阻断式发布门禁，而不是在已知红灯上叠加假门禁。

## Requirements

- 开始修复前重新运行并记录当前基线；设计文档中的旧失败数量只作为历史证据，不能替代
  本任务的实测结果。
- 后端全量 pytest 必须零失败。逐项区分生产行为错误、测试断言漂移和非隔离环境依赖；
  不得通过 skip、xfail、retry 或放宽关键断言消除失败。
- `ruff check app tests` 必须为零。语义问题与 import 排序分批处理，避免机械 diff 掩盖
  行为修改。
- `black --check app tests` 必须为零。Black 仅作为独立机械批次执行，保持
  `backend/pyproject.toml` 对 Alembic 历史 revision 的排除规则。
- mypy 继续使用 `backend/pyproject.toml` 当前 durable workflow/job 限定范围；不得扩展为
  全后端检查，也不得把结果表述为全后端已类型检查。
- 前端 `api:check`、lint、type-check、unit、build 必须零失败；生产组件不能迁就过时的
  fixture 或重复声明 transport contract。
- Playwright 的 desktop/mobile Chromium 项目必须全部通过。测试优先使用现有 role/name
  语义；只有当前 DOM 确实缺少稳定语义锚点时，才给生产组件补最小可访问名称。
- 浏览器 fixture 必须模拟当前 API/SSE 契约；外部服务、时间或环境依赖导致的不稳定测试
  必须改成 hermetic fixture，不得用重试掩盖确定性失败。
- 每个修复批次都保留可独立验证和回滚的边界；任务结束时不得遗留测试服务、容器、
  screenshot、trace、video、HTML report 或临时日志。

## Out Of Scope

- 不处理 Python/npm advisory、依赖升级、hash lock、镜像扫描或发布 workflow；这些属于 R1。
- 不实施 U1 的 modal/写作台可访问性增强，不新增 axe 场景。
- 不扩大 mypy 范围，不重构业务架构，不顺带清理未被质量门发现的历史技术债。
- 不修改 Alembic 历史 revision 的格式。

## Acceptance Criteria

- [x] 已记录 2026-08-11 当前基线，包含每条命令的退出状态、失败数量和归因分类。
- [x] 后端全量 pytest、`ruff check app tests`、`black --check app tests`、限定范围 mypy、
      `compileall` 全部退出 0。
- [x] 前端 `api:check`、lint、type-check、unit、build 全部退出 0。
- [x] Playwright desktop/mobile Chromium 全部通过；当前套件为 20/20，且未启用 retry。
- [x] 没有新增 skip、xfail、永久 ignore、`continue-on-error` 或削弱关键断言。
- [x] 行为修复、ruff/import 和 Black 机械格式化保持独立提交边界。
- [x] 独立复核确认全量命令真实执行，工作树无测试运行产物。
