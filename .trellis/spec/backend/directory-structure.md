# Backend Directory Structure

> How `backend/app/` is organized. Every new module must follow this layering.

---

## Tech stack

FastAPI + SQLAlchemy 2.0 (async) + Pydantic v2 + Celery/Redis + LangGraph. Async drivers: `asyncmy` (MySQL) and `aiosqlite` (SQLite). See `backend/requirements.txt`.

---

## Request flow

```
HTTP request
  → app/main.py                         FastAPI app + lifespan + include_router
  → app/api/routers/<module>.py         APIRouter, response_model, Depends(...)
  → app/services/<module>_service.py    business logic, owns the AsyncSession + commit
  → app/repositories/<module>_repository.py   SQLAlchemy select/execute, flush only
  → app/models/<module>.py              SQLAlchemy ORM (subclass of db.base.Base)
  → app/schemas/<module>.py             Pydantic request/response DTOs
```

The dependency chain is wired by `Depends`. Routers never call repositories directly; they go through a service.

---

## Directory map

| Dir | Responsibility | Example |
|-----|----------------|---------|
| `app/api/routers/` | One `APIRouter` per domain; declares endpoints, `response_model`, `Depends`. Aggregated in `app/api/routers/__init__.py` as `api_router`. | `app/api/routers/admin.py`, `auth.py`, `novels.py` |
| `app/services/` | Business logic. Constructed with an `AsyncSession`; commits transactions; orchestrates repos + utils. | `app/services/user_service.py`, `auth_service.py` |
| `app/repositories/` | Data access only. Subclass `BaseRepository`; run queries; `flush()` only, never `commit()`. | `app/repositories/base.py`, `user_repository.py` |
| `app/models/` | SQLAlchemy 2.0 `Mapped` / `mapped_column` ORM tables. Re-exported via `app/models/__init__.py`. | `app/models/user.py`, `novel.py` |
| `app/schemas/` | Pydantic v2 request/response DTOs. Fully separate from ORM models. | `app/schemas/user.py`, `novel.py` |
| `app/core/` | Cross-cutting infra: `config.py` (pydantic-settings), `security.py` (JWT/password), `dependencies.py` (auth + session DI). | `app/core/dependencies.py` |
| `app/db/` | Engine/session factory, `Base`, `init_db.py`, `system_config_defaults.py`. | `app/db/session.py`, `base.py` |
| `app/tasks/` | Celery tasks (sync entrypoints that bootstrap an event loop). | `app/tasks/emotion_tasks.py` |
| `app/utils/` | Pure helpers, no DB/HTTP side effects. | `app/utils/json_utils.py`, `llm_tool.py` |
| `app/config/` | Celery app definition only. | `app/config/celery_config.py` |

---

## App bootstrap

`app/main.py` builds the FastAPI app, runs `init_db()` and prompt preload in the lifespan, then includes the aggregated router.

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with AsyncSessionLocal() as session:
        await PromptService(session).preload()
    yield

app = FastAPI(title=settings.app_name, debug=settings.debug, version="1.0.0", lifespan=lifespan)
app.include_router(api_router)
```

Reference: `app/main.py`.

---

## Dependency injection

All DI is centralized in `app/core/dependencies.py`:

- `get_session` — yields an `AsyncSession` for the request scope (defined in `app/db/session.py`, re-used everywhere).
- `get_current_user` / `get_current_admin` — OAuth2 bearer → `UserInDB`.

**Service-as-dependency pattern**: each router declares a thin factory that injects the session into the service constructor. Every router follows this.

Good example — `app/api/routers/admin.py`:

```python
def get_user_service(session: AsyncSession = Depends(get_session)) -> UserService:
    return UserService(session)

@router.post("/users", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreateAdmin,
    service: UserService = Depends(get_user_service),
    current_admin=Depends(get_current_admin),
) -> UserSchema:
    ...
```

---

## Adding a new domain module

1. `app/models/<thing>.py` — ORM table subclassing `Base`; export it from `app/models/__init__.py`.
2. `app/schemas/<thing>.py` — Pydantic DTOs (Base / Create / Update / Read). See [database-guidelines](./database-guidelines.md) and [quality-guidelines](./quality-guidelines.md).
3. `app/repositories/<thing>_repository.py` — subclass `BaseRepository`.
4. `app/services/<thing>_service.py` — hold the session + repo; commit here.
5. `app/api/routers/<thing>.py` — `APIRouter`, `get_<thing>_service` factory, then `include_router` in `app/api/routers/__init__.py`.

---

## AIMETA file header (project convention)

Every Python module in `backend/app/` starts with an `AIMETA` comment line describing the file's purpose, responsibility, entity, layer, and dependencies. Keep it on line 1 and keep it accurate when you change a file's role.

```python
# AIMETA P=用户服务_用户管理业务逻辑|R=用户CRUD_权限|NR=不含认证逻辑|E=UserService|X=internal|A=服务类|D=sqlalchemy|S=db|RD=./README.ai
```

Fields: `P`=purpose, `R`=responsibilities, `NR`=non-responsibilities, `E`=entity/symbol, `X`=exposure (`internal`/`http`), `A`=archetype, `D`=deps, `S`=state layer, `RD`=README pointer. New files should include this header.

---

## Anti-patterns to avoid

- **Bypassing `Depends(get_session)` in a router.** Manually opening `AsyncSessionLocal()` inside an endpoint breaks session lifecycle and skips the standard wiring. Known occurrences: `app/api/routers/novels.py`, `tasks.py`, `writer.py` (streaming/background endpoints). Prefer `Depends(get_session)`; if a background task needs its own session, open it inside the service layer, not the router.
- **Defining Pydantic schemas inside a router file.** DTOs belong in `app/schemas/`. Known occurrence: `app/api/routers/foreshadowing.py` defines `ForeshadowingCreate` / `ForeshadowingResponse` inline — do not repeat this in new code.
- **Importing ORM `User` and schema `User` with the same unqualified name.** Alias on import (`from ...schemas.user import User as UserSchema`) to avoid the collision.
