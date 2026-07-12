# Backend Quality Guidelines

> Cross-cutting rules: async discipline, Pydantic, config, Celery, testing, and the AIMETA header.

---

## Async/sync discipline

- All DB I/O goes through `AsyncSession` and is awaited.
- All HTTP I/O uses `httpx.AsyncClient`. **No `requests`, no `httpx.Client` sync calls.**
- Wrapping a genuinely sync library (smtplib, etc.): use `asyncio.to_thread`, never `asyncio.run` inside an async path.

Good example — `app/services/auth_service.py`:

```python
def _send():
    smtp = smtplib.SMTP_SSL(server, port, timeout=10)
    ...
await asyncio.to_thread(_send)
```

---

## Pydantic schemas

Split request/response DTOs from ORM models in `app/schemas/`. The local convention extends the Base/Create/Update/Read quartet with role-specific variants (`UserCreateAdmin`, `UserRegistration`, etc.).

Reference: `app/schemas/user.py`.

```python
class UserBase(BaseModel):
    username: str = Field(..., description="用户名")
    email: Optional[EmailStr] = Field(default=None, description="邮箱，可选")

class UserCreate(UserBase):
    password: str = Field(..., min_length=6, description="明文密码")

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = Field(default=None)
    password: Optional[str] = Field(default=None, min_length=6)

class User(UserBase):                       # the Read / response model
    id: int = Field(...)
    is_admin: bool = Field(default=False)
    class Config:
        from_attributes = True
```

Rules:

- Response models set `class Config: from_attributes = True` so `Model.model_validate(orm_obj)` works.
- Declare `response_model=...` on the route decorator (do not rely on return-type annotation alone). Reference: `app/api/routers/admin.py` (`response_model=UserSchema`, `status_code=201`).
- Convert ORM → schema with `Schema.model_validate(obj)` at the router/service boundary (see `user_service.py`).
- Aliasing: when importing both ORM `User` and schema `User` into the same file, alias the schema import (`from ...schemas.user import User as UserSchema`).

Bad example — defining schemas inline in a router (`app/api/routers/foreshadowing.py`). Put them in `app/schemas/`.

---

## Config (pydantic-settings)

`app/core/config.py` defines `Settings(BaseSettings)` with explicit `env=` per field, computed DB-URL `@property`s, and an `lru_cache`-backed module-level singleton `settings`.

```python
class Settings(BaseSettings):
    app_name: str = Field(default="AI Novel Generator API", description="FastAPI 文档标题")
    debug: bool = Field(default=True, description="是否开启调试模式")
    secret_key: str = Field(..., env="SECRET_KEY", description="JWT 加密密钥")
    logging_level: str = Field(default="INFO", env="LOGGING_LEVEL", ...)
    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
```

Rules for new config:

- Every field names its env var explicitly via `env=` (and use `validation_alias=AliasChoices(...)` for backwards-compatible renames, e.g. `OPENAI_API_BASE_URL` / `OPENAI_BASE_URL`).
- Compute derived values (DB URLs, dialect flags) as `@property`s (`sqlalchemy_database_uri`, `is_sqlite_backend`), not stored fields.
- Consume `settings` by import, not by re-reading env vars ad hoc.

> Existing quirks (do not copy, do not "fix" without a task): `env_file` references a non-existent `new-backend/.env`; some validators use the deprecated pydantic v1 `@validator` instead of `@field_validator`.

---

## Celery tasks

`app/config/celery_config.py` defines the Celery app (Redis broker/backend). Tasks are **sync** (`def`, not `async def`) and bootstrap their own event loop. Reference: `app/tasks/emotion_tasks.py`:

```python
@app.task(bind=True, name='app.tasks.emotion_tasks.analyze_emotion_async')
def analyze_emotion_async(self, novel_id, chapter_ids=None):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_analyze_emotion_impl(novel_id, chapter_ids, self))
    finally:
        loop.close()
```

Rule for new tasks: reuse `app.db.session.AsyncSessionLocal` and `settings.sqlalchemy_database_uri` inside the async implementation. Do not rebuild a separate engine and do not import the sync `sessionmaker` from `sqlalchemy.orm` (the existing task does both — legacy, do not extend).

---

## Testing

- `pytest` + `pytest-asyncio`. Config in `pytest.ini` and `conftest.py` at repo root.
- Tests live in `backend/tests/`.
- Mark async tests per `pytest-asyncio` mode; do not spin up `asyncio.run` inside them.

---

## Forbidden patterns

- `print(...)` for diagnostics — use the module logger.
- `requests` or sync `httpx.Client` for outbound HTTP — use `httpx.AsyncClient`.
- `asyncio.run(...)` inside an async path or FastAPI request.
- Committing inside a repository (see [database-guidelines](./database-guidelines.md)).
- `HTTPException` raised from a repository (see [error-handling](./error-handling.md)).
- f-string / `.format` inside `logger.<level>(...)` calls (see [logging-guidelines](./logging-guidelines.md)).
- Bare `except Exception: pass`.
- Logging secrets, tokens, or full prompt bodies.

---

## Review checklist

- [ ] New module has an `AIMETA` header on line 1.
- [ ] Router uses `Depends(get_session)` / `Depends(get_<x>_service)`; no manual `AsyncSessionLocal()`.
- [ ] Repository subclasses `BaseRepository` and only `flush()`es.
- [ ] Service owns `commit()`/`rollback()`; raises `ValueError` on business failure, not `HTTPException`.
- [ ] DTOs in `app/schemas/`, `response_model=` declared, `from_attributes = True` on Read models.
- [ ] Outbound HTTP is `httpx.AsyncClient`; sync libs wrapped with `asyncio.to_thread`.
- [ ] Logger declared at module top with `getLogger(__name__)`; uses `%s` args.
- [ ] No secrets in log lines.
- [ ] Schema change shipped as an Alembic migration under `backend/alembic/versions/` (see [database-guidelines](./database-guidelines.md)).
