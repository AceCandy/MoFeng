# CI 拦截 components/views @/api value import（修 AppShell TaskAPI）

## Goal

L26a gap：components/views 仍有 @/api value import（AppShell.vue:19 TaskAPI），ESLint no-restricted-imports 未拦截（type import 预存warning放行）。status===401 已收敛(client.ts:8)✅。需：1) 看 eslint.config.js no-restricted-imports 配置为何没拦 TaskAPI value import；2) 规则覆盖 value import；3) 修 AppShell TaskAPI 用法（移到 @/queries composable 层或 props 传入）。

## Requirements

- components/views 的 @/api value import 全部下沉到 @/queries/@/utils 层，ESLint 规则升级为 error 拦截。

## Acceptance Criteria

- [x] eslint 规则升级 @typescript-eslint/no-restricted-imports + allowTypeImports:true + severity error
- [x] components/views 的 @/api value import 全部下沉（AppShell TaskAPI->useTaskStream / SettingsManagement normalizeComparableVersion->@/utils/version / InspirationMode HttpRequestError->@/utils/errors）
- [x] type import 放行不误报（probe 验证）
- [x] 三件套绿：eslint 0 error + vue-tsc 0 + vitest 152 passed

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
