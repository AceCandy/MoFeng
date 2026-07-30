# Backend Development Guidelines

> FastAPI + SQLAlchemy 2.0 async + Pydantic v2 + PostgreSQL/asyncpg. Long-running chapter work uses the independent durable worker; Celery remains legacy-only. Backend lives under `backend/app/`.

---

## At a glance

| Concern | Convention | Reference |
|---------|------------|-----------|
| Layering | `routers → services → repositories → models` + `schemas` | [directory-structure](./directory-structure.md) |
| DI | `Depends(get_session)` + `get_<x>_service` factories, wired in `core/dependencies.py` | [directory-structure](./directory-structure.md) |
| DB | SQLAlchemy 2.0 async; explicit migrate/bootstrap/check; no runtime mutation | [database-guidelines](./database-guidelines.md) |
| Errors | Service raises `ValueError`; router translates to `HTTPException` | [error-handling](./error-handling.md) |
| Logging | stdlib `logging`, `getLogger(__name__)`, lazy `%s` args | [logging-guidelines](./logging-guidelines.md) |
| Quality | `httpx.AsyncClient`, `response_model=` on routes, AIMETA header on every file | [quality-guidelines](./quality-guidelines.md) |
| Transport contracts | Deterministic OpenAPI, generated TypeScript aliases, versioned SSE decoders, CI gates | [transport-contracts](./transport-contracts.md) |
| Security | CORS whitelist, Fernet secret encryption, SSRF guard, auth hardening | [security-guidelines](./security-guidelines.md) |
| Chapter context | One versioned snapshot for generation, review, consistency, and recovery | [chapter-context-contract](./chapter-context-contract.md) |
| Durable jobs | PostgreSQL leases, fencing, event replay, public projections, and worker recovery | [durable-job-guidelines](./durable-job-guidelines.md) |
| Chapter projections | Immutable outbox lineage, aggregate lock order, replay, and rollout fencing | [chapter-projection-contract](./chapter-projection-contract.md) |

---

## Guidelines Index

| Guide | Description |
|-------|-------------|
| [Directory Structure](./directory-structure.md) | Request flow, directory map, DI wiring, AIMETA header |
| [Database Guidelines](./database-guidelines.md) | Engine/session, transaction ownership, explicit Alembic/bootstrap/readiness lifecycle |
| [Error Handling](./error-handling.md) | Domain errors vs `HTTPException`, status-code map, anti-patterns |
| [Logging Guidelines](./logging-guidelines.md) | `dictConfig` setup, level conventions, lazy formatting |
| [Quality Guidelines](./quality-guidelines.md) | Async discipline, Pydantic schemas, config, Celery, review checklist |
| [Generated Transport Contract](./transport-contracts.md) | OpenAPI artifacts, generated ownership, task decoder, and semantic CI gate |
| [Security Guidelines](./security-guidelines.md) | CORS, Fernet secret encryption, SSRF, auth hardening |
| [Canonical Chapter Context](./chapter-context-contract.md) | Resolver/adapters, revision layers, snapshot recovery, and tests |
| [Durable Job And Event Log](./durable-job-guidelines.md) | Enqueue identity, lease/fencing, handler side effects, SSE cursor recovery, and process tests |
| [Replayable Chapter Projections](./chapter-projection-contract.md) | Finalize outbox validation, live/tombstone lock order, replay snapshots, and race tests |

---

## Pre-Development Checklist

- Read the guide for every touched concern; for database lifecycle changes, read Database, Quality, Security, and Logging Guidelines.
- For changes crossing runtime, storage, and deployment, read the [Cross-Layer Thinking Guide](../guides/cross-layer-thinking-guide.md).
- For background execution, task APIs, SSE, Redis wake-up, or worker deployment, read the [Durable Job And Event Log](./durable-job-guidelines.md).
- For route/schema changes or migrated frontend DTOs, read the [Generated Transport Contract](./transport-contracts.md).
- For Chapter projection dispatch, replay, runtime, rollout, or tombstone changes, read the [Replayable Chapter Projections](./chapter-projection-contract.md).
- Before adding helpers or copied contracts, read the [Code Reuse Thinking Guide](../guides/code-reuse-thinking-guide.md).

## Quality Check

- Always apply [Quality Guidelines](./quality-guidelines.md) and [Logging Guidelines](./logging-guidelines.md).
- For schema, migration, bootstrap, readiness, or database config changes, also apply [Database Guidelines](./database-guidelines.md) and [Security Guidelines](./security-guidelines.md).
- For changes spanning multiple layers or repeated constants/commands, apply the [Cross-Layer](../guides/cross-layer-thinking-guide.md) and [Code Reuse](../guides/code-reuse-thinking-guide.md) checklists.
- Durable job changes require PostgreSQL lease/fencing coverage; recovery claims require a real independent-process termination/reclaim test.
- Chapter projection changes must preserve the documented aggregate lock order and validate outbox lineage at the final runtime boundary.
- Run focused tests plus syntax/type/static checks; database lifecycle changes require isolated PostgreSQL coverage, not SQLite-only evidence.

---

## Known cross-cutting debt (context, not a TODO list)

These are documented so new code does not repeat them. They are intentionally **not** fixed inline by small features:

1. Error signaling is split between `ValueError` (good) and `HTTPException` raised from services (legacy). New code uses `ValueError`.
2. No shared timestamp mixin / uniform PK type across models. New models match sibling models in their aggregate.
3. Some routers open `AsyncSessionLocal()` directly. New routers use `Depends(get_session)`.

---

**Language**: documentation in English; log messages and field `description`s may be Chinese (they surface to users).
