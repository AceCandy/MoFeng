# WritingDesk Statechart Implementation Plan

## Preconditions

- [x] Start only after the user approves the latest planning summary and `task.py start` changes this child task to `in_progress`.
- [x] Load all files in `implement.jsonl`; inspect the exact code before editing and preserve unrelated worktree changes.
- [x] Record a clean frontend production bundle baseline before installing XState; do not commit `dist/` or browser downloads.
- [x] Use Node 22-compatible npm tooling and install backend runtime + `requirements-dev.txt` before claiming Python quality gates.

## Phase 1 - Backend Current Lookup And Release Contract

- [x] Add owner-scoped repository lookup with active-first, cross-revision deterministic ordering and terminal fallback that excludes superseded/successor predecessors.
- [x] Add reusable `ChapterWorkflowConnection`, current snapshot service path and bounded concurrent-successor reconciliation.
- [x] Register `GET /chapter-workflows/current` before `/{run_id}` and return connection-or-null without exposing foreign runs.
- [x] Reuse one `events_url` builder for start/current responses; keep existing start and command wire behavior compatible.
- [x] Replace unrestricted snapshot status/version/node fields with complete V1 Literals for workflow status, root-job status, node key and schema versions; add unknown-value failure tests.
- [x] Add focused repository/service/HTTP tests for null, owner isolation, multiple active revisions, terminal ordering, successor exclusion, route precedence and snapshot/cursor response.
- [x] Regenerate `backend/openapi.json` and `frontend/src/api/generated/schema.d.ts`; run byte, ownership and semantic transport checks.
- [x] Normalize frontend OpenAPI npm scripts to the available `python3` interpreter so the documented local gate is executable.
- [x] Keep backend Settings default false; make Compose interpolation require an explicit flag, and update `backend/env.example`, `deploy/.env.example`, provisioning script and deployment docs to set `true` for this release.
- [x] Add a release-config test proving missing Compose configuration fails, explicit true resolves, and the start API remains hidden when false.

Rollback checkpoint: backend remains compatible with the old frontend while the gate is false; revert this phase as one schema/artifact/config unit before any frontend cutover.

## Phase 2 - Workflow API, Decoder And Vue Query Cache

- [x] Add exact `xstate@5.32.5`, `@xstate/vue@5.0.1` and `@playwright/test@1.62.0` entries and update npm lockfile; do not use caret ranges.
- [x] Add generated aliases and one runtime decoder for connection, snapshot, command response and typed 409 detail.
- [x] Define readonly runtime enum lists with a compile-time equality assertion against generated workflow/root-job/node unions, so missing transition values fail type-check.
- [x] Add workflow API functions on the shared HTTP/auth wrapper; consume returned `events_url` through the existing task SSE decoder.
- [x] Add the workflow query-key factory, current query and start/command mutations.
- [x] On 202 and typed 409, atomically update the same current cache before notifying the actor; preserve malformed 409 as a contract error.
- [x] Add decoder/API/query tests for valid, malformed, unsupported-version, null, scope mismatch, 202 and 409 cases.

Rollback checkpoint: the old WritingDesk is still connected; new API/query code has no command owner until Phase 5.

## Phase 3 - Pure Statechart

- [x] Implement typed machine context/events/actors inside the existing composables boundary.
- [x] Implement `booting`, `fatal` and `ready` with parallel workflow/transport regions exactly as documented in `design.md`.
- [x] Implement server status mapping, monotonic scope/run/revision guards and direct `allowed_commands` guards.
- [x] Implement stable command-envelope creation with one command UUID and frozen expected revisions/checkpoint.
- [x] Implement scope change, snapshot reconciliation, connection epoch, reconnect/backoff, reset and polling transitions without importing API/query modules into the pure model.
- [x] Add table-driven Vitest coverage generated from the exhaustive contract lists for every status/event/command, all illegal transitions, duplicate dispatch, stale response and transport/workflow independence.

Rollback checkpoint: pure machine remains unused by the page and can be removed without changing runtime behavior.

## Phase 4 - Vue Actors And Cache Reconciliation

- [x] Wire `useMachine` to injected current-query, mutation, stream and invalidation ports; rely on Vue mount/unmount to start/stop the actor.
- [x] On project/chapter scope change, stop the old stream, increment epoch, reset transient command state and bootstrap the new current query.
- [x] Treat durable task events only as refetch wake-ups; reconcile newer workflow snapshots and ignore old connection/run/revision callbacks.
- [x] Implement atomic cursor reset and bounded reconnect-to-polling fallback.
- [x] Invalidate Chapter/Project only on documented revision/phase boundaries and prove no event-by-event refresh loop.
- [x] Add actor integration tests with fake query/mutation/SSE ports for refresh, disconnect, replay, reset, scope switch, late callbacks, 202/409 races and polling.

Rollback checkpoint: integration is tested independently before it replaces any legacy page owner.

## Phase 5 - WritingDesk Direct Cutover

- [x] Replace WritingDesk generation, evaluation recovery, version selection/finalization, retry and cancel controls with machine selectors/events.
- [x] Map UI disabled/loading/error labels directly from machine snapshot + `allowed_commands`; preserve text and ARIA semantics.
- [x] Implement the PRD state/action table, including waiting-without-candidates, acknowledged external retry, cancelled restart, superseded follow and fatal resync/auth behavior.
- [x] Remove the standalone manual evaluate action; display workflow evaluation and route failures through workflow retry commands.
- [x] Remove `generatingChapter`, `evaluatingChapter`, `chapterGenerationResult`, local lifecycle status writes and rollback mutations.
- [x] Remove the status/content-driven `WDWorkspace` SSE watcher and the old WritingDesk chapter stream/reconnect/cache-upsert path.
- [x] Remove duplicate old mutation wait/refresh chains and orphaned imports/functions only after checking all repository call sites.
- [x] Preserve selected chapter/version, drawer/modal/focus, detail, delete/edit/optimization, sidebar and task-reminder behavior that does not own workflow lifecycle.
- [x] Add/update component tests for controls, labels, ARIA status, no-legacy-endpoint ownership and retained non-workflow behavior.

Phase 5 evidence (2026-07-31): `npm run lint`, `npm run type-check` and `npm run test:unit`
pass (30 files / 257 tests); legacy owner and deleted-file reference scans are empty; independent
review found and the implementation restored the version/evaluation detail modal entry paths.

Rollback checkpoint: do not retain a hidden frontend feature flag. Rollback uses the previous frontend artifact plus the backend compatibility facade.

## Phase 6 - Browser, Bundle And Full Review

- [x] Add exact `playwright.config.ts`, deterministic API/SSE fixtures, managed webServer and a `test:e2e` npm script before invoking the browser gate.
- [x] Cover current-null start, waiting refresh/no-candidate guard, disconnect/replay, duplicate click, stale event, projection retry, acknowledged external retry, cancelled restart, superseded follow, fatal contract error and ARIA-visible status.
- [x] Run a real browser screenshot/DOM/console review at desktop and mobile WritingDesk viewports; stop every started service afterward.
- [x] Run an automated rollout drill with gate=true through the legacy facade and new current/command API; assert one run/command/canonical outcome.
- [x] Run the rollback drill with a previous-frontend facade fixture and gate=false while an active durable run drains; assert no second legacy job/outcome and record only public correlation ids/counts in `research/rollout-rollback-drill.md`.
- [x] Build production assets and compare total/route-chunk gzip against the recorded baseline; keep current hard budgets unchanged.
- [x] Run the full validation matrix below, inspect `git diff --check`, tracked/untracked files and generated artifact drift.
- [x] Perform an independent full-scope review against `check.jsonl`, PRD AC1-AC13 and the rollout/rollback sequence; fix findings and re-run affected gates.

Phase 6 evidence (2026-07-31): PostgreSQL focused tests pass (34); frontend lint,
type-check, unit tests (30 files / 262 tests), generated contract drift, production build
and Playwright (20 desktop/mobile runs) pass. Rollout/rollback and browser review evidence
lives in `research/rollout-rollback-drill.md` and `research/browser-review.md`. Final gzip
is 446.93 KB JS, 85.19 KB CSS and 49.37 KB for the WritingDesk route chunk. Independent
review findings for canonical UUID decoding and complete current ordering coverage were
fixed and their affected gates rerun. Playwright-managed services exited after the run.

## Validation Commands

Backend focused tests and quality:

```bash
cd backend
python3 -m pytest -q \
  tests/test_chapter_workflow_http.py \
  tests/test_chapter_workflow_compatibility_http.py \
  tests/test_chapter_workflow_start.py \
  tests/test_chapter_workflow_release_contract.py \
  tests/test_openapi_contract.py
python3 -m ruff check app tests/test_chapter_workflow_http.py tests/test_openapi_contract.py
python3 -m black --check app tests/test_chapter_workflow_http.py tests/test_openapi_contract.py
python3 -m mypy app/api/routers/writer.py app/repositories/chapter_workflow_repository.py \
  app/schemas/chapter_workflow.py app/services/job_service.py
```

Generated transport:

```bash
cd frontend
npm run api:check
```

Frontend unit/static/build gates:

```bash
cd frontend
npm run lint
npm run type-check
npm run test:unit
npm run build
```

Browser gate:

```bash
cd frontend
npx playwright install chromium
npm run test:e2e
```

Release configuration and owner drill:

```bash
cd backend
python3 -m pytest -q \
  tests/test_chapter_workflow_compatibility_http.py \
  tests/test_chapter_workflow_release_contract.py
cd ..
docker compose --env-file deploy/.env.example -f deploy/docker-compose.yml config >/dev/null
```

Repository hygiene and Trellis validation:

```bash
git diff --check
git status --short
python3 ./.trellis/scripts/task.py validate \
  .trellis/tasks/07-27-writing-desk-statechart
```

If a command cannot run because the local environment lacks dependencies or PostgreSQL, record that exact gap; do not substitute a weaker check and call the acceptance criterion complete.

## Risky Files / Review Hotspots

- backend workflow repository/service/router/schema and generated OpenAPI artifacts;
- deploy Compose/env/provisioning files because a missing gate can break the release unit;
- shared task SSE decoder/subscription boundary and `HttpRequestError.payload` conflict decoding;
- `WritingDesk.vue`, `WDWorkspace.vue`, workflow-related composables and legacy novel mutations;
- package/lock/config files for exact XState/Playwright versions and bundle impact.
