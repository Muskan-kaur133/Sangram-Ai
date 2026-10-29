# Sangram AI Backend

FastAPI + SQLAlchemy + Alembic backend for the Sangram AI dialectic arena.

This service owns authentication, user profiles, battle orchestration, SSE
streaming, saved answers/ADRs, sharing, catalog data, and health probes.

> **Stack note:** this backend is Python/FastAPI, not Node/Express. There is no
> `package.json` here. Node/npm commands belong to `frontend/`.

## Prerequisites

- **Python 3.11+**
- **Docker Desktop** with Docker Compose
- **Git**
- **Make** (optional, recommended for the shortcuts below)

## Quick start

```bash
cd backend

# 1. Create the local environment file (never commit .env)
cp .env.example .env

# 2. Start PostgreSQL
docker compose up -d postgres

# 3. Create and activate a virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# 4. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 5. Apply migrations
alembic upgrade head

# 6. Create the optional development demo user
python -m app.db.seed

# 7. Start the API
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open:

- API: <http://127.0.0.1:8000>
- Health: <http://127.0.0.1:8000/health>
- Readiness: <http://127.0.0.1:8000/health/ready>
- Swagger UI: <http://127.0.0.1:8000/docs>
- ReDoc: <http://127.0.0.1:8000/redoc>

### Makefile shortcuts

From `backend/`:

```bash
make venv          # create .venv with Python 3.11+
make install       # install requirements
make db-up         # docker compose up -d postgres
make db-migrate    # alembic upgrade head
make db-seed       # create the development demo user
make dev           # uvicorn with reload on 127.0.0.1:8000
make test          # pytest -q
make lint          # ruff check .
make format        # ruff format .
make typecheck     # byte-compile app and tests
make db-down       # stop docker compose services
make help          # show all targets
```

`make` defaults to `.venv/bin/python`. Override it when needed:

```bash
make test PYTHON=python
```

## Environment setup

Copy the template and adjust values for your machine:

```bash
cp .env.example .env
```

Important variables:

| Variable | Purpose |
| --- | --- |
| `ENVIRONMENT` | `development`, `test`, or `production` |
| `DEBUG` | Enables verbose SQL/runtime logging; keep `false` in production |
| `SECRET_KEY` | Signs JWTs and derives stored token digests |
| `DATABASE_URL` | Async SQLAlchemy URL, e.g. `postgresql+asyncpg://postgres:postgres@localhost:5432/sangram_ai` |
| `ALLOWED_ORIGINS` | JSON list of allowed frontend origins |
| `COOKIE_SECURE` | Must be `true` in production (HTTPS only) |
| `OPENAI_API_KEY` | Optional OpenAI provider key |
| `ANTHROPIC_API_KEY` | Optional Anthropic provider key |
| `GOOGLE_API_KEY` | Optional Gemini/Google AI Studio provider key |
| `GROQ_API_KEY` | Optional Groq provider key |
| `MISTRAL_API_KEY` | Optional Mistral provider key |
| `XAI_API_KEY` | Optional xAI provider key |

Provider keys are optional. Without a key, that provider is reported as
unavailable and its models cannot be used for live battles. Gemini uses
`GOOGLE_API_KEY`.

`.env` is ignored by Git. Never commit real secrets. `.env.example` must contain
placeholders only.

## Database

PostgreSQL is defined in `docker-compose.yml` as the `postgres` service:

```bash
docker compose up -d postgres
docker compose ps
```

Wait until the container reports `healthy`, then run:

```bash
alembic upgrade head
```

Useful commands:

```bash
alembic current
alembic revision --autogenerate -m "describe change"
alembic downgrade -1
```

### Demo user

```bash
python -m app.db.seed
```

The seeder is idempotent and refuses to run when `ENVIRONMENT=production`.
It creates a normal password-backed account, not an auth bypass.

```text
Email:    demo@sangram.ai
Password: SangramDemo123!
```

Log in through `/api/auth/login`, the frontend, or Swagger UI.

## Health and security

- `GET /health` — liveness alias
- `GET /health/live` — liveness
- `GET /health/ready` — bounded PostgreSQL connectivity check

Responses include baseline security headers (`X-Content-Type-Options`,
`X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, and CSP). HSTS is
added only when `ENVIRONMENT=production`.

Example:

```bash
curl -i http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/health/ready
```

## Testing and quality checks

```bash
# Backend
make test
make lint
make typecheck

# Or directly
pytest -q
ruff check .
python -m compileall -q app tests
```

The test suite uses an in-memory SQLite database and does not require
PostgreSQL. The readiness probe tests mock database connectivity.

### Frontend checks

The React app is in `../frontend`:

```bash
cd ../frontend
npm install
npm run lint
npm run build
```

The frontend currently has `lint` and `build` scripts only. There are no
`test` or `typecheck` npm scripts configured in this repository.

## Project layout

```text
backend/
├── alembic/                 # Database migrations
├── app/
│   ├── api/                 # FastAPI routers and dependencies
│   ├── core/                # Config, errors, logging, middleware
│   ├── db/                  # SQLAlchemy engine, session, seed
│   ├── interfaces/          # Service protocols / ownership boundaries
│   ├── proposals/           # Domain entities
│   ├── schemas/             # Pydantic request/response models
│   └── services/            # Auth, battles, gateway, saved answers, sharing
├── docs/                    # Architecture, API, setup, deployment notes
├── tests/                   # pytest suite
├── docker-compose.yml       # Local PostgreSQL
├── Makefile                 # Developer commands
├── alembic.ini
├── pyproject.toml           # Project metadata, pytest and ruff config
└── requirements.txt
```

## Troubleshooting

### Docker daemon is not running

Start Docker Desktop, then verify:

```bash
docker info
```

### Port already in use

```bash
lsof -nP -iTCP:5432 -sTCP:LISTEN
lsof -nP -iTCP:8000 -sTCP:LISTEN
```

Stop the conflicting process or change the port in `.env`/`docker-compose.yml`.

### Database connection refused

```bash
docker compose ps
docker compose logs postgres
```

Wait for the `healthy` status and confirm `DATABASE_URL` points at
`localhost:5432` with the same user/password/database as the compose service.

### Migration fails

```bash
alembic current
alembic history
```

Make sure PostgreSQL is healthy and `.env` contains the correct
`DATABASE_URL` before running `alembic upgrade head`.

### `ModuleNotFoundError`

Activate the virtual environment and reinstall dependencies:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### `ruff: command not found`

Install the development dependencies:

```bash
pip install -r requirements.txt
```

### Seed refuses to run

This is expected when `ENVIRONMENT=production`. The demo seeder is
development-only.
