# Code Reuse Thinking Guide

> **Purpose**: Stop and think before creating new code — does the project already have it? Duplicated logic is the #1 source of drift bugs in MoFeng.

---

## The Problem

When you copy-paste or rewrite existing logic:

- Bug fixes don't propagate (e.g. one fetch wrapper gets a timeout fix, the other doesn't).
- Behavior diverges across domains (e.g. two error-message readers disagree on which field wins).
- The codebase gets harder to reason about because "where is the real X?" has multiple answers.

---

## Step 1: Search before writing

Before adding a helper, a fetch wrapper, a validator, or a type, search the layer it belongs to:

```bash
# Backend: repositories, services, schemas
rg -n "class.*Repository" backend/app/repositories
rg -n "class.*Service" backend/app/services

# Frontend: api modules, queries, composables, stores
rg -n "requestJson|HttpRequestError" frontend/src/api
rg -n "QueryKeys\\s*=" frontend/src/queries
```

The existing symbol is the contract. Extend it; do not fork it.

---

## Step 2: Ask these questions

| Question | If Yes… |
|----------|---------|
| Does `BaseRepository` already do this? | Subclass it; do not re-implement `select(...).execute()`. |
| Does `src/api/http.ts` already handle this (timeout, abort, error normalization)? | Use `requestJson` / `requestRaw`; do not write a new fetch wrapper. |
| Does the target domain already export a `xxxQueryKeys` factory? | Import it; do not invent a parallel key. |
| Is this conversion `ORM → schema` already done by `Schema.model_validate`? | Use it; do not hand-build dicts. |
| Am I about to declare a type that mirrors a backend Pydantic schema? | Check generated `components` and existing domain aliases; regenerate instead of copying fields. |
| Am I copying code from another file? | **STOP** — extract to the right layer or reuse the existing symbol. |

---

## Common duplication patterns in MoFeng

### 1. A second HTTP wrapper

**Bad** — a domain module defines its own request helper with timeout/abort logic. Two paths then own "how a request fails and what its error message looks like," and they drift.

**Good** — route everything through `src/api/http.ts` (`requestJson` / `requestRaw` / `HttpRequestError`). `src/api/auth.ts` uses `requestRaw` only for `/users/me`, where the `X-Token-Refresh` response header is part of the domain contract.

### 2. Schemas defined inside a router

**Bad** — `app/api/routers/foreshadowing.py` declares `ForeshadowingCreate` / `ForeshadowingResponse` inline. The schema layer no longer owns the full DTO contract.

**Good** — DTOs live in `app/schemas/<domain>.py`; routers import them.

### 3. Re-deriving `Base` columns or query helpers

**Bad** — re-declaring `created_at`/`updated_at` ad hoc, or rewriting `select(model).filter_by(...)` inside a service.

**Good** — subclass `BaseRepository` for data access; follow `app/models/user.py` for the column shape. (Note: there is no shared timestamp mixin today — see [backend/database-guidelines](../backend/database-guidelines.md); until one exists, copy the `user.py` shape, do not invent a third.)

### 4. Inline casts or duplicate API payload shapes

**Bad** — every consumer casts the same untyped field locally:

```ts
const world = (blueprint as { world_setting?: any }).world_setting
```

**Good** — for a migrated DTO, export an indexed alias from the owning API module.
If OpenAPI correctly exposes a dynamic field as `unknown`, narrow it once in a focused
domain utility or runtime decoder and reuse that function. Each local cast or object
shape is a private contract copy that can drift from the backend.

```ts
export type NovelProject = components['schemas']['NovelProject']

const history = decodeConversationHistory(project.conversation_history)
```

### 5. Two validation strategies in one area

**Bad** — `src/components/admin/UserManagement.vue` uses Naive `:rules` + `formRef.validate()` while `PasswordManagement.vue` (same folder) validates by hand in the handler. Reviewers cannot predict which style a new admin form will use.

**Good** — pick the manual-validation pattern for new forms (see [frontend/quality-guidelines](../frontend/quality-guidelines.md)).

---

## When to abstract

**Abstract when**:

- The same logic appears 3+ times (e.g. a third domain wants the same query-key factory shape — already the project standard).
- The logic has a bug surface (HTTP error normalization, ORM→schema mapping).
- Multiple consumers would otherwise each own a private copy of a contract.

**Do not abstract when**:

- Used once.
- Trivial one-liner.
- The abstraction would be more complex than the duplication (e.g. do not build a generic "form field validator" — the manual pattern is intentionally simple).

---

## Gotcha: Python `Literal` + if/elif/else fall-through

Python has no compile-time exhaustive check on `Literal`. When you add a new value to a `Literal` (e.g. a new `db_provider` or `logging_level`), every if/elif/else chain that switches on it silently falls into `else` with the wrong default. Existing validators in `app/core/config.py` (`_normalize_db_provider`, `_normalize_logging_level`) hold this contract.

**Rule**: when extending a `Literal`/enum used in a validator or router branch, use
`rg` to find every switch on that value and add an explicit branch; do not rely on
`else` being correct for the new value.

```python
# BAD — a new provider silently hits else and is rejected with a confusing message
if provider == "mysql":
    return mysql_uri
else:
    return sqlite_uri

# GOOD — explicit branch per value
if provider == "mysql":
    return mysql_uri
elif provider == "sqlite":
    return sqlite_uri
raise ValueError(f"unsupported provider: {provider}")
```

---

## Gotcha: a value that has to change in N places

Several MoFeng changes are inherently multi-site. Treat each as a checklist:

- **DB schema change**: model field + Alembic revision under `backend/alembic/versions/` + isolated migration test. Runtime and `db-bootstrap` must not patch schema. See [backend/database-guidelines](../backend/database-guidelines.md).
- **Generated API response shape change**: backend Pydantic schema +
  `backend/openapi.json` + `frontend/src/api/generated/schema.d.ts` + the existing
  domain alias/decoder + every component prop/emit that reads the field. Generated
  artifacts and aliases are one release unit; do not add a second field owner.
- **Error message field change**: `app/services/*` raises the value; `frontend/src/api/http.ts::readErrorMessage` reads it. Keep the field name (`detail`) consistent.
- **Renaming an API path**: router prefix + every call site in `frontend/src/api/*` + any legacy redirect in `src/router/index.ts`.

Before changing any of these values, use `rg` to find the old value and update all
sites in one change.

---

## Checklist before commit

- [ ] Searched the target layer for an existing symbol before adding a new one.
- [ ] No second HTTP wrapper; no schemas inside routers; no inline casts or duplicate
  object shapes for migrated transport payloads.
- [ ] New repository subclasses `BaseRepository`; new queries use the `xxxQueryKeys` factory.
- [ ] Generated response changes update both committed artifacts, reuse the domain
  alias/decoder, and pass byte/ownership checks.
- [ ] Multi-site changes (schema, response shape, path rename) updated in all sites.
- [ ] `Literal`/enum additions updated every switch that branches on the value.
- [ ] AIMETA header fields still match the file's actual role (e.g. `D=fetch`, not `D=axios`).
