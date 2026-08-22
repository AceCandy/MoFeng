# 修复前端依赖审计漏洞

## Goal

用非强制安全补丁将前端依赖审计从 12 个漏洞降为 0，并保持现有产品与工具链主版本。

## Requirements

- 仅执行普通 `npm audit fix` 或等价的精确安全版本更新，禁止 `--force`。
- 修改范围限于前端依赖声明与锁文件；不迁移主版本、不顺带重构产品代码。
- 保存修复前后 audit 结果，确认生产依赖持续为 0 个漏洞。
- 完整前端门禁通过后才可提交和归档。

## Acceptance Criteria

- [x] `npm audit` 与 `npm audit --omit=dev` 均为 0。
- [x] Vite、Vitest 及传递依赖落在当前主版本的安全版本。
- [x] API check、type-check、完整单测、lint、build 和 bundle budget 均通过。
- [x] 锁文件 diff 只包含安全修复所需收敛，且可由 `npm ci` 复现。

## Out of Scope

- 任何主版本迁移、Node 基线调整或产品行为修改。

## Verification

- `npm audit fix`：更新 39 个包，12 个漏洞收敛为 0，未使用 `--force`。
- `npm ci`：从锁文件安装 461 个包，审计为 0。
- `npm audit`、`npm audit --omit=dev`：均为 0。
- `npm run api:check`、`npm run type-check`、`npm run lint`：通过。
- `npm run test:unit`：44 个测试文件、348 个测试全部通过。
- `npm run build`：Vite 7.3.6 构建及 bundle budget 通过；JS 总 gzip 556.07 KB，CSS 总 gzip 82.04 KB。
- `git diff --check`：通过；独立复核确认 tracked diff 仅 `frontend/package-lock.json`，无主版本迁移或异常依赖来源。

## Unverified and Remaining Risk

- 未执行真实浏览器冒烟或生产部署验证；本批只更新开发工具链锁文件，现有完整测试与构建门禁已覆盖约定范围。
- 后续同主版本与主版本升级仍由其他子任务独立处理。
