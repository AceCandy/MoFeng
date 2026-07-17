# CI 拦截 components/views @/api value import（修 AppShell TaskAPI）

## Goal

L26a gap：components/views 仍有 @/api value import（AppShell.vue:19 TaskAPI），ESLint no-restricted-imports 未拦截（type import 预存warning放行）。status===401 已收敛(client.ts:8)✅。需：1) 看 eslint.config.js no-restricted-imports 配置为何没拦 TaskAPI value import；2) 规则覆盖 value import；3) 修 AppShell TaskAPI 用法（移到 @/queries composable 层或 props 传入）。

## Requirements

- TBD

## Acceptance Criteria

- [ ] TBD

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
