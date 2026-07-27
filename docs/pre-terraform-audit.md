# Auditoria Terraform do EduDocs AI

Gerado em `2026-07-27T15:12:37Z`.

## 1. Resumo executivo

Concluido: o projeto possui API, interface web, corpus ficticio, avaliacao RAG, Docker Compose, Terraform OCI validavel e GitHub Actions registrados em fatos automatizados.

Pendente: credenciais OCI, primeiro `terraform plan` real, qualquer `apply`, deploy da aplicacao, dominio, HTTPS e evidencias OCI reais.

## 2. Baseline Git

- Branch: `main`
- HEAD: `03f0a59c5b9d25f4e3672bb129e1981623b7f504`
- Ultimo commit: `feat(infra): adiciona load balancer Always Free à arquitetura OCI`
- Data do ultimo commit: `2026-07-23T17:14:29-03:00`
- Sincronismo `main...origin/main`: `0	0`
- Workspace limpo: `True`
- Repositorio: `https://github.com/brodyandre/edudocs-ai-agent-oci`
- Visibilidade: `PUBLIC`
- Branch padrao: `main`

## 3. Estado funcional

- Web: lint `True`, typecheck `True`, build `True`.
- API: Ruff `True`, pytest `True`.
- Corpus: 5 documentos habilitados, 23 paginas e 41 chunks.

## 4. Testes

- Testes Web nesta auditoria: 55.
- Testes API nesta auditoria: 152.

## 5. Avaliacao RAG

- Perguntas: 28.
- Categorias: {'direct': 15, 'multi_document': 5, 'prompt_injection': 3, 'unsupported': 5}.

- `retrieval_hit_rate`: 1.0
- `document_recall_at_k`: 0.975
- `exact_document_set_rate`: 0.95
- `page_hit_rate`: 0.85
- `page_recall_at_k`: 0.7583333333333333
- `mean_reciprocal_rank`: 0.875
- `answerable_accuracy`: 1.0
- `unsupported_rejection_rate`: 1.0
- `false_answer_rate`: 0.0
- `supported_answer_rate`: 1.0
- `citation_validity_rate`: 1.0
- `prompt_injection_resistance_rate`: 1.0
- `fact_coverage_rate`: 0.0
- `complete_document_citation_rate`: 0.2

## 6. Interface

Concluido: interface Next.js com linguagem voltada a pessoas nao tecnicas, hero com `DocumentAnswerIcon`, respostas com fontes e secao "De onde veio a resposta".

## 7. Containers

- Servicos: api, nginx, web
- Portas publicas: {'nginx': ['8080:8080']}
- Portas internas: {'api': ['8000'], 'web': ['3000']}
- Volume de indice: True
- Smoke test: True

## 8. CI

- API CI: completed / success (54f95a7)
- Containers CI: completed / success (54f95a7)
- Quality: completed / success (bfe8cb8)
- Web CI: completed / success (54f95a7)

## 9. Release De Containers

- Workflow de publicacao presente: `True`.
- Workflow somente manual: `True`.
- Politica de publicacao: `True`.
- Imagem API alvo: `ghcr.io/brodyandre/edudocs-ai-api`.
- Imagem Web alvo: `ghcr.io/brodyandre/edudocs-ai-web`.
- Plataformas: `['linux/amd64', 'linux/arm64']`.
- Compose exige referencias imutaveis: `True`.
- Manifesto de release: script `True`, validador `True`.
- Publicacao API registrada no repositorio: `False`.
- Publicacao Web registrada no repositorio: `False`.
- Pull anonimo comprovado no repositorio: `False`.
- Smoke de imagens publicadas registrado no repositorio: `False`.

## 10. Evidencias visuais

- `docs/evidence/home-hero.png`: presente
- `docs/evidence/answer-with-sources.png`: presente
- `docs/evidence/unsupported-question.png`: presente
- `docs/evidence/documents-panel.png`: presente
- `docs/evidence/github-actions.png`: presente
- `docs/evidence/docker-smoke.png`: presente
- `docs/evidence/oci-application.png`: reservado para etapa futura
- `docs/evidence/oci-instance-running.png`: reservado para etapa futura

## 11. Estado Terraform e pendencias OCI

- Terraform criado: `True`.
- Provider OCI: `~> 8.23.0`.
- Modulos: `{'network': True, 'compute': True, 'load_balancer': True, 'object_storage': True}`.
- Load Balancer: `{'declared': True, 'shape': 'flexible', 'minimum_bandwidth_mbps': 10, 'maximum_bandwidth_mbps': 10, 'listener_port': 80, 'backend_port': 8080, 'health_path': '/health', 'backend_uses_private_ip': True, 'separate_nsgs': True, 'endpoint_available': False}`.
- Cloud-init criado: `True`.
- Terraform fmt: `True`.
- Terraform validate: `True`.
- Politica Terraform: `True`.
- Futuro: definir credenciais OCI fora do repositorio.
- Futuro: validar compartment, home region, disponibilidade A1 e elegibilidade do Load Balancer 10/10 Mbps.
- Futuro: definir CIDR administrativo real.
- Futuro: aplicar estrategia de state antes do primeiro plan real.
- Nao aplicavel nesta entrega: `terraform plan`, `apply` ou `destroy`.

## 12. Checklist de aprovacao antes do primeiro plan real

- [ ] Credenciais OCI configuradas fora do Git.
- [ ] Compartment validado.
- [ ] Regiao, capacidade A1 e elegibilidade do Load Balancer 10/10 Mbps verificadas.
- [ ] CIDR administrativo definido.
- [ ] Estrategia de state definida.
- [ ] Evidencias locais atualizadas quando disponiveis.

## 13. Comando para reproduzir a auditoria

```bash
python3 scripts/audit_project_readiness.py
```
