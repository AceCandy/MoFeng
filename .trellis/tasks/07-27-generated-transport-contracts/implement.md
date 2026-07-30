# Generated Transport Contracts Implementation Plan

## Success Sequence

### 1. Lock Current Contract Evidence

- [x] Record the current OpenAPI counts, operationId set and in-scope endpoint/model map in focused tests.
- [x] Record the sorted current 110 operation-ID SHA256, then add failing tests for deterministic method selection, missing SSE components, exporter hermeticity and duplicate generated DTO ownership.
- [x] Confirm excluded dynamic/file/SSE framing endpoints remain explicitly out of scope.

Verify: new tests fail for the intended current gaps, not because a database/server is unavailable.

### 2. Build Backend OpenAPI Infrastructure

- [x] Add the legacy-compatible stable operationId generator, reject multi-method routes, preserve explicit compatibility IDs and enforce application-wide uniqueness.
- [x] Add custom OpenAPI component registration for snapshot/task/reset payloads.
- [x] Add `schema_version: Literal[1]` to the three public SSE data payload models and preserve public allowlists.
- [x] Add the hermetic `python -m app.openapi_export` write/check CLI and canonical serializer.
- [x] Generate and commit `backend/openapi.json`.

Verify: exporter runs with schema-valid non-sensitive sentinels, does not enter lifespan/DB, produces identical bytes twice, rejects unsupported diff constructs, preserves the current 110-ID set, and all operations/components satisfy tests.

Rollback point: backend OpenAPI module, schema-version additions and artifact form one reversible unit; no database changes exist.

### 3. Wire The Fixed Frontend Generator

- [x] Add exact `openapi-typescript: 7.13.0` to `frontend/package.json` and reconcile the lockfile.
- [x] Add `api:export`, `api:generate` and `api:check` scripts using activated `python` plus identical generator flags.
- [x] Generate and commit `frontend/src/api/generated/schema.d.ts` without post-processing its built-in header.

Verify: two `npm run api:generate` runs are byte-identical and `npm run api:check` is read-only/successful.

### 4. Migrate Domain Types In Order

- [x] Expand: add generated aliases under the existing exported type names without changing URL, payload or consumer imports.
- [x] Cut over workflow request/snapshot/command DTO mirrors to generated aliases.
- [x] Cut over task/list/snapshot/event/reset DTO mirrors to generated aliases.
- [x] Make novel/admin Chapter reads share the generated `components['schemas']['Chapter']` alias; remove `AdminChapter` union after consumers compile.
- [x] Cut over chapter projection and ordinary admin request/response DTO mirrors in scope.
- [x] Contract: prove no old structural declarations/imports remain, then remove them.
- [x] Update query/component imports without changing field semantics or introducing speculative mappers.
- [x] Add the TypeScript-AST ownership check for the migrated schema-name allowlist.

Verify after each domain: focused type-check/tests pass and no structural hand-written duplicate remains.

Rollback point: before contract cleanup, the same-name alias is the source adapter and each domain can restore its prior declaration without runtime dual execution; the final task must not ship mixed duplicate ownership.

### 5. Harden The SSE Boundary

- [x] Implement one decoder family accepting `unknown` for snapshot/task/reset; HTTP and SSE snapshot paths reuse the same function.
- [x] Route valid values to the existing cursor/reset/cache flow.
- [x] Ignore unknown outer events and reject unknown version/malformed v1 before state mutation.
- [x] Implement same-scope snapshot resync, repeated-failure safe error and polling fallback behavior.
- [x] Add unit tests for valid SSE/HTTP snapshot, task/reset, malformed, unsupported-version, reconnect and no-cache-mutation cases.

Verify: no `message.data as BackgroundTask*` remains, invalid payloads cannot invoke handlers/reducer, and existing cursor/reset tests continue to pass.

### 6. Add Cross-Layer CI

- [x] Add the dedicated path-filtered transport contract workflow with full git history, Python and Node setup.
- [x] Run exporter/backend tests, `api:check`, ownership/decoder tests, type-check and lint.
- [x] Install `oasdiff 1.26.1` from the exact Linux archive and verify the pinned SHA256 from the official checksum list.
- [x] Compare PR base/current canonical artifacts from repository root using the explicit base SHA, `$RUNNER_TEMP` file cleanup, ERR-level blocking and review annotations.
- [x] Cover the first-baseline branch explicitly; do not silently skip comparisons after the artifact exists.

Verify: locally exercise a stale artifact failure; in a temporary test branch/artifact fixture prove response-field removal and required request-field addition fail semantic comparison.

### 7. Update Specs And Perform Independent Review

- [x] Update backend quality/durable SSE, frontend directory/type-safety, cross-layer and code-reuse specs to describe generated ownership and versioned decoder behavior.
- [x] Run an independent read-only review against PRD/design/specs after implementation; main implementation owner resolves verified findings.
- [x] Inspect the final diff for generated noise, secrets, absolute paths, caches, temporary reports or binaries.

Verify: Trellis quality check passes and all acceptance criteria map to tests, commands or explicit CI behavior.

## Validation Commands

Backend focused checks from `backend/` with the backend virtual environment activated:

```bash
python -m pytest -q \
  tests/test_openapi_contract.py \
  tests/test_task_event_sse.py
# Requires a usable Docker socket for its container-backed fixture.
python -m pytest -q tests/test_chapter_workflow_http.py
python -m ruff check app/openapi_schema.py app/openapi_export.py tests/test_openapi_contract.py
python -m black --check app/openapi_schema.py app/openapi_export.py tests/test_openapi_contract.py
python -m mypy app/openapi_schema.py app/openapi_export.py
python -m compileall -q app
```

Frontend checks from `frontend/`:

```bash
npm run api:generate
npm run api:check
npm run test:unit -- src/queries/__tests__/tasks.spec.ts
npm run type-check
npm run lint
```

Repository checks:

```bash
python3 ./.trellis/scripts/task.py validate .trellis/tasks/07-27-generated-transport-contracts
git diff --check
git status --short
```

CI-only semantic gate uses the checksum-verified `oasdiff 1.26.1` binary against the pull-request base artifact. Local execution is optional when the same pinned binary is available; CI is authoritative.

## Validation Evidence (2026-07-30)

- Backend OpenAPI and task SSE suites: 15 tests passed. Ruff, Black check, mypy,
  and `compileall` passed; 64 existing Pydantic deprecation warnings remain.
- Frontend: `npm run api:check`, all 25 unit-test files (177 tests), type-check,
  and lint passed.
- Two consecutive generation runs were byte-identical. SHA256 values:
  `backend/openapi.json` =
  `da6770e6948dfe24833c5e1d9872f628fb5dcfccdc29ae4b1a619cbc4e9b543b`;
  `frontend/src/api/generated/schema.d.ts` =
  `f3fe5d1350b2ab71e1030374ddb02e65c463155520aa8d25e8f9ee8ca203799b`.
- A stale exporter check exited `1` and left both artifact hashes unchanged.
  The pinned `oasdiff` exited `1` for both a removed required response field and
  an added required request field.
- Independent backend/frontend/spec/hygiene reviews found no unresolved contract
  drift after fixing scope mismatch and superseded-connection callback handling.
- Environment limits: three container-backed chapter workflow HTTP tests stopped
  in fixture setup with Docker socket `PermissionError: 13`; no business assertion
  ran. `actionlint` is not installed, so the workflow was not checked by that tool.
  CI remains authoritative for these two environment-dependent checks.

## Risk Register

| Risk | Control |
| --- | --- |
| Toolchain rollout renames operationIds | Golden 110-ID equality, legacy-compatible deterministic method selection, explicit old-ID adapter for later function renames |
| Import-time settings leak into artifact | Process-local schema-valid sentinels, metadata normalization, sentinel/path tests |
| OpenAPI says more than SSE actually guarantees | Register data payload components only; keep framing tests/protocol docs separate |
| Generated types spread unreadable indexes | Domain-local aliases at API boundary |
| Runtime decoder becomes a second DTO mirror | Validate only untrusted boundary and reducer-critical fields; return generated aliases; no separate interface declarations |
| Semantic tool misses OpenAPI 3.1 features | Reject known unsupported constructs and pin/checksum the evaluated version |
| CI base artifact unavailable | One-time explicit bootstrap only; fail closed after baseline |
| Tool/download outage tempts gate bypass | Exact binary cache/retry; no “temporarily disable” path |

## Final Completion Gate

- [x] Every AC in `prd.md` has evidence.
- [x] `npm run api:check` and focused backend OpenAPI tests pass from a clean working tree.
- [x] Generated and canonical artifacts contain no environment or private data.
- [x] No product service was started; if any diagnostic server is started later, it is stopped before handoff.
- [x] No database migration/data mutation, remote push or unrelated cleanup occurred.
