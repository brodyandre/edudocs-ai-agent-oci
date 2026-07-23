# CI/CD

## 1. Objetivo

A integração contínua valida automaticamente qualidade geral, corpus, API, avaliação RAG, web, containers e Terraform OCI. Esta etapa não publica imagens, não executa deploy, não acessa OCI e não chama Groq.

## 2. Workflows

- `Quality`: valida UTF-8, whitespace, higiene do repositório, JSON, links relativos do README, corpus, Docker Compose, Terraform e política OCI.
- `API CI`: valida dependências Python, corpus, índice fake, Ruff, Pytest e avaliação RAG estrita.
- `Web CI`: valida dependências Node, lint, typecheck, testes, build Next.js e política npm audit.
- `Containers CI`: valida Compose/Nginx, builds Docker `amd64`/`arm64` e smoke integrado.

## 3. Gatilhos

Todos os workflows rodam em `push` para `main`, `pull_request` para `main` e `workflow_dispatch`. Os workflows específicos usam filtros de caminhos para evitar execuções sem relação direta com API, web ou containers.

## 4. Jobs

Os jobs são separados por responsabilidade para deixar falhas fáceis de investigar. O smoke integrado sobe o Compose local, executa `scripts/smoke_test.py`, mostra logs apenas em falha e finaliza com `docker compose down -v`.

## 5. Cache

Python usa cache de pip baseado em `apps/api/pyproject.toml`. Node usa cache npm baseado em `apps/web/package-lock.json`. Docker Buildx usa cache GitHub Actions separado por componente e arquitetura.

## 6. Permissões

Todos os workflows usam `permissions: contents: read`. Não há `packages: write`, `id-token: write`, `deployments: write`, `pull-requests: write` ou `write-all`.

## 7. FakeProvider

O CI define `EDUDOCS_LLM_PROVIDER=fake` e `EDUDOCS_EMBEDDING_PROVIDER=fake`. Nenhuma etapa usa `GROQ_API_KEY`, secrets de produção ou chamadas externas de LLM.

## 8. Avaliação RAG

O workflow da API constrói e valida o índice determinístico antes da avaliação. A avaliação estrita grava JSON e Markdown em `$RUNNER_TEMP` para evitar alterações nos relatórios versionados.

## 9. Builds amd64

`Containers CI` valida imagens da API e da web para `linux/amd64` com Docker Buildx, sem push.

## 10. Builds ARM64

O mesmo workflow valida API e web para `linux/arm64` com QEMU e Buildx, usando cache por arquitetura, sem publicação.

## 11. Smoke test

O smoke valida a home, `/health`, `/ready`, `/api/documents` e chats de certificado, reembolso, transporte e prompt injection. Também bloqueia exposição de stack trace, segredo, caminho interno e prompt interno.

## 12. Política do npm audit

`Web CI` executa `npm audit --omit=dev --json` e `npm audit --json`. O estado esperado atual é 0 vulnerabilidades. O script mantém uma baseline restrita para achados moderados conhecidos, mas vulnerabilidades `high`, `critical` ou achados fora dessa baseline fazem o job falhar.

## 13. Segredos

`scripts/check_repository_hygiene.py` detecta arquivos proibidos, chaves privadas, tokens GitHub, valores reais de `GROQ_API_KEY` e OCIDs. A saída mostra caminho, tipo e orientação, sem imprimir o valor sensível.

## 14. Execução local

```bash
make ci
make docker-ci
```

`make ci` cobre as validações principais sem publicar, acessar OCI nem fazer deploy. `make docker-ci` executa build local, Compose e smoke integrado.

## 15. Como investigar falhas

Leia primeiro o job e a etapa com falha. Para containers, consulte os logs do smoke exibidos somente em falha. Para npm audit, compare o relatório com a baseline aceita. Para avaliação RAG, use os relatórios temporários gerados no runner.

## 16. Limitações

Os workflows não publicam artefatos grandes, não fazem upload do índice e não geram cobertura. A validação de links cobre links relativos do README e não depende de links externos.

Terraform no CI executa apenas `fmt`, `init -backend=false`, `validate`, `scripts/check_terraform_policy.py` e testes offline da política. A validação cobre o Flexible Load Balancer 10/10 Mbps, backend privado 8080, listener HTTP 80 e dois NSGs. Não há `plan`, `apply`, `destroy`, credenciais OCI ou permissões de escrita.

## 17. O que não é feito nesta etapa

- Publicação de imagens.
- Deploy.
- Acesso à OCI.
- Uso de Groq.
