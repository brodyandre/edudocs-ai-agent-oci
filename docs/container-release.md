# Release De Containers

Este guia descreve a publicacao manual das imagens da API e da web no GitHub Container Registry.

## 1. Objetivo

Publicar imagens Docker profissionais, publicas, multi-arquitetura e rastreaveis para o futuro deploy na VM `VM.Standard.E4.Flex`.

## 2. Imagens

- API: `ghcr.io/brodyandre/edudocs-ai-api`
- Web: `ghcr.io/brodyandre/edudocs-ai-web`

O Nginx continua usando `nginxinc/nginx-unprivileged:1.27.4-alpine`; nao ha imagem Nginx customizada.

## 3. Plataformas

Cada imagem deve publicar um manifest list com:

- `linux/amd64`
- `linux/arm64`

AMD64 e obrigatoria para a futura instancia E4 Flex, e ARM64 permanece publicada para portabilidade.

## 4. Tags

O workflow publica sempre:

- `sha-${GITHUB_SHA}`

Opcionalmente publica:

- `main`

Nao ha `latest`. O alias `main` nao deve ser usado como referencia de implantacao.

## 5. Digests

Producao usa referencias imutaveis:

```text
ghcr.io/brodyandre/edudocs-ai-api@sha256:<digest>
ghcr.io/brodyandre/edudocs-ai-web@sha256:<digest>
```

O digest correto e o digest do manifest multiarch, nao o digest de uma arquitetura individual.

## 6. Manifest Multiarch

Valide com:

```bash
make images-inspect API_IMAGE_REF=<api-por-digest> WEB_IMAGE_REF=<web-por-digest>
```

Esse alvo usa `docker buildx imagetools inspect`, nao faz login e exige as duas arquiteturas.

## 7. Workflow Manual

O workflow `.github/workflows/publish-images.yml` e acionado apenas por `workflow_dispatch`:

```bash
gh workflow run publish-images.yml --ref main -f publish_main_alias=true
```

Antes de publicar, ele valida branch `main`, repositório, SHA em `origin/main` e workspace limpo.

## 8. Permissoes

Somente o workflow de publicacao possui:

```yaml
permissions:
  contents: read
  packages: write
```

Os workflows de CI e PR continuam somente leitura.

## 9. GITHUB_TOKEN

O login no GHCR usa a action oficial `docker/login-action` com `secrets.GITHUB_TOKEN`. Nao use PAT, secret customizado, senha, credencial OCI ou token em arquivo.

## 10. Visibilidade Publica

As imagens precisam ficar publicas para que a VM faça pull sem `docker login`. Se o pull anonimo falhar apos o push, altere manualmente a visibilidade do pacote no GitHub para Public e confirme que o pacote esta vinculado ao repositorio.

## 11. Pull Anonimo

O workflow usa um `DOCKER_CONFIG` temporario e vazio para validar:

```bash
docker buildx imagetools inspect ghcr.io/brodyandre/edudocs-ai-api@sha256:<digest>
docker buildx imagetools inspect ghcr.io/brodyandre/edudocs-ai-web@sha256:<digest>
```

Nao use login nesse config.

## 12. Labels OCI

As imagens incluem labels `org.opencontainers.image.*` para titulo, descricao, source, revision, created, version e licenca MIT.

## 13. Cache

Buildx usa cache `type=gha` separado por componente:

- `publish-api`
- `publish-web`

Isso evita colisao entre camadas da API e da web.

## 14. Smoke Pos-publicacao

Depois do pull anonimo, o workflow sobe `docker-compose.prod.yml` usando as referencias por digest e executa `scripts/smoke_test.py`.

## 15. Artefato De Release

O workflow envia o artefato `edudocs-container-release` com:

- `container-release-manifest.json`
- `container-release-summary.md`

O manifesto nao e commitado.

## 16. Uso No Compose

`docker-compose.prod.yml` exige:

```bash
API_IMAGE_REF=ghcr.io/brodyandre/edudocs-ai-api@sha256:<digest>
WEB_IMAGE_REF=ghcr.io/brodyandre/edudocs-ai-web@sha256:<digest>
docker compose -f docker-compose.prod.yml up -d
```

Sem essas variaveis, o Compose de producao falha.

## 17. FakeProvider No Primeiro Deploy

O primeiro deploy publico pode usar `EDUDOCS_LLM_PROVIDER=fake` e `EDUDOCS_EMBEDDING_PROVIDER=fake` para validar infraestrutura, containers, Load Balancer, health checks, interface e integracao.

## 18. Groq Futuro

Groq real deve ser ativado depois por mecanismo seguro, sem gravar `GROQ_API_KEY` no Terraform, cloud-init, Compose versionado ou state.

## 19. Seguranca

Imagens publicas nao podem conter `.env`, chaves, tfvars reais, state, planos, `.git`, `.venv`, caches do host, arquivos `~/.oci` ou tokens.

## 20. Troubleshooting

- Workflow falha antes do login: corrija preflight local.
- Push funciona, pull anonimo falha: altere manualmente a visibilidade do pacote para Public.
- Smoke falha: consulte logs do job e valide `API_IMAGE_REF` e `WEB_IMAGE_REF`.
- ARM64 ausente: corrija Buildx/QEMU antes de qualquer deploy OCI.

## 21. Rollback Por Digest

Rollback deve trocar `API_IMAGE_REF` e `WEB_IMAGE_REF` para digests anteriores aprovados. Nao use `main` como rollback de producao.

## 22. Limitacoes

A publicacao GHCR nao cria recurso OCI, nao configura DNS, nao ativa HTTPS e nao prova disponibilidade do Load Balancer real. Esses passos dependem do primeiro `terraform plan`, revisao e `apply` futuros.
