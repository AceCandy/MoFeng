# Generated Transport Contracts Design

## 1. Architecture

```text
backend Pydantic request/response models
  -> FastAPI app + stable operationId + explicit SSE payload components
  -> python -m app.openapi_export
  -> backend/openapi.json                         (committed canonical source artifact)
  -> openapi-typescript 7.13.0 --alphabetize
  -> frontend/src/api/generated/schema.d.ts      (committed generated artifact)
  -> domain-local aliases + SSE runtime decoder
  -> src/api methods -> queries -> UI/statechart
```

The two committed artifacts are a release unit. Runtime/frontend builds never need a live backend or remote schema service.

## 2. Artifact Ownership

| Artifact | Owner | Mutation rule |
| --- | --- | --- |
| Backend Pydantic schemas | `backend/app/schemas/*` | Human-authored wire source of truth |
| `backend/openapi.json` | exporter | Generated only; canonical JSON |
| `frontend/src/api/generated/schema.d.ts` | `openapi-typescript` | Generated only; built-in DO NOT EDIT header |
| Domain aliases | `frontend/src/api/<domain>.ts` | May index generated `components`/`operations`; may not repeat fields |
| Runtime decoder | task SSE boundary | Human-authored validation of untrusted JSON; returns generated aliases |
| UI/domain models | feature owner | Separate only when UI shape genuinely differs; mapper required |

Generated `paths`/`components` indexing stays at the API boundary. Components and queries consume readable domain aliases rather than embedding generated lookup expressions throughout the UI.

## 3. Backend OpenAPI Module

Add a focused module such as `backend/app/openapi_schema.py` with three responsibilities:

1. `stable_operation_id(route: APIRoute) -> str`
2. building/caching the application OpenAPI document with explicitly registered extra models
3. canonical document validation shared by runtime schema and exporter tests

`backend/app/main.py` passes `stable_operation_id` through `FastAPI(generate_unique_id_function=...)`, includes routers, then installs the custom OpenAPI builder. Business routers do not each hand-author operation IDs.

### Stable operationId

The first rollout is compatibility-preserving. For the existing single-method routes, the app-level generator deliberately reproduces FastAPI `0.110.0` output:

```text
method = the only route method, lowercased
raw = route.name + route.path_format
prefix = replace every non-word character in raw with "_"
operationId = prefix + "_" + method
```

Constraints:

- a route with zero or multiple methods fails immediately and must be split into one `APIRoute` per operation;
- an explicit `route.operation_id` is retained verbatim and participates in the same uniqueness check;
- route registration order and process hash seed are excluded because no unordered set element is selected;
- all generated operations are scanned after schema build; missing/duplicate IDs raise instead of relying on FastAPI warnings;
- a golden assertion compares SHA256 of the sorted current 110-ID set to `18f9fcb2944270ab91d2fdbf3e4e552b891e4e56d7925cb9079484ef12c60aa2`, so the toolchain rollout cannot silently rename external contracts without carrying a 110-line runtime registry.

Function name remains part of the legacy-compatible ID. Therefore a later internal function rename is treated as a contract change: first set the old value explicitly as a compatibility adapter, then rename the function. A genuine operationId rename requires a separate consumer inventory and expand/cutover/contract approval. This preserves current consumers without committing a 110-entry registry.

### Extra SSE components

FastAPI only discovers models referenced by request/response fields. The OpenAPI builder explicitly registers:

- `BackgroundTaskSnapshotResponse`
- `BackgroundTaskEventResponse`
- `BackgroundTaskCursorResetResponse`

Pydantic `$defs` are merged into `components.schemas` with OpenAPI-compatible refs. A same-name/different-schema collision fails closed. The builder does not add dummy paths and does not claim that an SSE stream is one JSON body.

### Unsupported semantic-diff features

`oasdiff 1.26.1` does not fully resolve `$dynamicRef`/`$dynamicAnchor` and drops `components.pathItems`. A backend contract test rejects these constructs in the canonical artifact until the pinned tool version is deliberately upgraded and re-evaluated.

## 4. Hermetic Exporter

Add `backend/app/openapi_export.py` with:

```text
python -m app.openapi_export [--output openapi.json]
python -m app.openapi_export --check [--output openapi.json]
```

The module overwrites the relevant process-local environment with fixed, schema-valid, non-sensitive sentinels before lazily importing `app.main`:

```text
SECRET_KEY=mofeng-openapi-contract-sentinel-000000000000000000000000
ENVIRONMENT=development
BOOTSTRAP_CREATE_DEFAULT_ADMIN=false
DATABASE_URL=postgresql+asyncpg://openapi:openapi@127.0.0.1:1/openapi_contract
```

The key is a public test sentinel, not a runtime credential. The database URL is syntactically valid but targets an unused local port. The exporter calls `app.openapi()` directly, so ASGI lifespan never starts and the URL is never connected; no DB readiness/bootstrap/preload runs.

Canonicalization rules:

- normalize only environment-sensitive root metadata to project constants;
- preserve every path, component, constraint, description and extension;
- serialize with deterministic key order and indentation;
- UTF-8 output with exactly one trailing newline;
- resolve the output path explicitly and never include it in the document;
- write through a same-directory temporary file plus atomic replace so one artifact is never truncated;
- `--check` computes bytes in memory, compares the committed file, emits a concise error and exits non-zero without rewriting it.

Tests set recognizable SECRET/DB/path sentinels and assert none are present. Calling the exporter twice must return identical bytes.

## 5. Frontend Generation

Declare the exact devDependency:

```json
"openapi-typescript": "7.13.0"
```

Use these concrete package scripts from `frontend/`; they call the activated backend Python as `python`, not a POSIX-only `.venv/bin/python` path:

```json
{
  "api:export": "cd ../backend && python -m app.openapi_export --output openapi.json",
  "api:generate:types": "openapi-typescript ../backend/openapi.json --alphabetize --output src/api/generated/schema.d.ts",
  "api:generate": "npm run api:export && npm run api:generate:types",
  "api:check:openapi": "cd ../backend && python -m app.openapi_export --check --output openapi.json",
  "api:check:types": "openapi-typescript ../backend/openapi.json --alphabetize --output src/api/generated/schema.d.ts --check",
  "api:check": "npm run api:check:openapi && npm run api:check:types"
}
```

The exporter atomically replaces `backend/openapi.json`; the standard generator owns its output write unchanged so `--check` remains authoritative. The pair is intentionally sequential rather than pretending to be a cross-process transaction. If type generation fails after OpenAPI export, the command exits non-zero and the stale frontend artifact remains visibly different; the read-only `api:check` cannot rewrite either file.

`openapi-typescript` already prepends its own generated-file warning. No wrapper or post-processing step modifies the file, because its `--check` performs an exact byte comparison.

## 6. Type Migration

Migration follows expand -> cutover -> contract. First add the generated artifacts and same-name aliases without changing HTTP behavior. Then migrate consumers in this order:

1. workflow request/snapshot/command aliases;
2. task/list/snapshot/event/reset aliases;
3. canonical Chapter alias used by user and admin reads;
4. chapter projection aliases;
5. remaining ordinary admin request/response aliases.

An API module may preserve its existing exported symbol name with a readable alias such as:

```ts
export type Chapter = components['schemas']['Chapter']
```

It may not restate the object fields. `admin.ts` imports/re-exports the canonical Chapter alias rather than declaring an admin subset, so `queries/novel.ts` returns one type. Only after all imports compile against aliases does the contract step remove the old structural declarations. These aliases are the source-compatibility adapter; no runtime feature flag or dual HTTP path is needed because URLs and wire fields do not change.

Use the TypeScript compiler parser in a focused ownership check to reject structural `interface`/object-literal type declarations for the migrated schema-name allowlist in `frontend/src/api/*`. Indexed-access aliases into the generated module are allowed. This adds no runtime dependency and prevents manual DTOs from growing back.

## 7. SSE Version And Decoder

The three state-bearing outer events map exactly to versioned payload models:

| Outer SSE event | Payload model | Other use |
| --- | --- | --- |
| `snapshot` | `BackgroundTaskSnapshotResponse` | Also the JSON response of `GET /api/tasks/snapshot` |
| `task` | `BackgroundTaskEventResponse` | SSE only |
| `reset` | `BackgroundTaskCursorResetResponse` | SSE only |

Each gains `schema_version: Literal[1]`. The terminal `error` event remains the existing bounded `{detail}` transport error and is converted to `Error` by the shared stream reader before task state handlers; it does not enter cache/reducer/statechart.

The decoder accepts `unknown` and returns a discriminated result:

```text
ok(value)
unsupported_version(version)
malformed(reason_code)
ignored_unknown_event
```

Rules:

- JSON parsing alone is not validation;
- version, outer SSE event name and every reducer-critical field are narrowed before a generated alias is returned;
- `TaskAPI.getSnapshot` requests `unknown` and reuses the same snapshot decoder as outer SSE `snapshot` before returning data to Vue Query;
- `event_type` inside a task event remains an open string so new durable event names are forward-compatible;
- an unknown outer SSE event is ignored without mutating state;
- malformed v1 or unsupported versions never reach cache/reducer/statechart;
- first failure requests a fresh snapshot for the same authenticated scope and reconnects from the new cursor;
- if the new snapshot is also unsupported/malformed, close the stream, surface a bounded safe error and retain long-polling fallback;
- existing cursor dedupe, reset replacement and user/scope clearing rules remain unchanged.

OpenAPI components describe only JSON data payloads. `id:`, `event:` and `data:` line framing remains protocol behavior in the streaming code/tests.

## 8. CI Gates

Add `.github/workflows/transport-contract-ci.yml` rather than making backend-only schema changes run the complete frontend build workflow. Do not define a workflow-wide `defaults.run.working-directory`; every step owns its cwd explicitly.

Path triggers include:

- `backend/app/main.py`, OpenAPI modules, `backend/app/api/routers/**`, `backend/app/schemas/**`;
- `backend/openapi.json`, `backend/requirements*.txt`, `backend/pyproject.toml`, backend test/config files and focused tests;
- `frontend/package.json`, lockfile, `src/api/**`, query consumers, generated artifact and contract scripts/tests;
- the transport workflow itself.

The job:

1. checks out full history;
2. sets up Python and Node with dependency caches;
3. installs `requirements-dev.txt` and runs pytest with `working-directory: backend`;
4. installs npm dependencies and runs `api:check`, ownership/decoder tests, type-check and lint with `working-directory: frontend`;
5. runs artifact/base operations from the repository root;
6. downloads `oasdiff_1.26.1_linux_amd64.tar.gz` from the exact release and verifies SHA256 `ea0007fe536c7915785f754885d2afdb11352d6a14531950edf9d601a2baa674`, taken from the release `checksums.txt`;
7. on pull requests, checks `git cat-file -e "${base_sha}:backend/openapi.json"`, writes `git show "${base_sha}:backend/openapi.json"` to `$RUNNER_TEMP/openapi-base.json`, installs an EXIT trap to remove it, then runs:

```text
$RUNNER_TEMP/oasdiff breaking \
  $RUNNER_TEMP/openapi-base.json \
  backend/openapi.json \
  --fail-on ERR \
  --format githubactions
```

Bootstrap rule: if the base SHA does not yet contain `backend/openapi.json`, CI prints an explicit “baseline introduced” result and skips only the semantic comparison. Byte drift, tests and generated ownership still run. Once the baseline exists, missing/unreadable base/current artifacts fail.

ERR-level breaking changes block. WARN/INFO remain visible for review; tightening to `--fail-on WARN` is a later policy decision after real repository noise is measured. CI never uploads schemas to `oasdiff.com` and never uses `--open`.

## 9. Compatibility And Rollback

- Additive `schema_version` remains readable by existing clients that ignore unknown fields.
- Field removal, required-field addition, enum/type narrowing and response-shape changes follow expand -> migrate consumers -> contract after a compatibility window.
- Backend schema, `backend/openapi.json`, generated TypeScript and aliases ship and roll back together.
- During expand/cutover, existing exported type names remain as aliases. If one domain migration fails, restore that domain's old implementation before contract cleanup; once all consumers pass, delete the duplicate declarations in the same cutover commit.
- If the pinned semantic tool is unavailable in CI, retry or restore the exact verified binary/cache. Do not merge by disabling the gate.
- No database or canonical Chapter data changes occur, so rollback is code/artifact-only.

## 10. Trade-offs

- A single large generated file is accepted because it is deterministic, versioned and hidden behind domain aliases; splitting it would require additional generator config and increase drift surfaces.
- The legacy-compatible operationId formula deliberately retains function names. This is safer than changing 110 public identifiers or maintaining a 110-entry registry; explicit old IDs protect later internal renames.
- A small handwritten runtime decoder is retained because generated TypeScript has no runtime semantics. Generating a second validation system would add a second toolchain and schema artifact for only three SSE payloads.
- A dedicated semantic diff tool is selected instead of a custom structural summary. OpenAPI 3.1 refs, request/response direction, required/nullable and composed schemas are too risky to reimplement locally.
