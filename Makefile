.PHONY: setup quality corpus index lint test evaluate web-build compose-check build up down restart ps logs smoke docker-ci project-audit readme-evidence pre-terraform ci clean

PYTHON ?= python3
VENV_PYTHON ?= .venv/bin/python
COMPOSE ?= docker compose
SMOKE_BASE_URL ?= http://localhost:8080
COMPOSE_CONFIG_JSON ?= /tmp/edudocs-compose-config.json
EVALUATION_JSON ?= /tmp/edudocs-evaluation.json
EVALUATION_MARKDOWN ?= /tmp/edudocs-evaluation.md

setup:
	$(PYTHON) -m venv .venv
	$(VENV_PYTHON) -m pip install -e "apps/api[dev]"
	npm --prefix apps/web ci

quality:
	$(PYTHON) scripts/check_utf8.py
	$(PYTHON) scripts/check_repository_hygiene.py
	$(MAKE) compose-check

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
	cd apps/api && ../../$(VENV_PYTHON) -m app.evaluation.cli run --strict --output-json $(EVALUATION_JSON) --output-markdown $(EVALUATION_MARKDOWN)

web-build:
	npm --prefix apps/web run typecheck
	npm --prefix apps/web run build

compose-check:
	$(COMPOSE) config
	$(COMPOSE) config --format json > $(COMPOSE_CONFIG_JSON)
	$(PYTHON) scripts/validate_compose_policy.py $(COMPOSE_CONFIG_JSON) infrastructure/nginx/nginx.conf

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

docker-ci: build up smoke down

project-audit:
	$(PYTHON) scripts/audit_project_readiness.py
	$(PYTHON) scripts/check_utf8.py

readme-evidence:
	$(PYTHON) scripts/sync_readme_evidence.py
	$(PYTHON) scripts/check_readme.py

pre-terraform:
	$(PYTHON) scripts/check_repository_hygiene.py
	$(PYTHON) scripts/validate_corpus.py
	$(VENV_PYTHON) -m ruff check apps/api
	$(VENV_PYTHON) -m pytest apps/api/tests
	cd apps/api && ../../$(VENV_PYTHON) -m app.evaluation.cli run --strict --output-json /tmp/edudocs-pre-terraform-evaluation.json --output-markdown /tmp/edudocs-pre-terraform-evaluation.md
	npm --prefix apps/web run lint
	npm --prefix apps/web run typecheck
	npm --prefix apps/web run test
	npm --prefix apps/web run build
	$(COMPOSE) config
	$(COMPOSE) down
	$(COMPOSE) up -d --build
	SMOKE_BASE_URL=$(SMOKE_BASE_URL) $(PYTHON) scripts/smoke_test.py
	AUDIT_RUN_SMOKE=1 $(PYTHON) scripts/audit_project_readiness.py
	$(COMPOSE) down
	$(PYTHON) scripts/sync_readme_evidence.py
	$(PYTHON) scripts/check_readme.py
	$(PYTHON) scripts/check_utf8.py
	git diff --check

ci: quality corpus lint test evaluate web-build

clean:
	$(PYTHON) -c "import pathlib, shutil; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('__pycache__') if p.is_dir()]; [shutil.rmtree(p, ignore_errors=True) for p in map(pathlib.Path, ['.pytest_cache', '.ruff_cache', 'apps/web/.next'])]"
