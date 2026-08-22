# 前端依赖现代化与安全升级

## Goal

消除前端依赖审计漏洞，并将直接依赖升级到当前运行时可可靠支持的最新版本；通过分批验证和独立回滚，避免一次性主版本升级掩盖兼容问题。

## Background

- `npm audit` 报告 12 个开发工具链漏洞（1 low、8 high、3 critical），生产依赖审计为 0。
- 普通 `npm audit fix` 可修复现有漏洞，不需要 `--force`。
- 约 36 个直接依赖存在更新，其中 Vite、Vitest、TypeScript、Vue Router、Pinia、jsdom、marked 等涉及主版本迁移。
- 当前 Node 基线不一致：CI 使用 Node 22、部署镜像使用 Node 20、本地为 Node 24.15.0；部分最新依赖已不支持当前 Docker 的 Node 20。

## Requirements

- R1. 按下表顺序逐项规划、批准、实现、检查、提交和归档；父任务只负责协调与最终集成复核。
- R2. 安全修复必须先完成，禁止使用 `npm audit fix --force`，不得通过忽略审计结果伪造完成。
- R3. 同主版本更新与主版本迁移分开，任何一批失败时都能独立回滚。
- R4. Node、CI、Docker 与 `@types/node` 必须对齐；“最新”指最新兼容版本，不以版本号最大为目标。
- R5. 不放宽 TypeScript 严格模式、测试要求或 bundle 预算，不顺带修改后端 Python 依赖或无关产品代码。
- R6. 对只被单个脚本使用的 `npm-run-all2`，先评估原生 npm 串行脚本；原生脚本满足现有行为时删除该依赖。

## Ordered Task Map

| 顺序 | 子任务 | 交付物 | 主要验证 |
|---:|---|---|---|
| 1 | `08-22-fix-frontend-audit-vulnerabilities` | 安全补丁与锁文件收敛 | `npm audit`、完整前端门禁 |
| 2 | `08-22-upgrade-frontend-compatible-dependencies` | 所有同主版本直接依赖更新 | outdated 清单、完整前端门禁 |
| 3 | `08-22-align-node-and-build-toolchain` | Node 基线及 Vite/Vitest/TypeScript/jsdom 工具链迁移 | `npm ci`、工具链门禁、构建与冒烟 |
| 4 | `08-22-upgrade-frontend-framework-majors` | Vue Router、Pinia、marked 等剩余主版本迁移 | 聚焦回归、完整前端门禁、浏览器冒烟 |

## Acceptance Criteria

- [ ] 4 个子任务均按顺序独立规划、批准、验证、提交和归档。
- [ ] `npm audit` 与 `npm audit --omit=dev` 均报告 0 个漏洞。
- [ ] 直接依赖均处于最新兼容版本；保留的非 latest 项有明确的运行时或 peer 兼容证据。
- [ ] CI、Docker、`engines.node` 与 `@types/node` 使用一致的 Node 24 基线，最低版本满足所有依赖要求。
- [ ] `npm ci` 可从锁文件复现安装，API artifact、类型检查、单测、lint、生产构建和 bundle 预算均通过。
- [ ] 登录、AppShell、写作台编辑器完成浏览器冒烟，未发现依赖升级引入的可见回归。
- [ ] 父任务完成跨批次集成复核并记录未验证项与剩余风险后才归档。

## Out of Scope

- 后端 Python 依赖、业务功能、UI 重设计或无关重构。
- 为追求版本号最大而采用与真实 Node 运行时不匹配的类型包。
- 自动合并所有主版本升级为一个不可分辨、不可独立回滚的变更。

