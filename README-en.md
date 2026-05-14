# MoFeng (墨风)

> AI-assisted long-form novel creation system for ideation, blueprint generation, chapter writing, review, and admin management.

[中文](./README.md) | English

## Overview

MoFeng (墨风) is a full-stack writing assistant for long-form fiction. It supports the end-to-end workflow from concept conversation to blueprint confirmation, chapter drafting, version review, foreshadowing analysis, and project management.

Current stack:

- Frontend: Vue 3 + Vite + TypeScript + TanStack Query for Vue + Pinia + Vue Router + Naive UI
- Backend: FastAPI + SQLAlchemy + Pydantic Settings
- Storage: SQLite or MySQL, plus libsql for vector retrieval
- AI: OpenAI-compatible LLM APIs, OpenAI/Ollama embeddings

## Frontend state management

The frontend has been migrated to TanStack Query for Vue:

- API requests, server-state caching, refresh, retry, and loading/error states are handled by TanStack Query
- Novel projects, chapters, detail materials, admin data, LLM settings, auth/register flows, and update logs are accessed through Query composables
- Pinia only keeps client state, such as the auth token, current user, and temporary inspiration-flow conversation state
- The shared Query Client lives in `frontend/src/lib/queryClient.ts`
- Business Query composables live in `frontend/src/queries/`

## Core workflow

1. Sign in or register
2. Configure personal LLM and embedding models in Settings
3. Start a project in Inspiration Mode through multi-turn idea conversation
4. Generate and confirm a structured blueprint
5. Manage projects in Workspace
6. Review worldbuilding, characters, outlines, chapters, and analysis in Detail
7. Generate, review, select, and edit chapter content in Writing Desk
8. Manage users, prompts, updates, and system configuration in Admin

## Features

- Multi-turn inspiration chat for project creation
- Blueprint generation and persistence
- Chapter drafting, evaluation, version selection, and editing
- Outline generation and maintenance
- Foreshadowing tracking and status sync
- Emotion curve and analytics views
- `.txt` novel import
- User, prompt, update log, and system configuration management

## Quick start

### Local development

Backend:

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
copy env.example .env   # Windows
# cp env.example .env   # macOS / Linux
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Default access URLs:

- Frontend: `http://127.0.0.1:5173`
- API: `http://127.0.0.1:8000`
- Swagger: `http://127.0.0.1:8000/docs`

Optional launcher scripts from repo root:

- Windows CMD: `dev.bat`
- PowerShell: `powershell -ExecutionPolicy Bypass -File .\dev.ps1`
- Bash: `bash ./dev.sh`

Launcher script behavior:

- If `frontend/node_modules` is missing, dependencies are installed automatically
- If `backend/.venv` is missing, the virtual environment is created automatically
- If `uvicorn` is missing from the selected Python environment, `backend/requirements.txt` is installed automatically
- If default ports `8000` or `5173` are occupied, the script switches to the next available port
- Frontend and backend dev servers listen on `0.0.0.0`, so they can be reached from other devices on the local network
- The script prints the local access URL and the effective API proxy target after startup

### Docker (local)

```bash
# Windows
copy deploy\.env.example deploy\.env
# macOS / Linux
# cp deploy/.env.example deploy/.env

docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d --build
```

Default access URL:

- `http://127.0.0.1:8088`

To start with the bundled MySQL profile:

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile mysql up -d --build
```

## Configuration

For local development, use `backend/env.example` as the template for `backend/.env`.

Minimum required settings:

- `SECRET_KEY`
- `DB_PROVIDER`
- `SQLITE_DB_PATH` when using SQLite

Recommended for writing features:

- `OPENAI_API_KEY`
- `OPENAI_API_BASE_URL`
- `OPENAI_MODEL_NAME`
- `EMBEDDING_PROVIDER`
- `EMBEDDING_MODEL`
- `VECTOR_DB_URL`
- `ADMIN_DEFAULT_USERNAME`
- `ADMIN_DEFAULT_PASSWORD`

For Docker deployment, use `deploy/.env.example` as the template for `deploy/.env`.

## Initialization behavior

On first backend startup, the application automatically:

1. Ensures the database exists
2. Creates missing tables
3. Backfills missing legacy fields
4. Creates the default admin account if none exists
5. Imports `backend/prompts/*.md` into the database if missing
6. Syncs default system configuration

## Project structure

```text
.
├─ backend/                  # FastAPI backend
│  ├─ app/
│  │  ├─ api/                # Routers
│  │  ├─ core/               # Config, security, dependencies
│  │  ├─ db/                 # DB setup and initialization
│  │  ├─ models/             # ORM models
│  │  ├─ repositories/       # Data access layer
│  │  ├─ schemas/            # Pydantic schemas
│  │  └─ services/           # Business services
│  ├─ prompts/               # Default prompt templates
│  └─ env.example
├─ frontend/                 # Vue frontend
│  ├─ src/
│  │  ├─ api/                # API clients and types
│  │  ├─ components/
│  │  ├─ lib/                # Frontend infrastructure such as Query Client
│  │  ├─ queries/            # TanStack Query composables
│  │  ├─ router/
│  │  ├─ stores/             # Pinia client state
│  │  └─ views/
├─ deploy/                   # Docker, Nginx, Compose
├─ docs/                     # Supplementary docs
├─ dev.bat
├─ dev.ps1
└─ dev.sh
```

## Secondary development notes

This repository has already been adapted for secondary development. Before publishing your own fork or deployment, review at least the following:

- `VERSION_INFO_URL`
- `IMAGE_REPO`
- `EMAIL_FROM`
- Linux.do OAuth settings if enabled
- Default admin credentials

A more detailed deployment guide is available in [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md).

## License

Please refer to the actual `LICENSE` file or your project distribution policy.
