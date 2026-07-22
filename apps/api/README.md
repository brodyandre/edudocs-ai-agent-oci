# API EduDocs AI

Esta API é a base funcional para ingestão e indexação do corpus fictício da EduDocs Academy. A entrega atual implementa o pipeline PDF -> páginas -> texto normalizado -> chunks -> embeddings -> índice persistido, além dos endpoints iniciais de saúde, prontidão e listagem de documentos.

Ainda não há geração de respostas por LLM, LangGraph ou agente conversacional.

## Ambiente virtual

A partir da raiz do repositório:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e "apps/api[dev]"
```

Para habilitar o provedor real de embeddings posteriormente:

```bash
pip install -e "apps/api[embeddings]"
```

O extra `embeddings` instala `sentence-transformers`, mas nenhum modelo é baixado durante importação de módulos ou testes.

## Configuração

As variáveis principais estão em `.env.example` na raiz e em `apps/api/.env.example`:

- `EDUDOCS_MANIFEST_PATH`
- `EDUDOCS_DOCUMENTS_DIR`
- `EDUDOCS_INDEX_DIR`
- `EDUDOCS_EMBEDDING_PROVIDER`
- `EDUDOCS_EMBEDDING_MODEL`
- `EDUDOCS_FAKE_EMBEDDING_DIMENSION`
- `EDUDOCS_CHUNK_SIZE`
- `EDUDOCS_CHUNK_OVERLAP`
- `EDUDOCS_BATCH_SIZE`
- `EDUDOCS_DEFAULT_TOP_K`
- `EDUDOCS_TESTING`

O provedor padrão é `fake`, determinístico e local. Para usar `sentence-transformers`, configure `EDUDOCS_EMBEDDING_PROVIDER=sentence-transformers` em ambiente preparado para baixar ou carregar o modelo configurado.

## Construção do índice

Execute a partir de `apps/api`:

```bash
python -m app.ingestion.cli build
python -m app.ingestion.cli validate
python -m app.ingestion.cli inspect
```

Quando estiver usando a `.venv` criada na raiz sem ativá-la:

```bash
../../.venv/bin/python -m app.ingestion.cli build
```

O índice ativo é publicado em `corpus/index/active`. A publicação é atômica: o índice novo é construído em diretório temporário e substitui o ativo apenas após validação.

## Decisão sobre versionamento do índice

Os embeddings, artefatos lexicais e metadados de índice não são versionados. Eles podem ser reconstruídos de forma determinística a partir do corpus versionado, do manifesto e das configurações registradas.

## Execução da API

Com as dependências instaladas:

```bash
uvicorn app.main:app --reload
```

Endpoints iniciais:

- `GET /health`: informa que o processo está ativo.
- `GET /ready`: retorna sucesso apenas quando o índice local está válido.
- `GET /api/documents`: lista documentos habilitados do manifesto, sem expor caminhos internos.

## Testes e lint

Execute a partir da raiz do repositório:

```bash
ruff check apps/api
pytest apps/api/tests
```

Os testes usam corpus temporário, PDFs controlados e `FakeEmbeddingProvider`. Eles não chamam serviços externos e não baixam modelos.

## Limitações

- Não há geração de resposta com LLM.
- Não há LangGraph nesta etapa.
- A busca é inicial e combina similaridade semântica local com TF-IDF.
- O provedor real de `sentence-transformers` é preguiçoso e depende de instalação opcional.
- O índice gerado localmente não deve ser commitado.
