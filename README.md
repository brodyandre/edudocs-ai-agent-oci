# EduDocs AI

EduDocs AI é um projeto em desenvolvimento para um agente RAG voltado a consultas sobre documentos educacionais fictícios. O repositório prepara a base técnica do Challenge antes da implementação funcional da API, da interface, do agente e da infraestrutura.

## Problema

Instituições educacionais lidam com normas, comunicados, guias e materiais de apoio espalhados em PDFs. O projeto propõe uma arquitetura para consultar esse acervo com respostas baseadas em evidências, citando documento e página quando houver suporte no corpus.

## Escopo do MVP

O MVP planejado contempla ingestão de PDFs fictícios, extração e normalização de texto, criação de chunks, geração de embeddings locais, índice persistido, busca híbrida, orquestração do fluxo RAG e resposta por provedor de LLM isolado por interface.

Ficam fora do MVP autenticação, OCR, upload público, Kubernetes, banco relacional e funcionalidades administrativas.

## Arquitetura resumida

O fluxo planejado conecta uma interface Next.js a uma API FastAPI. A API aciona um grafo LangGraph, que consulta um recuperador híbrido sobre índice local e metadados. Quando houver evidências suficientes, a resposta será gerada por um provedor de LLM inicialmente baseado em Groq, sem acoplamento direto ao restante da aplicação.

## Tecnologias planejadas

- Next.js, React, TypeScript e Tailwind CSS para a interface.
- Python e FastAPI para a API.
- LangGraph para orquestração do agente.
- LangChain apenas em integrações nas quais agregue valor real.
- PyMuPDF para extração de PDFs.
- Embeddings multilíngues locais configuráveis.
- Busca semântica persistida e busca lexical com TF-IDF ou BM25.
- Docker Compose para execução local.
- Terraform, Nginx e OCI Compute ARM64 para deploy planejado.

## Status atual

Em desenvolvimento. Esta versão contém a estrutura inicial e a documentação técnica do projeto. A API, a interface, o agente RAG, a ingestão funcional e o deploy ainda não foram implementados.

## Roadmap resumido

1. Documentar arquitetura, pipeline RAG, segurança e plano de entregas.
2. Criar corpus fictício e critérios de avaliação.
3. Implementar ingestão local de PDFs.
4. Implementar recuperador híbrido e provedor falso determinístico para testes.
5. Implementar API FastAPI e interface Next.js.
6. Preparar Docker Compose, Terraform e deploy em OCI.
7. Registrar evidências finais, exemplos e captura de tela.

## Documentos técnicos

- [Arquitetura](docs/architecture.md)
- [Pipeline RAG](docs/rag-pipeline.md)
- [Segurança](docs/security.md)
- [Plano de entregas](docs/delivery-plan.md)
