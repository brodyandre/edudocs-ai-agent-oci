# Auditoria pre-Terraform do EduDocs AI

Gerado em `2026-07-23T17:40:27Z`.

## 1. Resumo executivo

Concluido: o projeto possui API, interface web, corpus ficticio, avaliacao RAG, Docker Compose e GitHub Actions registrados em fatos automatizados.

Pendente: a infraestrutura OCI ainda nao foi criada e o Prompt 09 continua pendente.

## 2. Baseline Git

- Branch: `main`
- HEAD: `38e8b7f9cbb215add938eb260dfa47dd42238dba`
- Ultimo commit: `feat(web): adiciona ícone de consulta documental ao hero`
- Data do ultimo commit: `2026-07-23T13:35:44-03:00`
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
- Testes API nesta auditoria: 100.

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
- Quality: completed / success (54f95a7)
- Web CI: completed / success (54f95a7)

## 9. Evidencias visuais

- `docs/evidence/home-hero.png`: pendente
- `docs/evidence/answer-with-sources.png`: pendente
- `docs/evidence/unsupported-question.png`: pendente
- `docs/evidence/documents-panel.png`: pendente
- `docs/evidence/github-actions.png`: pendente
- `docs/evidence/docker-smoke.png`: pendente
- `docs/evidence/oci-application.png`: reservado para etapa futura
- `docs/evidence/oci-instance-running.png`: reservado para etapa futura

## 10. Pendencias antes do Terraform

- Futuro: definir credenciais OCI fora do repositorio.
- Futuro: validar compartment, home region e disponibilidade A1.
- Futuro: definir CIDR administrativo.
- Futuro: aplicar estrategia de state.
- Nao aplicavel nesta entrega: `terraform plan`, `apply` ou `destroy`.

## 11. Checklist de aprovacao para executar o Prompt 09

- [ ] Credenciais OCI configuradas fora do Git.
- [ ] Compartment validado.
- [ ] Regiao e capacidade A1 verificadas.
- [ ] CIDR administrativo definido.
- [ ] Estrategia de state definida.
- [ ] Evidencias locais atualizadas quando disponiveis.

## 12. Comando para reproduzir a auditoria

```bash
python3 scripts/audit_project_readiness.py
```
