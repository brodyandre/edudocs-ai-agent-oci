# EduDocs AI

EduDocs AI é um projeto em desenvolvimento para um agente RAG voltado a consultas sobre documentos educacionais fictícios. O repositório prepara a base técnica do Challenge e já contém API, agente, ingestão local, avaliação determinística e interface web para consulta do corpus.

## Problema

Instituições educacionais lidam com normas, comunicados, guias e materiais de apoio espalhados em PDFs. O projeto propõe uma arquitetura para consultar esse acervo com respostas baseadas em evidências, citando documento e página quando houver suporte no corpus.

## Escopo do MVP

O MVP contempla ingestão de PDFs fictícios, extração e normalização de texto, criação de chunks, geração de embeddings locais, índice persistido, busca híbrida, orquestração do fluxo RAG, resposta por provedor de LLM isolado por interface e uma interface Next.js para consulta assistida.

Ficam fora do MVP autenticação, OCR, upload público, Kubernetes, banco relacional e funcionalidades administrativas.

## Arquitetura resumida

O fluxo conecta uma interface Next.js a uma API FastAPI. A API aciona um grafo LangGraph, que consulta um recuperador híbrido sobre índice local e metadados. Quando houver evidências suficientes, a resposta é gerada por um provedor de LLM isolado por interface; em desenvolvimento e testes, o provider falso determinístico evita dependência de rede ou segredos.

## Tecnologias

- Next.js, React, TypeScript e Tailwind CSS para a interface.
- Python e FastAPI para a API.
- LangGraph para orquestração do agente.
- LangChain apenas em integrações nas quais agregue valor real.
- PyMuPDF para extração de PDFs.
- Embeddings multilíngues locais configuráveis.
- Busca semântica persistida e busca lexical com TF-IDF ou BM25.
- Docker Compose e Nginx para execução local integrada.
- Terraform e OCI Compute ARM64 para deploy planejado.

## Status atual

Em desenvolvimento. Esta versão contém corpus fictício, ingestão, índice local, API FastAPI, agente RAG, avaliação determinística e interface web Next.js. Deploy em OCI e funcionalidades administrativas seguem fora do escopo atual.

## Interface web

A interface fica em `apps/web` e consome `GET /health`, `GET /ready`, `GET /api/documents` e `POST /api/chat`.

```bash
npm --prefix apps/web ci
npm --prefix apps/web run dev
```

Consulte [apps/web/README.md](apps/web/README.md) para instalação, variáveis, validações, integração e limitações.

## Execução integrada com Docker

O ambiente Docker local sobe API, web e Nginx em uma rede interna. A única porta publicada por padrão é `8080`, servida pelo Nginx.

```bash
make build
make up
make smoke
make down
```

A aplicação integrada fica em `http://localhost:8080`. Consulte [docs/local-development.md](docs/local-development.md) para detalhes de ambiente virtual, índice, Compose local, Compose de produção e smoke test.

## Roadmap resumido

1. Documentar arquitetura, pipeline RAG, segurança e plano de entregas.
2. Criar corpus fictício e critérios de avaliação.
3. Implementar ingestão local de PDFs.
4. Implementar recuperador híbrido e provedor falso determinístico para testes.
5. Implementar API FastAPI e interface Next.js.
6. Preparar Terraform e deploy em OCI.
7. Registrar evidências finais, exemplos e captura de tela.

## Documentos técnicos

- [Arquitetura](docs/architecture.md)
- [Pipeline RAG](docs/rag-pipeline.md)
- [Segurança](docs/security.md)
- [Plano de entregas](docs/delivery-plan.md)
