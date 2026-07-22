# Interface Web EduDocs AI

## Objetivo

A interface web oferece uma experiência local para consultar o agente EduDocs AI, acompanhar a disponibilidade da API, visualizar os documentos públicos do corpus e ler respostas fundamentadas com fontes.

## Stack

- Next.js com App Router.
- React e TypeScript.
- Tailwind CSS.
- ESLint.
- Vitest e React Testing Library.
- Cliente HTTP com `fetch` nativo e timeout via `AbortController`.

## Requisitos

- Node.js 20.20.2.
- API FastAPI do projeto executando localmente.
- Índice local do corpus já criado e validado.

## Node.js

O `package.json` declara `engines.node` como `20.20.2` para manter o ambiente alinhado ao projeto.

## Instalação

```bash
npm --prefix apps/web ci
```

## Variáveis

Crie um arquivo `.env.local` em `apps/web` se precisar mudar a URL da API.

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

O valor padrão do cliente também é `http://localhost:8000`.

No modo integrado com Nginx, `NEXT_PUBLIC_API_BASE_URL` deve ficar vazio. Assim o navegador chama `/health`, `/ready`, `/api/documents` e `/api/chat` no mesmo host de `http://localhost:8080`, sem depender de `localhost:8000` no bundle.

## Desenvolvimento

```bash
npm --prefix apps/web run dev
```

A aplicação fica disponível em `http://localhost:3000` quando a porta estiver livre.

## Lint

```bash
npm --prefix apps/web run lint
```

## Typecheck

```bash
npm --prefix apps/web run typecheck
```

## Testes

```bash
npm --prefix apps/web run test
```

Os testes cobrem o cliente HTTP, estados de disponibilidade, envio de perguntas, respostas com e sem evidência, erros HTTP, timeout, rede, cópia de resposta e requisitos de acessibilidade básicos.

## Build

```bash
npm --prefix apps/web run build
```

O `next.config.mjs` usa `output: "standalone"` para gerar a saída própria de container. O Dockerfile da web executa o build com `NEXT_PUBLIC_API_BASE_URL` vazio e roda como usuário não-root na porta interna `3000`.

## Integração com a API

A interface consome os contratos públicos já existentes:

- `GET /health` para disponibilidade da API.
- `GET /ready` para prontidão do índice local.
- `GET /api/documents` para documentos públicos do corpus.
- `POST /api/chat` para enviar perguntas ao agente.

As respostas de chat são exibidas com texto, status de fundamentação, latência, referência técnica discreta e fontes quando a API retorna evidências.

## Tratamento de Erros

O cliente converte falhas de rede, timeout, JSON inválido e respostas HTTP em mensagens públicas. Os códigos `400`, `422`, `429`, `503` e `504` recebem textos específicos para orientar o usuário sem expor detalhes internos.

## Acessibilidade

A tela usa landmarks semânticos, labels explícitos, navegação por teclado, link de salto, estados desabilitados, foco visível e regiões `aria-live` para atualizações assíncronas.

## Limitações

Não há autenticação, upload, histórico persistente, banco de dados ou chamada direta a documentos externos. O corpus é fictício e foi criado apenas para demonstração educacional.

## Estrutura

```text
apps/web/
  app/
  components/
  lib/
  public/
  tests/
  types/
```
