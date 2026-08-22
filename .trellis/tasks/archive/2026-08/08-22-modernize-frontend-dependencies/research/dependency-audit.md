# 前端依赖审计基线（2026-08-22）

- `npm audit --json`：12 个漏洞，1 low、8 high、3 critical；均位于开发工具链。
- `npm audit --omit=dev --json`：0 个生产依赖漏洞。
- `npm audit fix --dry-run`：普通修复可收敛漏洞，不需要 `--force`，预计更新 39 个包。
- 直接受影响依赖：Vite 7.1.9、Vitest 3.2.4；修复链包含 Rollup、tar、shell-quote、ws、js-yaml 等。
- `npm outdated --json`：约 36 个直接依赖不是 latest；主要主版本包括 Vite 8、Vitest 4、TypeScript 7、Vue Router 5、Pinia 4、jsdom 30、marked 18。
- Node 现状：本地 24.15.0，CI 22，Docker 20，`engines` 为 `^20.19.0 || >=22.12.0`。
- jsdom 30 与 npm-run-all2 9 要求 `^22.22.2 || ^24.15.0 || >=26`，因此现有 Docker Node 20 不支持完整 latest 集合。

