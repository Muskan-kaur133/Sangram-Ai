SHELL := /bin/sh

PYTHON ?= .venv/bin/python
PYTHON_BOOTSTRAP ?= python3.11

.DEFAULT_GOAL := help

.PHONY: help venv install dev test lint format typecheck \
	db-up db-down db-migrate db-seed

help:
	@echo "Sangram AI backend developer commands"
	@echo ""
	@echo "  make venv          Create .venv with Python 3.11+"
	@echo "  make install       Install requirements into .venv"
	@echo "  make dev           Run the FastAPI dev server on 127.0.0.1:8000"
	@echo "  make test          Run the pytest suite"
	@echo "  make lint          Run ruff checks"
	@echo "  make format        Format Python files with ruff"
	@echo "  make typecheck     Byte-compile app and tests (syntax check)"
	@echo "  make db-up         Start PostgreSQL via docker compose"
	@echo "  make db-down       Stop docker compose services"
	@echo "  make db-migrate    Apply Alembic migrations"
	@echo "  make db-seed       Create the development demo user"
	@echo ""
	@echo "Override the interpreter with PYTHON=/path/to/python if needed."

venv:
	$(PYTHON_BOOTSTRAP) -m venv .venv

install:
	$(PYTHON) -m pip install -r requirements.txt

dev:
	$(PYTHON) -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m ruff format .

typecheck:
	$(PYTHON) -m compileall -q app tests

db-up:
	docker compose up -d postgres

db-down:
	docker compose down

db-migrate:
	$(PYTHON) -m alembic upgrade head

db-seed:
	$(PYTHON) -m app.db.seed
