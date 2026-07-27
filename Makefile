.PHONY: setup quality corpus index lint test evaluate web-build compose-check terraform-fmt terraform-init terraform-validate terraform-policy terraform-check container-release-check container-release-manifest-check images-inspect images-smoke build up down restart ps logs smoke docker-ci project-audit readme-evidence pre-terraform ci clean

PYTHON ?= python3
VENV_PYTHON ?= .venv/bin/python
COMPOSE ?= docker compose
SMOKE_BASE_URL ?= http://localhost:8080
COMPOSE_CONFIG_JSON ?= /tmp/edudocs-compose-config.json
EVALUATION_JSON ?= /tmp/edudocs-evaluation.json
EVALUATION_MARKDOWN ?= /tmp/edudocs-evaluation.md
CONTAINER_RELEASE_MANIFEST ?=

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

terraform-fmt:
	terraform -chdir=infrastructure/terraform fmt -recursive -check

terraform-init:
	terraform -chdir=infrastructure/terraform init -backend=false

terraform-validate:
	terraform -chdir=infrastructure/terraform validate

terraform-policy:
	$(PYTHON) scripts/check_terraform_policy.py

terraform-check: terraform-fmt terraform-init terraform-validate terraform-policy

container-release-check:
	$(PYTHON) scripts/check_container_publish_policy.py

container-release-manifest-check:
	test -n "$(CONTAINER_RELEASE_MANIFEST)"
	$(PYTHON) scripts/check_container_release_manifest.py "$(CONTAINER_RELEASE_MANIFEST)"

images-inspect:
	test -n "$(API_IMAGE_REF)"
	test -n "$(WEB_IMAGE_REF)"
	bash -c 'set -euo pipefail; cfg=$$(mktemp -d); trap '\''rm -rf "$$cfg"'\'' EXIT; DOCKER_CONFIG="$$cfg" docker buildx imagetools inspect "$(API_IMAGE_REF)" | grep -E "linux/amd64|linux/arm64"; DOCKER_CONFIG="$$cfg" docker buildx imagetools inspect "$(WEB_IMAGE_REF)" | grep -E "linux/amd64|linux/arm64"; DOCKER_CONFIG="$$cfg" docker pull --platform linux/amd64 "$(API_IMAGE_REF)"; DOCKER_CONFIG="$$cfg" docker pull --platform linux/amd64 "$(WEB_IMAGE_REF)"; docker image inspect "$(API_IMAGE_REF)" --format '\''{{ index .Config.Labels "org.opencontainers.image.source" }} {{ index .Config.Labels "org.opencontainers.image.revision" }}'\''; docker image inspect "$(WEB_IMAGE_REF)" --format '\''{{ index .Config.Labels "org.opencontainers.image.source" }} {{ index .Config.Labels "org.opencontainers.image.revision" }}'\'''

images-smoke:
	test -n "$(API_IMAGE_REF)"
	test -n "$(WEB_IMAGE_REF)"
	bash -c 'set -euo pipefail; cfg=$$(mktemp -d); trap '\''DOCKER_CONFIG="$$cfg" API_IMAGE_REF="$(API_IMAGE_REF)" WEB_IMAGE_REF="$(WEB_IMAGE_REF)" $(COMPOSE) -f docker-compose.prod.yml down -v; rm -rf "$$cfg"'\'' EXIT; DOCKER_CONFIG="$$cfg" API_IMAGE_REF="$(API_IMAGE_REF)" WEB_IMAGE_REF="$(WEB_IMAGE_REF)" EDUDOCS_LLM_PROVIDER=fake EDUDOCS_EMBEDDING_PROVIDER=fake NGINX_PORT=$${NGINX_PORT:-8080} $(COMPOSE) -f docker-compose.prod.yml up -d; SMOKE_BASE_URL=http://localhost:$${NGINX_PORT:-8080} $(PYTHON) scripts/smoke_test.py'

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

ci: quality corpus lint test evaluate web-build terraform-check container-release-check

clean:
	$(PYTHON) -c "import pathlib, shutil; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('__pycache__') if p.is_dir()]; [shutil.rmtree(p, ignore_errors=True) for p in map(pathlib.Path, ['.pytest_cache', '.ruff_cache', 'apps/web/.next'])]"
