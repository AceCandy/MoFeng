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

## Schema initialization (no Alembic)

`alembic` is listed in `requirements.txt` but **is not used**. There is no `alembic.ini` and no versions directory. Schema is created at startup:

1. `Base.metadata.create_all` runs in `app/db/init_db.py`.
2. `app/db/init_db.py::_ensure_schema_updates` runs dialect-specific raw `ALTER TABLE` SQL to patch in changes that `create_all` cannot apply to existing tables.
3. Raw `.sql` files live in `backend/db/migrations/` as the human-readable change log.

**When adding a column/table**: bump `Base.metadata.create_all` coverage by defining the model, AND add the corresponding `ALTER TABLE` (or `CREATE TABLE IF NOT EXISTS`) block inside `_ensure_schema_updates` so existing deployments get the change. Add a `.sql` note under `backend/db/migrations/` for traceability. Do not introduce Alembic mid-flight without a separate migration effort.

---

## Anti-patterns to avoid

- **Committing inside a repository.** Breaks the "service owns the transaction" rule.
- **Constructing `AsyncSessionLocal()` in a router** instead of `Depends(get_session)`. Known in `novels.py`, `tasks.py`, `writer.py`.
- **Celery tasks building their own engine + `sessionmaker`.** `app/tasks/emotion_tasks.py` imports the sync `sessionmaker` from `sqlalchemy.orm` and reads `settings.database_url` (the raw, possibly non-async-driver URL) instead of reusing `AsyncSessionLocal` and `settings.sqlalchemy_database_uri`. New background tasks must reuse `app.db.session.AsyncSessionLocal`.
- **Adding a model without updating `_ensure_schema_updates`.** Existing deployments will not get the new column.
