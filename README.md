<div align="center">

# EduDocs AI

Agente de IA para consultar documentos educacionais fictícios com respostas rastreáveis, fontes e recusas seguras.

[![Quality](https://github.com/brodyandre/edudocs-ai-agent-oci/actions/workflows/quality.yml/badge.svg)](https://github.com/brodyandre/edudocs-ai-agent-oci/actions/workflows/quality.yml)
[![API CI](https://github.com/brodyandre/edudocs-ai-agent-oci/actions/workflows/api-ci.yml/badge.svg)](https://github.com/brodyandre/edudocs-ai-agent-oci/actions/workflows/api-ci.yml)
[![Web CI](https://github.com/brodyandre/edudocs-ai-agent-oci/actions/workflows/web-ci.yml/badge.svg)](https://github.com/brodyandre/edudocs-ai-agent-oci/actions/workflows/web-ci.yml)
[![Containers CI](https://github.com/brodyandre/edudocs-ai-agent-oci/actions/workflows/containers-ci.yml/badge.svg)](https://github.com/brodyandre/edudocs-ai-agent-oci/actions/workflows/containers-ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[Demonstração](#demonstracao-da-experiencia) ·
[Arquitetura](#arquitetura) ·
[Execução local](#execucao-local) ·
[Avaliação](#qualidade-e-avaliacao) ·
[GitHub Actions](#github-actions)

</div>

---

## Proposta de valor

Documentos extensos costumam esconder regras importantes em páginas diferentes. O EduDocs AI permite perguntar em linguagem natural, receber uma resposta curta e conferir de onde veio cada informação. Quando o corpus não sustenta a pergunta, o agente deve recusar em vez de completar com conhecimento externo.

O projeto usa uma aplicação educacional fictícia, a EduDocs Academy, para demonstrar um fluxo RAG completo sem expor dados reais.

## Índice

- [Demonstração da experiência](#demonstracao-da-experiencia)
- [Problema resolvido](#problema-resolvido)
- [Como funciona](#como-funciona)
- [Como o agente responde](#como-o-agente-responde)
- [Quando a informação não existe](#quando-a-informacao-nao-existe)
- [Documentos disponíveis](#documentos-disponiveis)
- [Experiência para pessoas não técnicas](#experiencia-para-pessoas-nao-tecnicas)
- [Arquitetura](#arquitetura)
- [Tecnologias](#tecnologias)
- [Qualidade e avaliação](#qualidade-e-avaliacao)
- [GitHub Actions](#github-actions)
- [Docker e execução integrada](#docker-e-execucao-integrada)
- [Execução local](#execucao-local)
- [Perguntas de exemplo](#perguntas-de-exemplo)
- [Segurança](#seguranca)
- [Estrutura do repositório](#estrutura-do-repositorio)
- [Estado do projeto](#estado-do-projeto)
- [Infraestrutura OCI](#infraestrutura-oci)
- [Entregáveis do Challenge](#entregaveis-do-challenge)
- [Limitações](#limitacoes)
- [Roadmap](#roadmap)
- [Licença](#licenca)
- [Autor](#autor)

## Demonstração da experiência

A primeira tela foi pensada para pessoas que não querem entender termos técnicos antes de usar o sistema. O hero mantém a promessa central do produto: **Pergunte aos documentos. Entenda a resposta.** O ícone documental reforça a ideia de pergunta, análise e fonte, sem competir com a ação principal.

<!-- EVIDENCE:HOME:START -->
![Hero da interface de consulta documental.](docs/evidence/home-hero.png)

_Hero da interface de consulta documental._
<!-- EVIDENCE:HOME:END -->

[Voltar ao índice](#índice)

## Problema resolvido

O cenário simulado é comum em ambientes educacionais: regras de certificado, reembolso, privacidade, matrícula e aprovação ficam distribuídas em PDFs. A consulta manual é lenta, exige familiaridade com o vocabulário institucional e pode levar a respostas sem rastreabilidade.

O EduDocs AI resolve esse recorte ao buscar trechos relevantes, responder apenas com base no corpus e mostrar documento, página e trecho usado. O público esperado inclui estudantes, equipes acadêmicas e avaliadores que precisam validar rapidamente se a resposta tem origem verificável.

[Voltar ao índice](#índice)

## Como funciona

```mermaid
flowchart LR
    PDF[PDFs fictícios] --> TXT[Extração com PyMuPDF]
    TXT --> CH[Chunks com metadados]
    CH --> EMB[Embeddings locais]
    EMB --> IDX[(Índice local)]
    CH --> META[(Metadados)]
    USER[Usuário] --> WEB[Next.js]
    WEB --> API[FastAPI]
    API --> GRAPH[LangGraph]
    GRAPH --> RET[Busca híbrida]
    RET --> IDX
    RET --> META
    RET --> GRAPH
    GRAPH --> LLM[Groq ou FakeProvider]
    LLM --> GRAPH
    GRAPH --> API
    API --> WEB
```

O fluxo começa com PDFs fictícios do corpus. A API extrai texto, cria chunks, gera embeddings locais e salva índice e metadados. Durante uma pergunta, o grafo LangGraph consulta o recuperador híbrido, avalia se há evidência suficiente e só então solicita a resposta ao provedor configurado.

<details>
<summary>Detalhes técnicos do fluxo RAG</summary>

- A ingestão usa `PyMuPDF` para leitura página a página.
- Os metadados preservam documento, versão, página, seção, ordem do chunk e hash de conteúdo.
- A recuperação combina sinal semântico com sinal lexical.
- O runtime do agente é o grafo LangGraph.
- O `FakeProvider` mantém testes determinísticos sem rede nem segredos.
- O provedor Groq está isolado por contrato para uso futuro com credencial externa.

</details>

[Voltar ao índice](#índice)

## Como o agente responde

Quando encontra base suficiente, o agente retorna uma resposta objetiva, indica que a informação vem do corpus e apresenta fontes. A interface destaca a seção **De onde veio a resposta**, com documento, página e trecho associado.

Esse desenho evita que a resposta pareça uma opinião solta. A pessoa consegue conferir a origem sem abrir todos os PDFs manualmente.

<!-- EVIDENCE:ANSWER:START -->
> **Captura pendente:** `docs/evidence/answer-with-sources.png`.
> Consulte o guia em `docs/screenshot-guide.md`.
<!-- EVIDENCE:ANSWER:END -->

[Voltar ao índice](#índice)

## Quando a informação não existe

O agente não deve improvisar telefone real, endereço físico, diretoria, catálogo atual ou qualquer dado que não esteja nos documentos. Para perguntas sem suporte, a resposta esperada é uma recusa clara e útil.

O mesmo princípio vale para prompt injection. Instruções maliciosas dentro da pergunta não devem sobrepor as regras de citação, recusa e uso exclusivo do corpus.

<!-- EVIDENCE:UNSUPPORTED:START -->
![Recusa segura quando o corpus nao sustenta a resposta.](docs/evidence/unsupported-question.png)

_Recusa segura quando o corpus nao sustenta a resposta._
<!-- EVIDENCE:UNSUPPORTED:END -->

[Voltar ao índice](#índice)

## Documentos disponíveis

O corpus atual tem cinco documentos fictícios, todos habilitados no manifesto `corpus/manifest.json`.

| Documento | Categoria | Versão | Finalidade |
| --- | --- | --- | --- |
| Regulamento do Estudante | regulamento | 1.0 | Regras de matrícula, acesso, aprovação, conduta e certificados. |
| Política de Cancelamento e Reembolso | cancelamento | 1.0 | Prazos, condições de reembolso e encerramento de acesso. |
| Guia de Certificados | certificados | 1.0 | Requisitos, emissão, segunda via e correção de certificados. |
| FAQ de Cursos e Matrículas | faq | 1.0 | Dúvidas frequentes sobre acesso, matrícula, suporte e bolsas. |
| Política de Privacidade | privacidade | 1.0 | Dados tratados, retenção, direitos e canais de privacidade. |

<!-- EVIDENCE:DOCUMENTS:START -->
![Painel de documentos disponiveis no corpus ficticio.](docs/evidence/documents-panel.png)

_Painel de documentos disponiveis no corpus ficticio._
<!-- EVIDENCE:DOCUMENTS:END -->

[Voltar ao índice](#índice)

## Experiência para pessoas não técnicas

A interface usa linguagem direta, exemplos de perguntas e estados compreensíveis. A pessoa não precisa saber o que é RAG, embedding ou LangGraph para consultar os documentos.

O MVP não exige cadastro, não persiste histórico entre sessões e organiza as fontes em uma área com nome humano: **De onde veio a resposta**. O layout é responsivo, preserva contraste e mantém o ícone decorativo fora da navegação por teclado.

[Voltar ao índice](#índice)

## Arquitetura

```mermaid
flowchart LR
    U[Usuário] --> N[Nginx]
    N --> W[Next.js]
    W --> A[FastAPI]
    A --> G[LangGraph]
    G --> R[Recuperador híbrido]
    R --> C[(Índice e corpus)]
    G --> P[Groq ou FakeProvider]
    P --> G
    G --> A
    A --> W
    W --> N
    N --> U

    subgraph Local
      N
      W
      A
      G
      R
      C
    end

    subgraph Futuro OCI
      OCI[Compute ARM64 planejado]
      TF[Terraform planejado]
    end
```

No runtime local, Docker Compose sobe API, web e Nginx em rede interna. A única porta pública padrão é `8080`, servida pelo Nginx. A infraestrutura OCI ainda é planejamento: não há Terraform criado nem deploy publicado nesta etapa.

[Voltar ao índice](#índice)

## Tecnologias

| Responsabilidade | Tecnologias auditadas |
| --- | --- |
| Interface | Next.js `^15.3.5`, React `^19.1.0`, TypeScript `^5.8.3`, Tailwind CSS `^3.4.17` |
| API | Python `>=3.10,<3.13`, FastAPI `>=0.115,<0.116` |
| IA | LangGraph `==0.2.76`, Groq SDK `>=0.13,<1`, FakeProvider determinístico |
| Documentos | PyMuPDF `==1.28.0`, NumPy `>=1.26,<2.0`, scikit-learn `>=1.4,<1.7` |
| Testes | pytest `>=8.0,<9`, Ruff `>=0.8,<0.14`, Vitest `^3.2.4` |
| Containers | Docker Compose, Nginx unprivileged, imagens locais para API e web |
| CI/CD | Quality, API CI, Web CI e Containers CI no GitHub Actions |
| Infraestrutura futura | Terraform e OCI Compute ARM64, ainda não iniciados nesta entrega |

[Voltar ao índice](#índice)

## Qualidade e avaliação

A avaliação RAG usa `corpus/evaluation/questions.json` com 28 perguntas: 15 diretas, 5 multi-documento, 5 sem suporte e 3 de prompt injection. O resultado versionado mais recente está em `corpus/evaluation/results/latest.json`.

| Métrica | Valor real | Leitura prática |
| --- | ---: | --- |
| `retrieval_hit_rate` | 1.0 | O recuperador encontrou algum documento esperado nos casos avaliáveis. |
| `document_recall_at_k` | 0.975 | Quase todos os documentos esperados aparecem no conjunto recuperado. |
| `exact_document_set_rate` | 0.95 | A maioria dos casos trouxe exatamente o conjunto documental esperado. |
| `page_hit_rate` | 0.85 | A página esperada aparece com boa frequência, mas ainda não é perfeita. |
| `page_recall_at_k` | 0.7583333333333333 | Há espaço para melhorar precisão de páginas. |
| `mean_reciprocal_rank` | 0.875 | O documento correto tende a aparecer bem posicionado. |
| `answerable_accuracy` | 1.0 | O agente separou perguntas respondíveis e não respondíveis no dataset. |
| `unsupported_rejection_rate` | 1.0 | Perguntas sem base foram recusadas. |
| `false_answer_rate` | 0.0 | Não houve resposta falsa registrada na avaliação. |
| `supported_answer_rate` | 1.0 | Perguntas respondíveis receberam resposta suportada. |
| `citation_validity_rate` | 1.0 | As citações geradas foram válidas nos critérios atuais. |
| `prompt_injection_resistance_rate` | 1.0 | Os casos de prompt injection foram resistidos. |
| `fact_coverage_rate` | 0.0 | Limitação atual: a cobertura literal dos fatos esperados ainda é baixa. |
| `complete_document_citation_rate` | 0.2 | Limitação atual: citações completas em casos multi-documento ainda precisam evoluir. |

Essas métricas não são maquiadas. Os pontos baixos indicam o que deve melhorar antes de uma apresentação final mais ambiciosa.

[Voltar ao índice](#índice)

## GitHub Actions

O repositório usa quatro workflows reais:

- **Quality**: higiene do repositório, UTF-8 e validações de política.
- **API CI**: Ruff, pytest e avaliação RAG.
- **Web CI**: lint, typecheck, testes, build e auditoria npm.
- **Containers CI**: Compose, Nginx, smoke integrado e builds amd64/arm64.

<!-- EVIDENCE:ACTIONS:START -->
![Workflows do GitHub Actions apos a validacao do projeto.](docs/evidence/github-actions.png)

_Workflows do GitHub Actions apos a validacao do projeto._
<!-- EVIDENCE:ACTIONS:END -->

[Voltar ao índice](#índice)

## Docker e execução integrada

A stack local integrada contém `api`, `web` e `nginx`. API e web ficam expostas apenas na rede interna do Compose; o Nginx publica `8080:8080`. O índice usa o volume `edudocs-index`.

Os containers usam controles como `read_only`, `tmpfs`, `cap_drop: ALL` e `no-new-privileges`. O pipeline também valida compatibilidade de build para `linux/amd64` e `linux/arm64`.

<!-- EVIDENCE:DOCKER:START -->
![Validacao integrada da stack Docker local.](docs/evidence/docker-smoke.png)

_Validacao integrada da stack Docker local._
<!-- EVIDENCE:DOCKER:END -->

[Voltar ao índice](#índice)

## Execução local

### A. Docker Compose recomendado

```bash
make setup
docker compose up -d --build
python3 scripts/smoke_test.py
```

A aplicação integrada fica em:

```text
http://localhost:8080
```

Para encerrar:

```bash
docker compose down
```

### B. API e Web separadas

```bash
make setup
cd apps/api
../../.venv/bin/python -m app.ingestion.cli build
../../.venv/bin/uvicorn app.main:app --reload --port 8000
```

Em outro terminal:

```bash
npm --prefix apps/web ci
npm --prefix apps/web run dev
```

Por padrão, a web em desenvolvimento usa `http://localhost:3000`.

[Voltar ao índice](#índice)

## Perguntas de exemplo

- Em quanto tempo o certificado digital deve ficar disponível depois da validação dos requisitos?
- Qual é o prazo de arrependimento para cancelamento com reembolso integral?
- Qual aproveitamento mínimo é exigido para aprovação em cursos avaliativos?
- Qual é o prazo para correção simples de dados após a emissão do certificado?
- Por quanto tempo registros de certificados podem ser mantidos?
- Qual é o telefone real de atendimento da EduDocs Academy?

[Voltar ao índice](#índice)

## Segurança

Segredos devem ficar fora do repositório. O frontend não recebe chave de LLM, e o provedor real deve ser configurado por variável de ambiente fora do Git. Os testes usam provider falso determinístico.

O projeto valida prompt injection no dataset, exige fontes para respostas suportadas, recusa perguntas sem base e mantém containers com privilégios reduzidos. As portas internas da API e da web não são publicadas diretamente no Compose local.

Limitações do MVP: sem autenticação, sem rate limit persistente, sem histórico permanente, sem upload de documentos e sem validação real de credenciais OCI.

[Voltar ao índice](#índice)

## Estrutura do repositório

```text
.
├── apps/
│   ├── api/        # FastAPI, ingestão, recuperação, LangGraph e avaliação
│   └── web/        # Next.js, componentes, estilos e testes de interface
├── corpus/         # Manifesto, PDFs fictícios, fontes e dataset de avaliação
├── docs/           # Documentação técnica, auditorias e guia de screenshots
├── infrastructure/ # Nginx local
├── scripts/        # Validadores, auditoria, smoke test e sincronização do README
├── docker-compose.yml
└── Makefile
```

[Voltar ao índice](#índice)

## Estado do projeto

Concluído:

- Corpus fictício com cinco PDFs.
- Ingestão, chunks, índice e metadados.
- Recuperador híbrido.
- Runtime LangGraph.
- API FastAPI.
- Interface Next.js com foco em pessoas não técnicas.
- Ícone `DocumentAnswerIcon` no hero.
- Avaliação RAG determinística.
- Docker Compose com Nginx.
- CI para qualidade, API, web e containers.
- Builds de containers para amd64 e ARM64 no CI.

Próximo:

- Criar Terraform.
- Provisionar OCI.
- Validar Groq real fora do ambiente de teste.
- Configurar domínio e HTTPS.
- Produzir evidências reais do deploy.

[Voltar ao índice](#índice)

## Infraestrutura OCI

A OCI é o próximo passo planejado. Esta entrega prepara a documentação e a auditoria pré-Terraform, mas não cria arquivos Terraform, não executa `plan`, `apply` ou `destroy`, e não afirma deploy ativo.

Antes do Prompt 09, ainda falta validar credenciais fora do Git, compartment, home region, capacidade A1, CIDR administrativo e estratégia de state.

<!-- EVIDENCE:OCI_APP:START -->
> **Captura reservada para etapa futura:** `docs/evidence/oci-application.png`.
> Consulte o guia em `docs/screenshot-guide.md`.
<!-- EVIDENCE:OCI_APP:END -->

<!-- EVIDENCE:OCI_INSTANCE:START -->
> **Captura reservada para etapa futura:** `docs/evidence/oci-instance-running.png`.
> Consulte o guia em `docs/screenshot-guide.md`.
<!-- EVIDENCE:OCI_INSTANCE:END -->

[Voltar ao índice](#índice)

## Entregáveis do Challenge

| Entregável | Estado |
| --- | --- |
| Repositório público | Concluído |
| Commits incrementais | Concluído |
| README profissional | Concluído nesta entrega |
| Agente RAG | Concluído para o MVP local |
| Corpus PDF | Concluído com documentos fictícios |
| Interface gráfica | Concluída para uso local |
| Deploy OCI | Pendente |
| Screenshots locais | Espaços preparados; imagens ainda pendentes |
| Evidência OCI | Reservada para etapa futura |

[Voltar ao índice](#índice)

## Limitações

- O corpus é fictício e não representa uma instituição real.
- Não há OCR para PDFs escaneados.
- Não há upload de documentos pelo usuário.
- Não há autenticação.
- O histórico não é persistido entre sessões.
- O provedor Groq real ainda não foi validado nesta etapa.
- A OCI ainda não foi implantada.
- As métricas `fact_coverage_rate`, `complete_document_citation_rate` e `page_recall_at_k` indicam pontos reais de melhoria.

[Voltar ao índice](#índice)

## Roadmap

1. Fechar documentação e auditoria pré-Terraform.
2. Criar infraestrutura Terraform para OCI sem versionar segredos.
3. Publicar a aplicação em Compute ARM64.
4. Configurar domínio, HTTPS e variáveis seguras.
5. Produzir capturas reais de aplicação e infraestrutura.
6. Reavaliar recuperação, cobertura factual e citações multi-documento.

[Voltar ao índice](#índice)

## Licença

Distribuído sob licença MIT. Consulte [LICENSE](LICENSE).

## Autor

Luiz Andre, conforme licença do repositório.
