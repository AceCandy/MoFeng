# Backend Database Guidelines

> SQLAlchemy 2.0 async patterns. The repository layer owns queries; the service layer owns transactions.

---

## Engine and session

Single async engine + session factory in `app/db/session.py`. Application runtime, Alembic/bootstrap, and the durable job runtime support PostgreSQL through the asyncpg driver. SQLite/aiosqlite is allowed only for isolated unit tests that do not claim deployment, migration, locking, lease, or event-log compatibility; MySQL is not a supported target. PostgreSQL enables `pool_pre_ping` and `pool_recycle=3600`. `expire_on_commit=False` keeps returned ORM objects usable after commit, but it does not prevent flush-time expiry of SQL-expression/server-generated attributes.

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

## Async ORM attributes after flush

An async flush can expire attributes populated by `server_default`, SQL-expression `onupdate`, or another database-side expression. Reading such an attribute synchronously may issue an implicit `SELECT`; outside SQLAlchemy's awaited greenlet this raises `MissingGreenlet`. `expire_on_commit=False` does not change this flush behavior.

Assign database-derived identifiers before adding a new aggregate to the session. In particular, a durable job remains transient while its stream row is locked and `event_sequence` is allocated; only then is the job inserted and used to build its public event snapshot.

```python
# Wrong: the second flush updates a persistent job and may expire updated_at.
await repo.add(job)
sequence = await next_stream_sequence(job)
payload = public_task_snapshot(job)

# Correct: allocate derived fields while the job is transient, then insert once.
sequence = await next_stream_sequence(job)
await repo.add(job)
payload = public_task_snapshot(job)
```

If code genuinely needs a database-generated value after flush, load it explicitly with `await session.refresh(instance, attribute_names=[...])` or an awaited `select(...)`. Never rely on ordinary Python attribute access to perform async I/O.

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

## Explicit database lifecycle

Alembic is in use: `backend/alembic.ini`, `backend/alembic/env.py` (async), and `backend/alembic/versions/a53385d06521_baseline.py` (the original frozen baseline). The full revision chain through the current head builds the schema from an empty database.

Database creation, schema migration, data bootstrap, and runtime are separate roles:

- `python -m app.db.cli db-create` optionally creates a PostgreSQL database for installation only.
- `python -m app.db.cli db-migrate` runs Alembic `upgrade head` only.
- `python -m app.db.cli db-bootstrap` runs immutable, transactional data steps under a version ledger and advisory lock.
- `python -m app.db.cli db-check` is read-only and verifies connectivity, Alembic head, bootstrap contracts, and the binary rollback floor.
- API/worker runtime never creates a database, migrates schema, seeds defaults, creates an administrator, or rewrites historical data.

A database with business tables but no `alembic_version` is never stamped automatically. Migration first computes a read-only manifest fingerprint (tables, columns, types, ordered key/index columns, constraints, and indexes). Only an exact registered baseline can be adopted with `db-adopt-legacy`, an operator identity, the observed fingerprint, and explicit backup confirmation; unknown or partial schemas fail closed.

Bootstrap versions insert active configuration and prompt defaults only when missing, and create a default administrator only when enabled and no administrator exists. A version may explicitly remove named obsolete rows; that destructive rule is part of the immutable checksum and must not be broadened in place. Historical provider keys are encrypted by a separate version without logging key values.

`Base.metadata.create_all` is **test-only**: DB-connected tests may build isolated schemas directly from models, bypassing Alembic. Raw `.sql` files under `backend/db/migrations/` are legacy and are not executed by runtime or the explicit CLI.

**When adding a column/table**: write an Alembic migration under `backend/alembic/versions/` (autogenerate, then run the migration against an isolated database). Do not rely on `create_all` to patch existing tables - it only creates new tables and does not alter existing ones.

## Scenario: changing the database lifecycle

### 1. Scope / Trigger

Apply this contract whenever a change touches Alembic, bootstrap data, database readiness, legacy adoption, database deployment ordering, or the environment values consumed by those roles. It prevents application processes from becoming implicit schema/data writers and makes failed releases observable before traffic is accepted.

### 2. Signatures

```text
python -m app.db.cli db-create
python -m app.db.cli db-migrate
python -m app.db.cli db-adopt-legacy \
  --operator <identity> \
  --expected-fingerprint <sha256> \
  --backup-confirmed
python -m app.db.cli db-bootstrap
python -m app.db.cli db-check

# External PostgreSQL: complete URL, no bundled postgres profile.
DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>:<port>/<database>

# Bundled PostgreSQL: DATABASE_URL is unset and POSTGRES_* forms the URL.
POSTGRES_HOST=pg
POSTGRES_PORT=5432
POSTGRES_USER=<user>
POSTGRES_PASSWORD=<password>
POSTGRES_DATABASE=<database>

GET /health
GET /api/health
GET /ready
GET /api/ready
```

Persistent contracts:

- `database_bootstrap_versions`: `version`, `name`, `checksum`, `status`, `minimum_binary_version`, start/completion/failure timestamps, and a non-secret `failure_code`.
- `legacy_database_adoptions`: schema fingerprint, adopted Alembic revision, operator, backup confirmation, result, and adoption time.

### 3. Contracts

- `db-migrate` performs schema migration only. It never seeds data or stamps an unversioned business database automatically.
- `db-bootstrap` requires the schema at code head. Each registered version is ordered, immutable, transactional, and mutually exclusive; a completed version is validated and skipped on rerun.
- `db-check` and the HTTP readiness endpoints are read-only. Their payload is `{"status": "ready" | "not_ready", "codes": string[]}`; HTTP readiness returns 200 when ready and 503 otherwise.
- `/health` and `/api/health` are dependency-free liveness endpoints and remain 200 while the process can respond.
- `BOOTSTRAP_CREATE_DEFAULT_ADMIN` defaults to `true`. When it is true in production, `ADMIN_DEFAULT_PASSWORD` must pass the production strength gate; when false, an administrator password is not required.
- `DATABASE_URL`, when set, is the complete target URL and takes precedence over every `POSTGRES_*` value. External-URL mode does not require `POSTGRES_PASSWORD` as a separate variable and deployment must not enable the bundled `postgres` profile.
- When `DATABASE_URL` is absent, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DATABASE` form the target URL. `POSTGRES_HOST=pg` selects the bundled Compose PostgreSQL profile.
- Application runtime, Alembic/bootstrap, and durable jobs accept PostgreSQL only. SQLite remains an isolated unit-test aid, not a local/deployment compatibility target; tests that exercise PostgreSQL locking, migration SQL, JSON behavior, or async driver semantics must use PostgreSQL.
- Logs and CLI output may contain revision ids, status codes, counts, and schema fingerprints. They must never contain database passwords, administrator passwords, provider keys, or decrypted values.

### 4. Validation & Error Matrix

| Condition | Required result |
|-----------|-----------------|
| Database cannot be reached | CLI fails; readiness includes `database_unreachable` or `readiness_check_failed` |
| Database revision set differs from code heads | Bootstrap refuses to run; readiness includes `schema_not_at_head` |
| Required bootstrap version is absent or not completed | Readiness includes `bootstrap_incomplete` |
| Ledger name/checksum/minimum binary version drifts | Bootstrap fails closed; readiness includes `bootstrap_contract_mismatch` |
| A completed row requires a newer binary | Readiness includes `binary_below_rollback_floor` |
| Business tables exist without `alembic_version` | `db-migrate` makes no schema change and reports `legacy_database_requires_adoption` plus the observed fingerprint |
| Adoption fingerprint is unknown or differs from the observed value | Adoption makes no change and reports `unknown_legacy_schema` or `legacy_fingerprint_mismatch` |
| Adoption lacks operator identity or backup confirmation | Adoption makes no change and fails validation |
| Production default-admin bootstrap uses a weak/empty password | Bootstrap refuses to write data |
| `DATABASE_URL` is set without a separate `POSTGRES_PASSWORD` | External mode remains valid and no bundled PostgreSQL service starts |
| `DATABASE_URL` and `POSTGRES_*` are both set | The complete `DATABASE_URL` wins; values are never merged |
| A release/deployment targets a non-PostgreSQL URL | Unsupported target; it cannot satisfy the release/readiness evidence and must not be presented as compatible |

### 5. Good / Base / Bad Cases

- Good: an empty database runs `db-migrate -> db-bootstrap -> db-check`; the check reports ready and runtime starts without any write-side initialization.
- Good: an external `DATABASE_URL` deploys migrate/bootstrap/app/worker without a separate `POSTGRES_PASSWORD` and without starting the bundled `pg` service.
- Base: rerunning migrate/bootstrap against a current database performs no additional bootstrap mutation and still validates every immutable ledger contract.
- Base: isolated, database-agnostic unit tests may use SQLite but cannot satisfy a PostgreSQL integration acceptance criterion.
- Bad: API lifespan, worker import, or a health endpoint invokes Alembic, `create_all`, seed logic, administrator creation, legacy key migration, or automatic `stamp`.

### 6. Tests Required

- Unit: fingerprinting is insensitive to unordered table/constraint discovery but changes when ordered composite key/index columns or CHECK constraints change.
- Unit: readiness asserts every stable code above, including name/checksum/floor drift and HTTP 503 response shape.
- PostgreSQL integration: empty and current databases, explicit legacy adoption with audit row, unknown/mismatched legacy rejection, migration rollback on injected failure, and concurrent bootstrap execution exactly once.
- PostgreSQL async integration: flush paths that use SQL-expression/server-generated timestamps perform explicit refreshes when needed; durable job enqueue allocates its stream sequence before the job insert and does not require a second job-row flush before public serialization.
- Static/deployment: runtime imports no mixed `init_db`; the image contains Alembic files; Compose resolves in bundled and external PostgreSQL modes and orders `migrate -> bootstrap -> app`.
- Deployment matrix: external `DATABASE_URL` works without `POSTGRES_PASSWORD` and does not enable bundled `pg`; bundled mode requires its `POSTGRES_*` values; no non-PostgreSQL target is accepted as runtime/Alembic/durable-job evidence.

### 7. Wrong vs Correct

Wrong:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()  # schema and data mutation in every runtime process
    yield
```

Correct:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    readiness = await check_database_readiness()
    if readiness.ready:
        await preload_read_only_state()
    yield
```

Deployment owns the write-side sequence before this runtime starts.

For external PostgreSQL, pass the complete `DATABASE_URL` and omit the Compose `postgres` profile. For bundled PostgreSQL, leave `DATABASE_URL` unset and provide `POSTGRES_*`; never combine a URL from parts of both modes.

---

## Anti-patterns to avoid

- **Committing inside a repository.** Breaks the "service owns the transaction" rule.
- **Constructing `AsyncSessionLocal()` in a router** instead of `Depends(get_session)`. Known in `novels.py`, `tasks.py`, `writer.py`.
- **Celery tasks building their own engine + `sessionmaker`.** `app/tasks/emotion_tasks.py` imports the sync `sessionmaker` from `sqlalchemy.orm` and reads `settings.database_url` (the raw, possibly non-async-driver URL) instead of reusing `AsyncSessionLocal` and `settings.sqlalchemy_database_uri`. New background tasks must reuse `app.db.session.AsyncSessionLocal`.
- **Adding a model without an Alembic migration.** The migration history is the source of truth; `create_all` only creates new tables, it does not alter existing ones. Add a migration under `backend/alembic/versions/` for any column/table change.
- **Calling sync `Session.query(...)` inside an `async def` service.** An `AsyncSession`'s `sync_session` only works under a greenlet; calling it directly from an `async` method raises `MissingGreenlet` and surfaces as a 500. Use `await session.execute(select(...))` + `.scalars()`. `ConsistencyService._get_check_context` is the reference. When a service needs both DB reads and long LLM calls, commit the read transaction first so the LLM call does not hold a DB connection (see `FinalizeService.finalize_chapter`).
- **Flushing a newly inserted ORM aggregate again to assign a derived field, then synchronously serializing SQL-expression/server-generated attributes.** The update flush may expire attributes such as `updated_at`; ordinary access can trigger implicit I/O and `MissingGreenlet`. Allocate derived fields before the insert, or explicitly `await session.refresh(...)` before reading them.
