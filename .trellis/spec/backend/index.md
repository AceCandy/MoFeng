# Backend Development Guidelines

> FastAPI + SQLAlchemy 2.0 (async) + Pydantic v2 + Celery. Backend lives under `backend/app/`.

---

## At a glance

| Concern | Convention | Reference |
|---------|------------|-----------|
| Layering | `routers → services → repositories → models` + `schemas` | [directory-structure](./directory-structure.md) |
| DI | `Depends(get_session)` + `get_<x>_service` factories, wired in `core/dependencies.py` | [directory-structure](./directory-structure.md) |
| DB | SQLAlchemy 2.0 async; repository `flush()`es, service `commit()`s | [database-guidelines](./database-guidelines.md) |
| Errors | Service raises `ValueError`; router translates to `HTTPException` | [error-handling](./error-handling.md) |
| Logging | stdlib `logging`, `getLogger(__name__)`, lazy `%s` args | [logging-guidelines](./logging-guidelines.md) |
| Quality | `httpx.AsyncClient`, `response_model=` on routes, AIMETA header on every file | [quality-guidelines](./quality-guidelines.md) |
| Security | CORS whitelist, Fernet secret encryption, SSRF guard, auth hardening | [security-guidelines](./security-guidelines.md) |

---

## Guidelines Index

| Guide | Description |
|-------|-------------|
| [Directory Structure](./directory-structure.md) | Request flow, directory map, DI wiring, AIMETA header |
| [Database Guidelines](./database-guidelines.md) | Engine/session, repository pattern, transaction ownership, schema init (Alembic + startup fallback) |
| [Error Handling](./error-handling.md) | Domain errors vs `HTTPException`, status-code map, anti-patterns |
| [Logging Guidelines](./logging-guidelines.md) | `dictConfig` setup, level conventions, lazy formatting |
| [Quality Guidelines](./quality-guidelines.md) | Async discipline, Pydantic schemas, config, Celery, review checklist |
| [Security Guidelines](./security-guidelines.md) | CORS, Fernet secret encryption, SSRF, auth hardening |

---

## Known cross-cutting debt (context, not a TODO list)

These are documented so new code does not repeat them. They are intentionally **not** fixed inline by small features:

1. Error signaling is split between `ValueError` (good) and `HTTPException` raised from services (legacy). New code uses `ValueError`.
2. No shared timestamp mixin / uniform PK type across models. New models match sibling models in their aggregate.
3. Some routers open `AsyncSessionLocal()` directly. New routers use `Depends(get_session)`.

---

**Language**: documentation in English; log messages and field `description`s may be Chinese (they surface to users).
