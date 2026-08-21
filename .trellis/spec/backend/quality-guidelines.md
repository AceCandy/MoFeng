# Backend Quality Guidelines

> Cross-cutting rules: async discipline, Pydantic, config, Celery, testing, and the AIMETA header.

---

## Async/sync discipline

- Application business/runtime DB I/O goes through `AsyncSession` and is awaited. Alembic may use SQLAlchemy's documented synchronous callback through `run_sync`.
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
- For routes under generated transport ownership, the Pydantic request/response model is
  the only field-level wire source. Regenerate `backend/openapi.json` and
  `frontend/src/api/generated/schema.d.ts`; never patch either artifact or restate the
  fields in a frontend interface. See [transport-contracts](./transport-contracts.md).
- A handler rename can change the compatibility-preserving operation ID. Pin the old
  explicit `operation_id` before an internal rename unless the public identifier is
  intentionally going through a compatibility rollout.

Bad example — defining schemas inline in a router (`app/api/routers/foreshadowing.py`). Put them in `app/schemas/`.

---

## Config (pydantic-settings)

`app/core/config.py` defines `Settings(BaseSettings)` with standard field-name environment loading, Pydantic v2 validation aliases for compatibility names, computed DB-URL `@property`s, and an `lru_cache`-backed module-level singleton `settings`.

```python
class Settings(BaseSettings):
    app_name: str = Field(default="AI Novel Generator API", description="FastAPI 文档标题")
    debug: bool = Field(default=True, description="是否开启调试模式")
    secret_key: str = Field(..., description="JWT 加密密钥")
    allow_registration: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "ALLOW_USER_REGISTRATION",
            "ALLOW_REGISTRATION",
        ),
    )
    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
```

Rules for new config:

- Standard environment names are inferred from the Python field name (`secret_key` → `SECRET_KEY`); do not pass the deprecated `env=` extra keyword to `Field`.
- Use `validation_alias=AliasChoices(...)` only for a non-standard canonical name or backwards-compatible rename. Put the canonical name first so it wins when both variables exist.
- Keep `populate_by_name=True` so tests and internal callers may construct `Settings` with Python field names even when a validation alias exists.
- Compute derived values such as the DB URL as `@property`s (`sqlalchemy_database_uri`), not stored fields.
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
- PostgreSQL locking, migration, lease/fencing, event ordering, and async-driver behavior require PostgreSQL integration tests; SQLite cannot satisfy those acceptance criteria.
- Durable worker recovery requires independent OS processes: terminate the lease owner, start a second worker, wait for lease expiry, and assert attempt/fencing increments, event order, and the single valid final outcome. Simulated method calls alone are not recovery evidence.
- Test external provider dedupe and ambiguous-result dead-letter separately. Database fencing is not evidence of external exactly-once execution.
- Route/schema changes under generated transport ownership run the hermetic OpenAPI
  contract tests plus `npm run api:check`. Byte drift and semantic compatibility are
  separate gates; passing one is not evidence for the other.
- Deterministic ordering tests that tie an `onupdate` timestamp must explicitly write
  every compared timestamp in the same SQL update. Reassigning the same ORM value may
  not mark it dirty, allowing `onupdate=func.now()` to replace the intended tie.

## PostgreSQL pytest profiles

### 1. Scope / Trigger

Apply when a backend test requires the shared PostgreSQL engine, transactional session
factory, or isolated multi-connection schema. Fast tests must remain collectable and
runnable without Docker or Testcontainers.

### 2. Signatures

```bash
pytest -m "not postgres" --strict-markers
pytest -m postgres --strict-markers
TEST_POSTGRES_URL="postgresql+asyncpg://..." pytest -m postgres --strict-markers
```

### 3. Contracts

- Register `postgres` in `backend/pytest.ini`.
- `pytest_collection_modifyitems` classifies the fixture closure before marker
  filtering. Tests using `_pg_engine`, `db_session_factory`, or `isolated_pg` receive
  the marker automatically.
- A new independent PostgreSQL fixture must depend on `_pg_engine` or mark its tests
  explicitly.
- Import Testcontainers only inside `_pg_engine` when `TEST_POSTGRES_URL` is absent.
  Fast collection must not import Testcontainers or access Docker.
- Both PostgreSQL entry paths reuse the disposable database contract in
  [Database Guidelines](./database-guidelines.md); the configured service database is
  never the mutable test target.

### 4. Validation & Error Matrix

| Condition | Required result |
| --- | --- |
| Fast profile without Docker | Collect and run non-PostgreSQL tests without importing Testcontainers |
| PostgreSQL fixture appears in the closure | Select under `-m postgres` and deselect under `-m "not postgres"` |
| `TEST_POSTGRES_URL` is configured | Use the external service to create a disposable database |
| `TEST_POSTGRES_URL` is absent | Lazily import Testcontainers and start `pgvector/pgvector:pg16` |
| Marker is misspelled or unregistered | `--strict-markers` fails collection |

### 5. Good / Base / Bad Cases

- Good: both profiles collect to complementary sets, and both PostgreSQL entry paths
  pass the isolation tests.
- Base: a unit test has ordinary fixtures only and never loads Docker dependencies.
- Bad: importing Testcontainers at conftest module scope, moving every database test to
  a duplicate directory tree, or replacing PostgreSQL acceptance with SQLite.

### 6. Tests Required

- Unit-test the fixture-name classifier with PostgreSQL and ordinary fixture names.
- Collect both marker expressions with `--strict-markers`; their selected counts must
  sum to the unfiltered collection count.
- Run `test_postgres_isolation.py` once through `TEST_POSTGRES_URL` and once through the
  container fallback; assert disposable database cleanup in both paths.

### 7. Wrong vs Correct

```python
# Wrong: every pytest collection imports Docker integration code.
from testcontainers.postgres import PostgresContainer

# Correct: only the selected container fallback imports Testcontainers.
async def _pg_engine():
    if configured_url:
        ...
        return
    from testcontainers.community.postgres import PostgresContainer
```

## External structured artifact verification

### 1. Scope / Trigger

Apply this contract when a CI or release gate parses JSON emitted by a pinned external
tool or registry, or reads repository metadata through shell. Producer configuration
proves requested behavior, not the emitted schema; verify field paths against a
redacted artifact produced by the pinned version and preserve JSON bytes across shell
expansion boundaries.

### 2. Signatures

BuildKit provenance is read with:

```bash
docker buildx imagetools inspect <digest-or-tag> --format '{{json .Provenance}}'
```

Release metadata is read and queried with:

```bash
metadata_json="$(git show origin/main:release-metadata/version-info.json)"
metadata_digest="$(jq -r '.image_digest // empty' <<<"${metadata_json}")"
```

### 3. Contracts

For each expected platform, require `SLSA` and validate:

- `.buildDefinition.buildType` is the BuildKit SLSA definition URL.
- `.buildDefinition.externalParameters.request.args["build-arg:APP_VERSION"]` is the
  planned version.
- `.buildDefinition.externalParameters.request.root.request.args["vcs:source"]` is the
  repository URL.
- `.buildDefinition.externalParameters.request.root.request.args["vcs:revision"]` is
  the source commit.

Do not read source identity from `root.configSource.request.args` or
`runDetails.metadata.vcs`; those paths are not part of the observed BuildKit output.

Pass repository metadata to `jq` unchanged. An empty string is a valid no-metadata
input for this query and produces an empty digest. Do not embed a brace-bearing JSON
default such as `{}` inside `${parameter:-word}`; Bash can leave the closing brace as
literal input and turn valid JSON into `...}}`.

### 4. Validation & Error Matrix

| Condition | Required behavior |
| --- | --- |
| Platform key or `SLSA` is missing | Fail the release gate |
| Source, revision, version, or build type differs | Fail the release gate |
| Provenance uses an unverified/obsolete path | Fail the contract test before dry-run |
| Metadata JSON is malformed after shell expansion | Fail before baseline selection |
| Metadata is absent | Produce an empty digest and continue through the empty-baseline rules |
| All expected platforms and fields match | Continue to digest scanning and smoke |

### 5. Good / Base / Bad Cases

- Good: a multi-platform map has exactly the expected platform keys and every SLSA
  entry matches repository, source commit, and version.
- Base: a legacy single-platform artifact exposes top-level `SLSA`; validate the same
  fields and require exactly one expected platform.
- Base: absent repository metadata yields an empty digest without manufacturing a JSON
  default inside shell parameter expansion.
- Bad: the producer was configured with `provenance: mode=max`, but the verifier assumes
  undocumented paths or skips emitted-value checks.
- Bad: `${metadata_json:-{}}` appends a literal closing brace to non-empty JSON before
  `jq` parses it.

### 6. Tests Required

- Workflow contract tests assert the required `root.request.args` paths appear in both
  candidate and baseline verifiers.
- Tests reject known obsolete `root.configSource` and `runDetails.metadata.vcs` paths.
- Execute the workflow's metadata query line with normal, legacy, and empty metadata;
  assert the digest is preserved or empty and the shell command exits successfully.
- Before enabling formal promotion, run the verifier against a real candidate artifact
  from the pinned action/tool chain and confirm each platform passes.

### 7. Wrong vs Correct

```jq
# Wrong: paths were inferred instead of observed.
.buildDefinition.externalParameters.request.root.configSource.request.args["vcs:source"]

# Correct: path verified against the emitted BuildKit provenance.
.buildDefinition.externalParameters.request.root.request.args["vcs:source"]
```

```bash
# Wrong: Bash may append a literal `}` when metadata_json is non-empty.
jq -r '.image_digest // empty' <<<"${metadata_json:-{}}"

# Correct: jq accepts empty input and the JSON crosses the shell boundary unchanged.
jq -r '.image_digest // empty' <<<"${metadata_json}"
```

## Release image vulnerability gate

### 1. Scope / Trigger

Apply this contract when the pinned Trivy gate reports `HIGH` or `CRITICAL`
vulnerabilities from the final release image, including findings inherited from its
base image or packaging-tool metadata.

### 2. Signatures

The release gate scans each platform digest with Trivy using
`severity: HIGH,CRITICAL` and `exit-code: "1"`. Local verification must scan the
built runtime image with the same Trivy version and severity threshold.

### 3. Contracts

- Fix the vulnerable final-image contents or select a base image that can satisfy the
  gate; do not weaken the gate to accommodate the current image.
- Remove build-only packaging tools from the runtime filesystem when the application
  does not require them.
- A base-image family change must preserve the configured nginx path, supervisor
  startup, UID `1000`, runtime dependency imports, and release smoke behavior.

### 4. Validation & Error Matrix

| Condition | Required behavior |
| --- | --- |
| Any platform has a HIGH/CRITICAL finding | Stop before smoke and promotion |
| Only an unfixed base-image finding remains | Change/fix the image; do not ignore it |
| Scan is clean but app or worker smoke fails | Stop before promotion |
| Every platform scan and digest smoke pass | Continue to candidate verification |

### 5. Good / Base / Bad Cases

- Good: the final multi-platform image has zero HIGH/CRITICAL findings and its digest
  passes database, HTTP, and worker smoke.
- Base: a local single-platform runtime build is scanned and smoked before pushing a
  workflow fix; GitHub still performs the authoritative multi-platform check.
- Bad: `ignore-unfixed`, VEX, an exception list, or `continue-on-error` makes a known
  release-image vulnerability non-blocking.

### 6. Tests Required

- Contract tests pin the intended base-image family, package-manager command, removal
  of unused packaging tools, Trivy severity/exit behavior, and explicit smoke command.
- Build the runtime target, scan the final image, and run the digest-only smoke script
  through isolated PostgreSQL before promotion.
- The repository dry-run must prove both platform scans and smoke pass without changing
  version tags, `latest`, Git tags, or release metadata.

### 7. Wrong vs Correct

```yaml
# Wrong: hides a known release-image vulnerability.
ignore-unfixed: true

# Correct: keep the blocking gate and fix the image contents.
severity: HIGH,CRITICAL
exit-code: "1"
```

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
- Editing canonical/generated transport artifacts by hand, or recreating a migrated
  Pydantic response shape as a TypeScript interface/object-literal alias.

---

## Review checklist

- [ ] New module has an `AIMETA` header on line 1.
- [ ] Router uses `Depends(get_session)` / `Depends(get_<x>_service)`; no manual `AsyncSessionLocal()`.
- [ ] Repository subclasses `BaseRepository` and only `flush()`es.
- [ ] Service owns `commit()`/`rollback()`; raises `ValueError` on business failure, not `HTTPException`.
- [ ] A flush-time SQL-expression/server-generated value is read only after an explicit awaited refresh/query; new aggregates receive derived fields before their insert flush.
- [ ] DTOs in `app/schemas/`, `response_model=` declared, `from_attributes = True` on Read models.
- [ ] Generated-ownership route/schema changes update both committed artifacts and pass
  exporter/type-generation byte checks plus the ownership guard.
- [ ] Internal handler renames preserve the prior operation ID, or the public rename has
  an explicit compatibility plan and semantic-diff evidence.
- [ ] Outbound HTTP is `httpx.AsyncClient`; sync libs wrapped with `asyncio.to_thread`.
- [ ] Logger declared at module top with `getLogger(__name__)`; uses `%s` args.
- [ ] No secrets in log lines.
- [ ] Schema change shipped as an Alembic migration under `backend/alembic/versions/` (see [database-guidelines](./database-guidelines.md)).
- [ ] Durable job changes follow [durable-job-guidelines](./durable-job-guidelines.md), including public projection, fencing, event atomicity, and real-process recovery gates.
