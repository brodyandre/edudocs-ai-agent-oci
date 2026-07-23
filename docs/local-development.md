# Desenvolvimento local

Este guia cobre o fluxo local do EduDocs AI com ambiente virtual, execução direta e execução integrada via Docker Compose.

## Requisitos

- Python 3.10 a 3.12.
- Node.js 20.20.2.
- Docker com Compose v2 para a execução integrada.

## Ambiente virtual

Na raiz do repositório:

```bash
make setup
```

O alvo cria `.venv`, instala a API em modo editável com dependências de desenvolvimento e executa `npm ci` da web.

## Corpus e índice

O corpus versionado fica em `corpus/manifest.json`, `corpus/documents` e `corpus/sources`. O índice gerado fica em `corpus/index` e não deve ser commitado.

```bash
make corpus
make index
```

## Execução direta

Terminal da API:

```bash
cd apps/api
../../.venv/bin/python -m uvicorn app.main:app --reload
```

Terminal da web:

```bash
npm --prefix apps/web run dev
```

Neste modo, a web usa `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` por padrão e fica disponível em `http://localhost:3000`.

## Execução integrada com Docker

```bash
make build
make up
make smoke
make down
```

O Compose local sobe `api`, `web` e `nginx` na rede `edudocs`. Apenas o Nginx publica porta no host, em `http://localhost:8080`.

Serviços internos:

- `api`: FastAPI na porta interna `8000`, sem porta publicada.
- `web`: Next.js standalone na porta interna `3000`, sem porta publicada.
- `nginx`: proxy reverso na porta `8080`.

Volume persistente:

- `edudocs-index`: montado em `/app/corpus/index` no container da API.

## Nginx

O arquivo `infrastructure/nginx/nginx.conf` encaminha:

- `/health` e `/ready` para a API.
- `/api/` para a API.
- Demais rotas para a web.

O proxy preserva `Host`, `X-Real-IP`, `X-Forwarded-*` e `X-Request-ID`, aplica limite de corpo de `1m`, timeouts explícitos, gzip, headers básicos de segurança e logs em stdout/stderr.

## Compose de produção

O arquivo `docker-compose.prod.yml` não faz build local. Ele espera imagens já publicadas e uma tag imutável:

```bash
IMAGE_TAG=2026-07-22 API_IMAGE=registry.example/edudocs-api WEB_IMAGE=registry.example/edudocs-web docker compose -f docker-compose.prod.yml up -d
```

Use `NGINX_PORT` para alterar a porta externa do Nginx. Não coloque chaves em arquivos versionados; injete segredos somente no ambiente de execução.

## Smoke test

```bash
SMOKE_BASE_URL=http://localhost:8080 python3 scripts/smoke_test.py
```

O smoke test valida a home HTML, `/health`, `/ready`, `/api/documents` e quatro chamadas de chat: certificado, reembolso, transporte e prompt injection. Ele também verifica ausência de stack trace, segredo, caminhos locais e prompt interno nas respostas.

## Comandos úteis

```bash
make ci
make docker-ci
make lint
make test
make evaluate
make ps
make logs
make restart
make clean
```

`make ci` executa validações locais de qualidade, corpus, API, web, avaliação RAG com saída temporária e Docker Compose config. `make docker-ci` executa build local dos containers, sobe o Compose, roda o smoke e desliga o ambiente; ele não publica imagens nem executa deploy.
