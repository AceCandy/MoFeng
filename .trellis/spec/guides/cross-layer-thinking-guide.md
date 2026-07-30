# Cross-Layer Thinking Guide

> **Purpose**: Think through data flow across layers before implementing. In MoFeng, most bugs live at layer boundaries — router↔service↔repository, ORM↔schema, and backend↔frontend.

---

## The problem

A single feature usually touches several layers:

```
Vue component → queries/* → api/* → HTTP → router → service → repository → ORM row
   ↑                                                                ↓
   └────────────── response shape must match all the way back ←──────┘
```

Each arrow is a place where formats, error semantics, or null handling can diverge.

---

## Step 1: Map the data flow

Before coding, draw the path the value will travel and name the type at each hop:

| Hop | Owner | Type / shape |
|-----|-------|--------------|
| HTTP request body | Router | Pydantic `*Create` / `*Update` |
| Service call | Service | ORM model or `Optional[...]` |
| Persistence | Repository | ORM model (`flush`, not `commit`) |
| Response | Router | Pydantic `*Read` with `from_attributes = True` |
| Frontend transport | `src/api/generated/schema.d.ts` + `src/api/<domain>.ts` | generated component + readable indexed alias |
| UI consumption | `queries/*` then component | `useQuery<T>` + props |

If you cannot name the type at every hop, you are not ready to write the code.

---

## Step 2: Identify boundaries and their common failures

| Boundary | Common MoFeng failure |
|----------|-----------------------|
| Router ↔ Service | Service raising `HTTPException` (couples to FastAPI); router not translating `ValueError` → 400 |
| Service ↔ Repository | Repository calling `commit()`; service not rolling back on `IntegrityError` |
| ORM ↔ Schema | Forgetting `from_attributes = True`; `model_validate` failing on lazy-loaded relations |
| ORM ↔ Async DB session | A flush expires an `onupdate`/server-generated attribute; synchronous serialization triggers implicit I/O and `MissingGreenlet` |
| Backend ↔ Frontend | Pydantic field changes without regenerating/checking OpenAPI and TypeScript artifacts |
| HTTP error ↔ User message | Router raising with a non-`detail` field the frontend's `readErrorMessage` won't find |
| Celery task ↔ Async session | Task building its own engine / sync `sessionmaker` instead of reusing `AsyncSessionLocal` |
| PostgreSQL event log ↔ Redis | Treating a wake-up notification as durable data instead of rereading by cursor |
| SSE snapshot ↔ Client cursor | Reusing an expired cursor or changing stream scope without replacing the snapshot/cursor pair |

---

## Step 3: Define the contract at each boundary

For each boundary, decide and write down:

- The exact input/output shape.
- Who validates (Pydantic at the router for input; repository `filter_by` for query params; manual handler in the frontend for user input).
- What errors can occur and which layer raises/translation occurs where.

---

## Concrete MoFeng cross-layer scenarios

### Scenario A: adding a field to an existing entity

Trace every site and update them in one change:

1. `app/models/<thing>.py` — add the column (typed `Mapped[...]`).
2. `backend/alembic/versions/<revision>.py` — add the Alembic upgrade/downgrade and verify it against an isolated database.
3. `app/schemas/<thing>.py` — add the field to the relevant `*Read` (and `*Create` / `*Update` if writable).
4. `backend/openapi.json` + `frontend/src/api/generated/schema.d.ts` — regenerate the
   committed artifacts; do not edit them by hand.
5. `frontend/src/api/<thing>.ts` — reuse the existing generated indexed alias. Add a
   domain mapper only when the UI shape genuinely differs.
6. `frontend/src/queries/<thing>.ts` + components — the `useQuery<T>` type already
   flows; update props/emits and null/`unknown` narrowing at the owning boundary.

Forgetting step 2 leaves existing databases without the column. Do not add a runtime
or bootstrap schema fallback. Forgetting step 4 leaves committed transport artifacts
stale and must fail `npm run api:check`.

### Scenario B: ORM ↔ Schema conversion

Use `Schema.model_validate(orm_obj)`, set `from_attributes = True` on the Read model. Do not hand-build response dicts in the router. Reference: `user_service.py` returns `UserInDB.model_validate(user)`; `app/api/routers/admin.py` then returns `UserSchema.model_validate(user)`.

Watch lazy-loaded relations: if a Read schema touches a relation, the repository must `.options(selectinload(...))` it (see `app/repositories/novel_repository.py`), or `model_validate` hits a detached-instance error under async.

### Scenario C: error message contract

The router raises `HTTPException(status_code=..., detail="<Chinese message>")`. `frontend/src/api/http.ts::readErrorMessage` looks for `detail` first. Keep error messages in `detail`. If you introduce a new error envelope field, update `readErrorMessage`'s field list in the same change.

### Scenario D: backend response ↔ generated frontend transport

For migrated routes, backend Pydantic models are the field-level source of truth.
`backend/openapi.json` and `src/api/generated/schema.d.ts` are generated artifacts;
`src/api/*` exposes readable indexed aliases without repeating fields. Dynamic
`unknown` values are narrowed once in a domain utility or transport decoder before UI
use. Field names stay snake_case across the wire (`must_change_password`,
`last_edited`). See
[Generated Transport Contract](../backend/transport-contracts.md).

### Scenario E: Celery task reusing async infrastructure

Legacy Celery tasks must reuse `app.db.session.AsyncSessionLocal` and `settings.sqlalchemy_database_uri`, not build a separate engine or import the sync `sessionmaker` from `sqlalchemy.orm`. New long-running chapter work uses the independent durable worker contract in [backend/durable-job-guidelines](../backend/durable-job-guidelines.md). SQLite-only evidence cannot validate PostgreSQL driver, locking, migration, or lease behavior.

---

## Common cross-layer mistakes

- **Implicit format assumptions** — assuming a date comes back as `ISO` string without checking `*Read`; assuming `id` is a number when `NovelProject.id` is `String(36)`.
- **Scattered validation** — validating the same rule in the Pydantic schema, the service, and the frontend handler. Validate once at the entry point per layer.
- **Leaky abstractions** — a Vue component reaching into raw response shapes instead of consuming the typed `useQuery<T>` data; a service importing FastAPI's `HTTPException`.
- **Every consumer re-parses the same payload** — multiple components casting the same untyped SSE/socket event. Put one decoder/type guard at the event boundary; see [code-reuse-thinking-guide](./code-reuse-thinking-guide.md) pattern 4.
- **Flush as invisible I/O setup** — inserting an ORM aggregate, flushing it again to fill a derived field, then serializing an expired attribute. Allocate derived fields while transient or explicitly await a refresh.
- **Wake-up as truth** — applying a Redis notification directly to UI state. Redis may duplicate or lose notifications; always reread the PostgreSQL event log from the durable cursor.

---

## Checklist for cross-layer features

Before implementation:

- [ ] Mapped the full path component → query → api → router → service → repository → model.
- [ ] Named the type at every hop.
- [ ] Decided where validation lives for each input.
- [ ] Confirmed the ORM relation is eager-loaded if the Read schema reads it.
- [ ] Mapped database-generated/`onupdate` attributes and any explicit refresh required after flush.
- [ ] For an event stream, named the durable source, scope/owner gate, cursor, snapshot pair, reset behavior, and optional wake-up path.

After implementation:

- [ ] Tested null / missing / empty / invalid at each boundary.
- [ ] Confirmed error messages flow through `detail` and surface in the UI.
- [ ] Confirmed the value survives a round-trip (create → read → update → read).
- [ ] For a field add: model + Alembic revision/test + backend schema + both generated
  artifacts + affected consumers all updated.
- [ ] For a path/field rename: every call site + legacy redirect updated.
- [ ] Consumers import a shared type / decoder instead of casting payload fields locally.
- [ ] `npm run api:check` passes without rewriting artifacts; semantic breaking changes
  have compatibility evidence in addition to byte-drift evidence.
- [ ] A transient job/event receives its stream sequence before the job insert; public serialization does not depend on implicit async ORM I/O.
- [ ] SSE reset and user/scope changes replace both snapshot and cursor before reconnecting.
