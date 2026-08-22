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

### Locking rereads must refresh the identity map

When a service first reads an identity without a lock and later reacquires that row with
`FOR UPDATE`, the locking query must use `execution_options(populate_existing=True)`.
SQLAlchemy otherwise may return the object already cached by the `AsyncSession`, even
though the database lock was acquired after another transaction committed. Command,
fencing, revision, and status validation must use the refreshed locked row.

```python
# Wrong: row may still expose values cached by an earlier unlocked read.
stmt = select(Command).where(Command.id == command_id).with_for_update()

# Correct: the locked database row replaces cached attributes.
stmt = (
    select(Command)
    .where(Command.id == command_id)
    .with_for_update()
    .execution_options(populate_existing=True)
)
```

PostgreSQL concurrency tests must preload the old entity in two independent sessions,
let one transaction commit, and assert the waiter observes the committed status after
acquiring its lock. A sequential replay test does not cover this identity-map hazard.

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

> **Warning**: A Python `default`, a DDL `server_default`, and a Python `onupdate` are different contracts. Do not call their textual difference schema drift by itself. Before adding a migration, compare the model with the Alembic history and live PostgreSQL catalog, then trace whether production writers use ORM-generated statements or bypass them. Add or change a server default only when an existing database-side write contract or observable failure requires it.

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

Apply this contract whenever a change touches Alembic, bootstrap data, database readiness, legacy adoption, database deployment ordering, process-manager user switching, or the environment values consumed by those roles. It prevents application processes from becoming implicit schema/data writers and makes failed releases observable before traffic is accepted.

It also applies when a versioned database contains an ORM-created table that is newer than its `alembic_version`, such as residue from an older runtime or test fixture that called `Base.metadata.create_all`. The owning revision must reconcile that object explicitly rather than assuming revision and physical schema always advance together.

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

# A process manager that switches to appuser must also switch HOME.
user=appuser
environment=HOME="/home/appuser"

GET /health
GET /api/health
GET /ready
GET /api/ready

alembic_version=<prior revision>
precreated ORM table=<exact target table contract>
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
- A process manager that starts the database client as `appuser` must set `HOME=/home/appuser`; changing only the UID may leave `HOME=/root`, making asyncpg's default PostgreSQL SSL-file discovery fail with `PermissionError` before connecting.
- Application runtime, Alembic/bootstrap, and durable jobs accept PostgreSQL only. SQLite remains an isolated unit-test aid, not a local/deployment compatibility target; tests that exercise PostgreSQL locking, migration SQL, JSON behavior, or async driver semantics must use PostgreSQL.
- An owning revision may adopt a precreated ORM table only after validating its ordered columns, types, nullability/defaults, primary key, named CHECK/unique constraints, foreign keys, and indexes against the target contract. Matching data is preserved and required seed rows use conflict-safe inserts; any mismatch fails before stamping the revision. A bare `IF NOT EXISTS` or unconditional skip is forbidden because it hides schema drift.
- A revision that must inspect the live catalog to reconcile precreated objects rejects Alembic offline SQL generation. Its downgrade must also reject destructive removal of adopted data or lineage; release rollback uses the documented binary rollback floor instead of schema deletion.
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
| Process manager runs as `appuser` with `HOME=/root` or another inaccessible directory | Deployment is invalid; readiness may report `database_unreachable` even though an independent CLI check succeeds |
| A release/deployment targets a non-PostgreSQL URL | Unsupported target; it cannot satisfy the release/readiness evidence and must not be presented as compatible |
| A prior revision has an exact-contract ORM-created target table | Adopt the table, preserve existing rows/cursors, insert only missing seed rows, and advance normally |
| A prior revision has an incompatible same-name table | Fail closed; the DDL transaction rolls back and `alembic_version` remains unchanged |
| Catalog-dependent reconciliation runs in Alembic offline mode | Fail before emitting revision DDL and require an online PostgreSQL migration |
| Downgrade would remove adopted checkpoint data or source lineage | Reject the schema downgrade; keep the current revision and use binary rollback |

### 5. Good / Base / Bad Cases

- Good: an empty database runs `db-migrate -> db-bootstrap -> db-check`; the check reports ready and runtime starts without any write-side initialization.
- Good: an external `DATABASE_URL` deploys migrate/bootstrap/app/worker without a separate `POSTGRES_PASSWORD` and without starting the bundled `pg` service.
- Good: the process manager switches both the application UID and HOME, and HTTP readiness succeeds in the real image after migrate/bootstrap/check.
- Base: rerunning migrate/bootstrap against a current database performs no additional bootstrap mutation and still validates every immutable ledger contract.
- Base: isolated, database-agnostic unit tests may use SQLite but cannot satisfy a PostgreSQL integration acceptance criterion.
- Good: a database at revision N contains the exact ORM form of a table owned by N+1; N+1 validates and adopts it without overwriting a nonzero cursor.
- Base: application rollback keeps the expanded schema and runs the documented compatible binary; it does not delete adopted checkpoint progress.
- Bad: `has_table(...)` causes N+1 to skip `CREATE TABLE` without checking the physical contract, then stamps an unknown or partial schema as current.
- Bad: offline SQL assumes a catalog-dependent target table is absent, or downgrade drops an adopted table because the revision did not record who created it.
- Bad: API lifespan, worker import, or a health endpoint invokes Alembic, `create_all`, seed logic, administrator creation, legacy key migration, or automatic `stamp`.
- Bad: a root-owned process manager sets `user=appuser` but leaves `HOME=/root`; an isolated `db-check` passes while the managed HTTP process reports `database_unreachable`.

### 6. Tests Required

- Unit: fingerprinting is insensitive to unordered table/constraint discovery but changes when ordered composite key/index columns or CHECK constraints change.
- Unit: readiness asserts every stable code above, including name/checksum/floor drift and HTTP 503 response shape.
- PostgreSQL integration: empty and current databases, explicit legacy adoption with audit row, unknown/mismatched legacy rejection, migration rollback on injected failure, and concurrent bootstrap execution exactly once.
- PostgreSQL migration integration: from the immediately prior revision, precreate the exact ORM table and prove upgrade, seed preservation, and head convergence; drift one structural element and prove rejection, transaction rollback, and unchanged `alembic_version`.
- Migration safety: reject offline SQL for catalog-dependent reconciliation; reject destructive downgrade and prove the revision plus nonzero checkpoint cursor remain unchanged; run `alembic check` on the resulting head schema.
- PostgreSQL async integration: flush paths that use SQL-expression/server-generated timestamps perform explicit refreshes when needed; durable job enqueue allocates its stream sequence before the job insert and does not require a second job-row flush before public serialization.
- Static/deployment: runtime imports no mixed `init_db`; the image contains Alembic files; Compose resolves in bundled and external PostgreSQL modes and orders `migrate -> bootstrap -> app`; managed app processes set HOME to the selected user's home.
- Release image smoke: use the real Supervisor/Uvicorn entrypoint and assert HTTP readiness plus worker health/metrics after migrate/bootstrap/check; a CLI-only probe does not cover process-manager environment inheritance.
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

Wrong process-manager user switching:

```ini
[program:uvicorn]
user=appuser
```

Correct:

```ini
[program:uvicorn]
user=appuser
environment=HOME="/home/appuser"
```

For external PostgreSQL, pass the complete `DATABASE_URL` and omit the Compose `postgres` profile. For bundled PostgreSQL, leave `DATABASE_URL` unset and provide `POSTGRES_*`; never combine a URL from parts of both modes.

Wrong precreated-table handling:

```python
if inspector.has_table(table_name):
    return  # stamps an unverified physical schema
```

Correct:

```python
if inspector.has_table(table_name):
    validate_exact_table_contract(connection, table_name)
else:
    create_table()
insert_required_seed_on_conflict_do_nothing()
```

Wrong rollback handling:

```python
def downgrade():
    op.drop_table(adopted_checkpoint_table)
```

Correct:

```python
def downgrade():
    raise RuntimeError("use the binary rollback floor")
```

---

## Anti-patterns to avoid

- **Committing inside a repository.** Breaks the "service owns the transaction" rule.
- **Constructing `AsyncSessionLocal()` in a router** instead of `Depends(get_session)`. Known in `novels.py`, `tasks.py`, `writer.py`.
- **Celery tasks building their own engine + `sessionmaker`.** `app/tasks/emotion_tasks.py` imports the sync `sessionmaker` from `sqlalchemy.orm` and reads `settings.database_url` (the raw, possibly non-async-driver URL) instead of reusing `AsyncSessionLocal` and `settings.sqlalchemy_database_uri`. New background tasks must reuse `app.db.session.AsyncSessionLocal`.
- **Adding a model without an Alembic migration.** The migration history is the source of truth; `create_all` only creates new tables, it does not alter existing ones. Add a migration under `backend/alembic/versions/` for any column/table change.
- **Calling sync `Session.query(...)` inside an `async def` service.** An `AsyncSession`'s `sync_session` only works under a greenlet; calling it directly from an `async` method raises `MissingGreenlet` and surfaces as a 500. Use `await session.execute(select(...))` + `.scalars()`. `ConsistencyService._get_check_context` is the reference. When a service needs both DB reads and long LLM calls, commit the read transaction first so the LLM call does not hold a DB connection (see `FinalizeService.finalize_chapter`).
- **Flushing a newly inserted ORM aggregate again to assign a derived field, then synchronously serializing SQL-expression/server-generated attributes.** The update flush may expire attributes such as `updated_at`; ordinary access can trigger implicit I/O and `MissingGreenlet`. Allocate derived fields before the insert, or explicitly `await session.refresh(...)` before reading them.

## LangGraph PostgreSQL Checkpoint Schema

- The pinned runtime contract is `langgraph==1.2.2`, `langgraph-checkpoint==4.1.1`, `langgraph-checkpoint-postgres==3.1.0`, `psycopg==3.3.4`, `psycopg-pool==3.3.1`, and `orjson==3.11.9`. Deployment uses the matching Psycopg binary build so the runtime image does not depend on an implicit system `libpq` resolution.
- Alembic exclusively owns the vendor `checkpoint_migrations`, `checkpoints`, `checkpoint_blobs`, and `checkpoint_writes` tables and their pinned migration rows. API and worker startup may validate this schema but must never call `AsyncPostgresSaver.setup()` or execute fallback DDL.
- `db-check` is read-only and fails closed when a required checkpoint table, constraint, index, or pinned vendor migration version is missing or newer than the binary understands. Checkpoint schema contributes to the binary rollback floor.
- Psycopg connection parameters are derived structurally from the configured SQLAlchemy URL. Do not replace driver names, credentials, query parameters, or search paths with string substitution.
- PostgreSQL tests give asyncpg and Psycopg connections the same random schema/database. Vendor tables must be proven present in that namespace and absent from `public`; `search_path` fallback is not isolation evidence.
- Test cleanup owns the random namespace before creation, closes the checkpointer connection/pool and SQLAlchemy engines on every failure path, then executes `DROP SCHEMA ... CASCADE`. A failed setup, seed, or checkpoint write must not leak a `test_*` schema.
- Checkpointer `setup()` is permitted only in a dependency smoke test that discovers/verifies the pinned vendor schema inside a disposable namespace. Application integration tests and runtime paths use the Alembic-installed schema.

### Disposable PostgreSQL test database

#### 1. Scope / Trigger

Apply whenever pytest uses PostgreSQL through `TEST_POSTGRES_URL`, including migration,
locking, durable worker, LangGraph checkpoint, and independent-process tests. The
configured URL locates a PostgreSQL service; it is never the database that tests mutate.

#### 2. Signatures

```text
TEST_POSTGRES_URL=postgresql+asyncpg://<user>:<password>@<host>:<port>/<service-database>

_temporary_postgres_engine(database_url: str | URL) -> AsyncIterator[AsyncEngine]
_pg_engine -> session-scoped AsyncEngine(database="mofeng_pytest_<uuid>")
```

The service account must connect to the `postgres` administration database, create and
drop databases, terminate connections to databases it created, and install the
`vector` extension in a new database.

#### 3. Contracts

- Build the administration and test URLs with SQLAlchemy `URL` operations so driver,
  credentials, host, port, and unrelated query parameters are preserved.
- Create one random `mofeng_pytest_<uuid>` database per pytest session. Install
  `vector`, create the complete ORM metadata with `checkfirst=False`, and seed executor
  control before yielding its engine.
- Independent-connection tests may create an additional random `test_<uuid>` schema
  inside that database. asyncpg and Psycopg must use the same database and schema.
- The configured service database and its `public` schema are never isolation
  boundaries. Tests must not delete, truncate, seed, or otherwise clean business rows.
- Cleanup ownership starts before `CREATE DATABASE`. Immediately after that statement
  succeeds, record that the database exists. On every later failure, dispose test
  engines, terminate remaining sessions, drop the random database, and finally dispose
  the administration engine.

#### 4. Validation & Error Matrix

| Condition | Required result |
|-----------|-----------------|
| `postgres` administration database is unreachable | Fail before creating test state; report the connection prerequisite |
| Account lacks database or extension privileges | Fail setup; drop any random database already created |
| Metadata creation, seed, Psycopg validation, or checkpoint write fails | Close both drivers and remove the random schema/database |
| A connection remains attached at teardown | Terminate only sessions whose `datname` is the generated test database, then drop it |
| A table resolves only through `public` | Fail the qualified table/schema assertion; never accept fallback as isolation |
| Configured business rows change | Fail the resource audit; test cleanup must never repair them with `DELETE` |

#### 5. Good / Base / Bad Cases

- Good: two pytest sessions use distinct random databases, and a child worker receives
  the generated database URL rather than the configured service database URL.
- Base: setup fails after `CREATE DATABASE`; teardown still removes the database and
  leaves no `test_*` schema or test-tagged connection.
- Bad: connect the session fixture directly to `TEST_POSTGRES_URL`, use business
  `public` plus transaction rollback as isolation, or clean shared rows after a test.

#### 6. Tests Required

- Assert the session engine database starts with `mofeng_pytest_` and differs from the
  configured service target.
- Inject metadata, seed, Psycopg validation, and checkpoint-write failures; assert the
  generated database/schema and application-named connections are absent afterward.
- Run a real asyncpg/Psycopg checkpoint round trip and prove vendor tables exist only
  in the selected random schema.
- After full and independent-process suites, audit zero `mofeng_pytest_*` databases,
  zero `test_*` schemas, zero test-tagged connections, and unchanged business counts.

#### 7. Wrong vs Correct

```python
# Wrong: TEST_POSTGRES_URL becomes the mutable test target.
engine = create_async_engine(os.environ["TEST_POSTGRES_URL"])
async with engine.begin() as connection:
    await connection.run_sync(Base.metadata.create_all)

# Correct: the configured URL locates the service; the context owns a disposable DB.
async with _temporary_postgres_engine(os.environ["TEST_POSTGRES_URL"]) as engine:
    yield engine
```

### Checkpoint autogenerate ownership

1. **Scope / Trigger**: apply whenever a migration, readiness check, or pinned checkpoint schema identifier changes.
2. **Signatures**: `CHECKPOINT_TABLES` and `CHECKPOINT_MIGRATION_VERSIONS` live in `app.db.chapter_workflow_checkpoint_schema`; Alembic passes `include_object=include_object` in online and offline configuration.
3. **Contracts**: migrations create and upgrade the four vendor tables, readiness inspects them, while autogenerate excludes reflected objects belonging to those tables. ORM `Base.metadata` must not pretend to own vendor DDL.
4. **Validation & Error Matrix**: a missing table/version makes readiness fail closed; a valid pinned table must not produce Alembic `remove_table/remove_index`; drift in ordinary business tables must still fail `alembic check`.
5. **Good / Base / Bad**: good is one shared identifier contract used by readiness and Alembic; base is a head database with no autogenerate diff; bad is importing a runtime engine into Alembic or adding vendor tables to ORM metadata solely to silence diffs.
6. **Tests Required**: upgrade an isolated PostgreSQL database to head, run `alembic check`, assert all four tables and exact pinned versions remain, and prove a LangGraph checkpoint round trip without calling `setup()`.
7. **Wrong vs Correct**:

```python
# Wrong: Alembic sees reflected vendor tables as deletions.
context.configure(connection=connection, target_metadata=Base.metadata)

# Correct: retain schema validation while excluding external ORM ownership.
context.configure(
    connection=connection,
    target_metadata=Base.metadata,
    include_object=include_object,
)
```
