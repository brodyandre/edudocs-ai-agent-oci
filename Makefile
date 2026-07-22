.PHONY: setup corpus index lint test evaluate build up down restart ps logs smoke ci clean

PYTHON ?= python3
VENV_PYTHON ?= .venv/bin/python
COMPOSE ?= docker compose
SMOKE_BASE_URL ?= http://localhost:8080

setup:
	$(PYTHON) -m venv .venv
	$(VENV_PYTHON) -m pip install -e "apps/api[dev]"
	npm --prefix apps/web ci

corpus:
	$(PYTHON) scripts/validate_corpus.py

index:
	cd apps/api && ../../$(VENV_PYTHON) -m app.ingestion.cli build

lint:
	$(VENV_PYTHON) -m ruff check apps/api
	npm --prefix apps/web run lint

test:
	$(VENV_PYTHON) -m pytest apps/api/tests
	npm --prefix apps/web run test -- --reporter=dot --silent

evaluate:
	cd apps/api && ../../$(VENV_PYTHON) -m app.evaluation.cli run --strict

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

restart: down up

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs --tail=200

smoke:
	SMOKE_BASE_URL=$(SMOKE_BASE_URL) $(PYTHON) scripts/smoke_test.py

ci: corpus lint test evaluate build up smoke down

clean:
	$(PYTHON) -c "import pathlib, shutil; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('__pycache__') if p.is_dir()]; [shutil.rmtree(p, ignore_errors=True) for p in map(pathlib.Path, ['.pytest_cache', '.ruff_cache', 'apps/web/.next'])]"
