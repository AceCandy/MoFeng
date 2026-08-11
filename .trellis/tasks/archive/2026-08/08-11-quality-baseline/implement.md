# 实施计划

## 1. 基线重测

- 确认 Docker、backend `.venv`、frontend `node_modules` 与 Playwright Chromium 可用性。
- 依次运行后端 pytest、ruff、Black check、scoped mypy、compileall。
- 依次运行前端 api:check、lint、type-check、unit、build、Playwright。
- 将退出状态、失败数量、首个可操作根因和环境阻塞写入 `research/baseline-2026-08-11.md`。

## 2. 后端行为失败

- 对每个 pytest 失败先运行最小复现，再读取实现与调用链。
- 修复生产错误或更新漂移断言；禁止 skip/xfail/retry。
- 每个根因 focused test 通过后重新运行后端全量 pytest。

## 3. 后端静态与格式基线

- 先修 ruff `F`/语义问题并验证相关测试。
- 单独执行 import 排序，复跑 ruff 与 pytest。
- 单独执行 Black `app tests`，确认 diff 只有机械格式化；复跑 pytest、ruff、Black check、
  scoped mypy 和 compileall。

## 4. 前端与浏览器基线

- 修复 api:check、eslint、vue-tsc、Vitest 或 build 的实际失败。
- 运行单个 Playwright 项目/场景定位 fixture、selector 或产品行为根因。
- 保留现有 role/live-region/heading 断言；若页面装配条件让状态面板在受支持阶段消失，
  修复生产装配条件，不通过改 selector 或降低断言规避。
- desktop/mobile 项目全部通过后，重新运行前端静态门和 build。

## 5. 最终质量门与复核

```bash
cd backend
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check app tests
.venv/bin/python -m black --check app tests
.venv/bin/python -m mypy
.venv/bin/python -m compileall -q app

cd ../frontend
npm run api:check
npm run lint
npm run type-check
npm run test:unit
npm run build
npm run test:e2e
```

- 独立复核失败归因、提交边界、无跳过策略和测试产物清理。
- 更新 PRD 验收项；规范只有出现可复用的新约定时才修改。

## Rollback Points

- pytest 每个独立根因修复后形成绿点。
- ruff 语义、import 排序、Black、前端 E2E 分别形成可回滚批次。
- 不在存在未归因失败时继续下一批机械改动。
