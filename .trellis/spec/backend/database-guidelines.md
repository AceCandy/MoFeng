# Backend Database Guidelines

> SQLAlchemy 2.0 async patterns. The repository layer owns queries; the service layer owns transactions.

---

## Engine and session

Single async engine + session factory in `app/db/session.py`. SQLite uses `NullPool` and relaxes `check_same_thread`; MySQL enables `pool_pre_ping` and `pool_recycle=3600`. `expire_on_commit=False` so returned ORM objects stay usable after commit.

```python
engine = create_async_engine(settings.sqlalchemy_database_uri, **engine_kwargs)
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖项：提供一个作用域内共享的数据库会话。"""
    async with AsyncSessionLocal() as session:
        yield session
```

Always obtain a session via `Depends(get_session)`. Never construct `AsyncSessionLocal()` in a router.

Reference: `app/db/session.py`.

---

## Base class

`app/db/base.py` defines `Base(DeclarativeBase)`. It only auto-generates the table name from the class name — **it provides no shared columns**.

```python
class Base(DeclarativeBase):
    """SQLAlchemy 基类，自动根据类名生成表名。"""
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower()
```

Each model declares its own `id`, `created_at`, `updated_at`. When adding a model, follow the column shape used in `app/models/user.py` (see "Model columns" below). Note: several existing models (`admin_setting`, `llm_config`, `system_config`, `usage_metric`) omit timestamps — treat that as historical, not a pattern to copy.

---

## Repository pattern

All data access subclasses `BaseRepository` (`app/repositories/base.py`). Repositories **flush, never commit**.

```python
class BaseRepository(Generic[ModelType]):
    model: type[ModelType]

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, **filters: Any) -> Optional[ModelType]:
        stmt = select(self.model).filter_by(**filters)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def add(self, instance: ModelType) -> ModelType:
        self.session.add(instance)
        await self.session.flush()   # flush, NOT commit
        return instance
```

Concrete query — `app/repositories/user_repository.py`:

```python
async def get_by_username(self, username: str) -> Optional[User]:
    stmt = select(User).where(User.username == username)
    result = await self.session.execute(stmt)
    return result.scalars().first()
```

For relations, use `.options(selectinload(...))` (see `app/repositories/novel_repository.py`).

---

## Transaction ownership: the service commits

| Layer | `flush()` | `commit()` |
|-------|-----------|------------|
| repository | yes (after add/update) | **never** |
| service | optional | **yes — single source of truth** |
| router | no | **no** (some legacy endpoints commit; do not extend this) |

Good example — `app/services/user_service.py`. The service catches `IntegrityError`, rolls back, and re-raises a domain error; the repo only flushes.

```python
self.session.add(user)
try:
    await self.session.commit()
except IntegrityError as exc:
    await self.session.rollback()
    raise ValueError("用户名或邮箱已存在") from exc
```

Bad example — committing in a repository or a router. This breaks the rule that services own the transaction boundary and makes rollback semantics inconsistent.

---

## Model columns

Use SQLAlchemy 2.0 typed columns. Reference: `app/models/user.py`.

```python
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

Primary key types are **not uniform** across the codebase: `User.id` is `Integer`, `NovelProject.id` is `String(36)` (UUID-ish), some tables reuse a `BIGINT_PK_TYPE` alias, and `AdminSetting` uses its `key: str` as PK. When adding a new model, match the convention of the sibling models in the same aggregate; do not silently introduce a third PK style.

---

## Schema initialization (Alembic)

Alembic is in use: `backend/alembic.ini`, `backend/alembic/env.py` (async), and `backend/alembic/versions/a53385d06521_baseline.py` (the current schema frozen as baseline). `alembic upgrade head` builds the schema from an empty database.

Production startup (`app/db/init_db.py::_run_alembic_upgrade`) is pure Alembic: a fresh database runs `alembic upgrade head` to build all tables; a legacy database without an `alembic_version` table is first stamped at `head` (`_needs_alembic_stamp`) then upgraded. There is no `Base.metadata.create_all` or `_ensure_schema_updates` fallback at boot - those were retired when the Alembic baseline was adopted.

`Base.metadata.create_all` is now **test-only**: DB-connected tests under `backend/tests/` build an in-memory SQLite schema from the models directly, bypassing Alembic. Raw `.sql` files under `backend/db/migrations/` are legacy (pre-Alembic) and read only by static tests; they are not executed at boot.

**When adding a column/table**: write an Alembic migration under `backend/alembic/versions/` (autogenerate, then `alembic upgrade head` locally). Do not rely on `create_all` to patch existing tables - it only creates new tables and does not alter existing ones.

---

## Anti-patterns to avoid

- **Committing inside a repository.** Breaks the "service owns the transaction" rule.
- **Constructing `AsyncSessionLocal()` in a router** instead of `Depends(get_session)`. Known in `novels.py`, `tasks.py`, `writer.py`.
- **Celery tasks building their own engine + `sessionmaker`.** `app/tasks/emotion_tasks.py` imports the sync `sessionmaker` from `sqlalchemy.orm` and reads `settings.database_url` (the raw, possibly non-async-driver URL) instead of reusing `AsyncSessionLocal` and `settings.sqlalchemy_database_uri`. New background tasks must reuse `app.db.session.AsyncSessionLocal`.
- **Adding a model without an Alembic migration.** The migration history is the source of truth; `create_all` only creates new tables, it does not alter existing ones. Add a migration under `backend/alembic/versions/` for any column/table change.
