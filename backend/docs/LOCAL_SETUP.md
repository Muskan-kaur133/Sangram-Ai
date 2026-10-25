# SANGRAM AI — Local Development Setup Guide

This guide walks you through setting up and running the Sangram AI backend locally on **Windows (PowerShell)** and **macOS / Linux (Bash)**.

---

## Prerequisites

- **Python 3.11+** (Verify with `python --version` or `python3 --version`)
- **Git**
- **Docker & Docker Compose** (Optional, recommended for PostgreSQL)

---

## 1. Local Setup on Windows (PowerShell)

### Step 1: Open PowerShell and Navigate to the Backend Directory
```powershell
# From the repository root:
cd Sangram-Ai-main/backend
```

### Step 2: Create and Activate a Virtual Environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

*(If script execution is disabled, enable it for current user: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`)*

### Step 3: Install Backend Dependencies
```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Configure Local Environment Variables
```powershell
Copy-Item .env.example .env
```
*(The default `.env` is pre-configured to run with zero external credentials.)*

### Step 5: Start Local PostgreSQL (via Docker Compose)
```powershell
docker compose up -d postgres
```

### Step 6: Apply Database Migrations
```powershell
alembic upgrade head
```

### Step 7: Run Tests
```powershell
pytest -v
ruff check .
python -m compileall -q app tests
```

### Step 8: Launch the FastAPI Development Server
```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)
- **Interactive API Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Liveness Probe**: [http://localhost:8000/health/live](http://localhost:8000/health/live)
- **Readiness Probe**: [http://localhost:8000/health/ready](http://localhost:8000/health/ready)

---

## 2. Local Setup on macOS / Linux (Bash)

### Step 1: Open Terminal and Navigate to Backend
```bash
cd Sangram-Ai-main/backend
```

### Step 2: Create and Activate Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Configure Environment
```bash
cp .env.example .env
```

### Step 5: Start PostgreSQL Container
```bash
docker compose up -d postgres
```

### Step 6: Apply Database Migrations
```bash
alembic upgrade head
```

### Step 7: Run Tests and Checks
```bash
pytest -v
ruff check .
python -m compileall -q app tests
```

### Step 8: Start Server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 3. Makefile Shortcuts

From `backend/`, the same workflow is available through `make`:

```bash
make help           # list all targets
make venv           # create .venv with Python 3.11+
make install        # install requirements
make db-up          # docker compose up -d postgres
make db-migrate     # alembic upgrade head
make db-seed        # create the development demo user
make dev            # uvicorn with reload on 127.0.0.1:8000
make test           # pytest -q
make lint           # ruff check .
make format         # ruff format .
make typecheck      # byte-compile app and tests
```

`make` defaults to `.venv/bin/python`. Override it if needed:

```bash
make test PYTHON=python
```

### Development demo user

The seed command creates a real password-backed account for local testing. It
does **not** bypass authentication; log in through the normal auth endpoints or
the frontend with:

- **Email:** `demo@sangram.ai`
- **Password:** `SangramDemo123!`

The seeder refuses to run when `ENVIRONMENT=production`.

---

## 4. Database Migration Commands (Alembic)

Developer 2 owns domain migrations. The scaffold is pre-configured:

```bash
# Generate a new migration from proposed entity models:
alembic revision --autogenerate -m "create_initial_domain_tables"

# Apply pending migrations to the database:
alembic upgrade head

# Rollback the last migration:
alembic downgrade -1
```

---

## 5. Connecting the Frontend

To point the React frontend at your local backend:
1. Navigate to `frontend/`.
2. Create or edit `frontend/.env`:
   ```bash
   VITE_API_BASE_URL=http://localhost:8000
   ```
3. Start the Vite development server:
   ```bash
   npm run dev
   ```
   *(Frontend runs on `http://localhost:3000` with CORS pre-configured).*
