# XState / Vue Runtime Research

Research date: 2026-07-30

## Project Baseline

- Frontend uses npm with lockfile v3; CI uses Node 22 and `npm ci`.
- `frontend/package.json` accepts Node `^20.19.0 || >=22.12.0` and currently uses Vue `^3.5.18`.
- XState, `@xstate/vue`, Playwright and browser/e2e scripts are absent.
- Vitest uses jsdom and scans `src/**/*.{spec,test}.ts`.
- Production builds already emit a Vite manifest and run `scripts/check-bundle-budget.mjs` against gzip bytes.

## Exact Dependency Selection

```text
xstate              5.32.5
@xstate/vue         5.0.1
@playwright/test    1.62.0
```

Registry evidence:

- `@xstate/vue@5.0.1` peer dependencies are `vue ^3.0.0` and `xstate ^5.32.5`.
- `@playwright/test@1.62.0` requires Node `>=20`, compatible with project CI.
- Application package entries must be exact, not caret ranges; lockfile remains authoritative for transitive packages.

Published package integrity recorded during planning:

```text
xstate@5.32.5
sha512-ULazi1oe6wGrXl0Frb6otSlkm5HLifbbVTkMk5kkSKqz4TkxJaVpnl6jOJwKeid3ORPxYyZQgNLUSYX9q65SIA==

@xstate/vue@5.0.1
sha512-SsiIgj+9lnArECyeqcJ+y4JsxcdT/dA8mLaN+lA8sk7TfZM5ASEMk+/2VLho2r/PtRBCg7KZqRstb5MBF7yEWg==
```

## Official Runtime Behavior

Official `statelyai/xstate` source inspected through Gread:

- `packages/xstate-vue/src/useMachine.ts`: `useMachine` is a typed alias over `useActor` and returns reactive `snapshot`, typed `send`, and `actorRef`.
- `packages/xstate-vue/src/useActor.ts`: creates the actor through `useActorRef` and exposes its current snapshot through `useSelector`.
- `packages/xstate-vue/src/useActorRef.ts`: creates one actor, starts it in Vue `onMounted`, stops it in `onBeforeUnmount`, and unsubscribes its observer.

Exact `xstate@5.32.5` declaration evidence:

- `ActorOptions.snapshot?: Snapshot<unknown>` initializes actor logic from a persisted internal state.
- deprecated `ActorOptions.state` remains an alias; new code must use `snapshot` if persistence is needed.
- restored machine actions are not re-executed, while invocations restart.

Sources:

- `https://api.gread.dev/read?name=statelyai/xstate&paths=packages/xstate-vue/src/useMachine.ts,packages/xstate-vue/src/useActor.ts,packages/xstate-vue/src/useActorRef.ts,packages/xstate-vue/package.json`
- `https://registry.npmjs.org/xstate/-/xstate-5.32.5.tgz`
- npm registry metadata for the exact versions above.

## Design Implications

- Use `useMachine`; do not build a parallel manual actor lifecycle wrapper.
- Invoked callback/promise actors must still own their AbortController/unsubscribe cleanup because Vue only stops the actor tree; external resources need actor cleanup functions.
- Product reload recovery should not persist an XState snapshot in localStorage. The durable server snapshot/cursor is newer and authoritative; local persisted machine state would create another recovery fact source.
- The `snapshot` option is useful for focused XState persistence tests, not required for WritingDesk product rehydration.
- Actor context must stay serializable and bounded even without browser persistence, which keeps transition tests deterministic and prevents server entity duplication.

## Browser Test Decision

The repo has no Playwright/Cypress setup. A checked-in Playwright Chromium smoke is preferable to an unreproducible manual-only browser check because this cutover depends on refresh, reconnect, duplicate clicks and ARIA state.

Scope is intentionally narrow:

- one WritingDesk route;
- deterministic API/SSE fixtures;
- desktop and mobile viewports;
- critical lifecycle branches only;
- console/page error assertion;
- managed web server that is stopped after the suite.

## Bundle Measurement

Do not compare npm unpacked package size. Measure browser cost from the actual Vite production graph:

1. run the same Node/npm lock and production build before dependency changes;
2. record manifest-referenced JS raw/gzip totals and WritingDesk route chunk gzip;
3. repeat after cutover;
4. report delta and top chunks;
5. keep existing hard budgets unchanged.

`@playwright/test` is a dev dependency and must not appear in the browser bundle. XState should remain in the lazy WritingDesk route graph; if it enters the initial app chunk unexpectedly, inspect imports before considering any budget change.
