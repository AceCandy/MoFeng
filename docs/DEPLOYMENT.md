# Deployment Guide

This document focuses on local deployment and secondary development setup for the current codebase.

## 1. Deployment modes

The repository currently supports two practical ways to run the project:

1. Local development: frontend and backend started separately
2. Local Docker deployment: full stack started with Docker Compose

Remote server deployment scripts may still exist in the repository, but they are not treated as the standard deployment path for this fork.

## 2. Local development

### 2.1 Prerequisites

- Python 3.10+
- Node.js 18+
- npm
- Optional: a Python virtual environment

### 2.2 Backend

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
```

Create the environment file:

```bash
# Windows
copy env.example .env

# macOS / Linux
# cp env.example .env
```

Prepare the database, then start the backend runtime:

```bash
python -m app.db.cli db-migrate
python -m app.db.cli db-bootstrap
python -m app.db.cli db-check
uvicorn app.main:app --reload
```

Default URLs:

- API: `http://127.0.0.1:6101`
- Swagger: `http://127.0.0.1:6101/docs`
- Liveness: `http://127.0.0.1:6101/api/health`
- Readiness: `http://127.0.0.1:6101/api/ready`

### 2.3 Frontend

```bash
cd frontend
npm install
npm run dev
```

Default URL:

- Frontend: `http://127.0.0.1:6100`

### 2.4 Root-level helper scripts

You can also start both services from the repository root.

Windows CMD:

```bat
dev.bat
```

PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\dev.ps1
```

Bash:

```bash
bash ./dev.sh
```

Helper script behavior:

- If `frontend/node_modules` is missing, frontend dependencies are installed automatically.
- If `backend/.venv` is missing, the backend virtual environment is created automatically.
- If the selected Python environment is missing `uvicorn`, backend dependencies from `backend/requirements.txt` are installed automatically.
- Before starting uvicorn, the scripts run `db-migrate`, `db-bootstrap`, and `db-check` in order.
- If default ports `6101` or `6100` are occupied, the scripts switch to the next available port.
- Frontend and backend listen on `0.0.0.0`, so the dev environment can be opened from other devices on the local network.
- After startup, the scripts print the local frontend URL and the effective local API proxy target.

Notes:

- `dev.ps1` starts the frontend through `cmd.exe /c npm.cmd run dev`, which avoids common PowerShell npm shim issues on Windows.
- If `backend/.env` is missing, the backend may start but core features will not be usable until configuration is completed.

## 3. Local Docker deployment

### 3.1 Prepare environment file

Use `deploy/.env.example` as the template:

```bash
# Windows
copy deploy\.env.example deploy\.env

# macOS / Linux
# cp deploy/.env.example deploy/.env
```

At minimum, review and update:

- `SECRET_KEY`
- `OPENAI_API_KEY`
- `OPENAI_MODEL_NAME`
- `ADMIN_DEFAULT_PASSWORD`

Recommended for forks:

- `VERSION_INFO_URL`
- `IMAGE_REPO`
- `EMAIL_FROM`
- `ENABLE_LINUXDO_LOGIN` and related OAuth settings

### 3.2 Start with bundled PostgreSQL

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile postgres up -d --build
```

Compose starts the shared application image in three roles: one-shot `migrate`, one-shot `bootstrap`, then `app`. `app` depends on successful completion of both database roles. The migration command includes its own connection wait, so the same Compose file also works with an external PostgreSQL server without a hard dependency on the optional `pg` profile.

For external PostgreSQL, set the complete `DATABASE_URL` and omit `--profile postgres`:

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d --build
```

In this mode `DATABASE_URL` takes precedence over `POSTGRES_*`; a separate `POSTGRES_PASSWORD` is not required and the bundled `pg` service is not started.

Default access URL:

- `http://127.0.0.1:6100`

The actual external port comes from `APP_PORT` in `deploy/.env`.

### 3.3 View logs

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml logs -f
```

### 3.4 Stop services

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml down
```

## 4. Environment configuration

### 4.1 Local development: `backend/.env`

Template: `backend/env.example`

Minimum startup configuration:

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | JWT signing secret |
| `DATABASE_URL` | One database mode required | Complete external PostgreSQL URL; no separate `POSTGRES_PASSWORD` is required |
| `POSTGRES_PASSWORD` | Required when `DATABASE_URL` is unset | Bundled/composed PostgreSQL password; other `POSTGRES_*` values have defaults and may be overridden |

Recommended for writing features:

| Variable | Recommended | Description |
|---|---|---|
| `OPENAI_API_KEY` | Yes | Default LLM API key |
| `OPENAI_API_BASE_URL` | As needed | OpenAI-compatible API base URL |
| `OPENAI_MODEL_NAME` | Yes | Default generation model |
| `VECTOR_STORE_ENABLED` | No | Enable pgvector RAG retrieval (default true) |
| `BOOTSTRAP_CREATE_DEFAULT_ADMIN` | As needed | Create a default admin during explicit bootstrap (default true) |
| `ADMIN_DEFAULT_USERNAME` | Yes | Default admin username |
| `ADMIN_DEFAULT_PASSWORD` | Strongly recommended | Default admin password |
| `ALLOW_USER_REGISTRATION` | As needed | Whether users can sign up |
| `SMTP_*` | As needed | Email verification support |

### 4.2 Docker deployment: `deploy/.env`

Template: `deploy/.env.example`

Additional common variables:

- `APP_PORT`: exposed application port
- `DATABASE_URL`: complete external PostgreSQL URL; takes precedence and does not start bundled PostgreSQL
- `POSTGRES_*`: PostgreSQL connection parts and bundled PostgreSQL configuration when `DATABASE_URL` is unset
- `IMAGE_REPO`: image repository name

## 5. Database lifecycle commands

The API runtime performs no schema or data mutation. Installation and deployment orchestration use separate commands:

```bash
cd backend
python -m app.db.cli db-create      # optional; installation-only CREATE DATABASE
python -m app.db.cli db-migrate     # Alembic upgrade head only
python -m app.db.cli db-bootstrap   # versioned defaults and data migrations
python -m app.db.cli db-check       # read-only readiness check
```

`db-bootstrap` creates the default administrator only when enabled and no administrator exists. Active system configuration and prompt defaults are inserted only when missing, so user values are not overwritten. The initial immutable version also deletes only the explicitly obsolete system keys and the obsolete `character_dna_guide` prompt. Historical provider API keys are encrypted by a separate version without logging key values. Every version records its checksum, completion status, and minimum compatible binary version.

If `db-migrate` finds business tables without `alembic_version`, it fails closed and reports a schema fingerprint. Do not stamp it manually. After verifying the fingerprint is a registered baseline and taking a backup, adoption is explicit:

```bash
python -m app.db.cli db-adopt-legacy \
  --operator release-operator \
  --expected-fingerprint <fingerprint-from-db-migrate> \
  --backup-confirmed
python -m app.db.cli db-bootstrap
python -m app.db.cli db-check
```

Unknown or partial schemas are not modified. Data bootstrap is forward-only; rollback is limited to binaries that understand the ledger rollback floor.

### 5.1 F2 projection telemetry and retention migration

The expected Alembic head for this release is `f2a6c9d4e8b1`. It is an expand-only
migration: it adds nullable pricing columns to `user_ai_models`, creates
`ai_usage_records`, and creates the append-only
`chapter_projection_retention_audits` table and indexes. It does not remove or
rewrite canonical chapter data. PostgreSQL still needs a reviewed DDL lock window.

Before production deployment, validate the release against both an empty database
and a restored copy of the current production database:

```bash
cd backend
alembic heads
python -m app.db.cli db-migrate
python -m app.db.cli db-bootstrap
python -m app.db.cli db-check
```

`alembic heads` must report exactly `f2a6c9d4e8b1`. Run the remaining three commands
once against each validation database. Do not use an unverified production database
as the empty-database test.

Production sequence:

1. Take a database backup and verify that the restore procedure can open the copy.
2. Capture `python -m app.worker health` and `python -m app.worker metrics`, then stop
   durable job workers and outbox consumers. Put write traffic in maintenance mode,
   or explicitly accept that outbox backlog will grow while consumers are paused.
3. Run `db-check` with the currently deployed binary. Resolve any schema, bootstrap,
   or rollback-floor error before migration.
4. Run `db-migrate`, `db-bootstrap`, and `db-check` with the release binary. Confirm
   that the database is at `f2a6c9d4e8b1` before starting a worker.
5. Start one candidate worker, verify health and metrics, then restore the remaining
   workers. Investigate any projection cost/usage or external-activity alert before
   rollout cutover.

If migration or readiness fails, keep workers and outbox consumers paused. Do not
invoke Alembic downgrade: F2 intentionally raises an error because usage and
retention rows are audit data. Fix forward from the preserved database state. Restore
the backup only under the approved maintenance procedure when no post-backup writes
must be retained.

A binary rollback leaves the schema at F2. The rollback candidate must pass
`db-check`, understand the bootstrap ledger rollback floor, and tolerate the added
columns and tables. `binary_below_rollback_floor` is a hard stop; never work around it
by stamping Alembic or dropping audit tables.

After deployment, use `python -m app.worker metrics` for cost/usage completeness and
the bounded `projection-retention-preview` / `projection-retention-purge` commands for
inactive artifact cleanup. The exact safety gates and command examples are in
`docs/runbooks/chapter-projections.md`.

## 6. Default admin account

The default admin comes from environment variables:

- `BOOTSTRAP_CREATE_DEFAULT_ADMIN`
- `ADMIN_DEFAULT_USERNAME`
- `ADMIN_DEFAULT_PASSWORD`
- `ADMIN_DEFAULT_EMAIL`

Set `ADMIN_DEFAULT_PASSWORD` to a strong password before first startup (the `.env.example` placeholder is rejected in production). The default admin username is `admin`. Change the password immediately after the first login.

## 7. Secondary development checklist

For your own fork or branded deployment, review these items before release:

### 7.1 Branding and external references

- Replace `VERSION_INFO_URL` with your own release metadata URL
- Review `IMAGE_REPO`
- Review visible product naming and email sender values

### 7.2 Authentication options

- Check whether `ALLOW_USER_REGISTRATION` should be enabled
- Check whether `ENABLE_LINUXDO_LOGIN` should remain enabled
- If Linux.do login is enabled, replace all OAuth credentials and redirect URLs

### 7.3 Model configuration expectations

Even when the backend has default models configured, the current frontend flow still expects users to save personal model settings before entering Inspiration Mode.

### 7.4 Dependency between frontend and backend

If the frontend opens but keeps loading, check these first:

- Backend is actually running on the printed backend port
- The printed local API proxy target is reachable
- `/api/auth/options` is reachable
- Current login state is valid

## 8. Troubleshooting

### 8.1 Frontend page keeps loading in development

Check:

- `http://127.0.0.1:6101/docs`
- `http://127.0.0.1:6101/api/health` for liveness
- `http://127.0.0.1:6101/api/ready` for database readiness

The frontend depends on backend APIs during startup and route restoration.

### 8.2 Inspiration Mode cannot start

Check:

1. You are logged in
2. LLM and embedding models were saved in Settings
3. The backend can reach the configured AI provider

### 8.3 Docker is up but the page is not reachable

Check:

1. Whether `APP_PORT` is already occupied
2. Container readiness status
3. Compose logs for `migrate`, `bootstrap`, and `app`

## 9. Related files

- `README.md`
- `README-en.md`
- `backend/env.example`
- `docs/runbooks/chapter-projections.md`
- `deploy/.env.example`
- `deploy/docker-compose.yml`
- `deploy/Dockerfile`
- `deploy/nginx.conf`
