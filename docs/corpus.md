# Corpus EduDocs Academy

## Objetivo do corpus

O corpus EduDocs Academy fornece documentos educacionais fictícios para testar o futuro agente RAG do projeto EduDocs AI. Ele foi criado para permitir perguntas diretas, perguntas cruzadas entre documentos, recusas quando não houver evidência e testes de resistência a prompt injection documental.

## Origem fictícia

Todo o conteúdo é original e fictício. A EduDocs Academy não representa empresa, escola, pessoa, endereço, telefone ou política real. Os e-mails usam o domínio reservado `example` para deixar claro que os canais são simulados.

## Documentos

O corpus inicial contém cinco documentos:

- `regulamento-do-estudante`: regras gerais de matrícula, acesso, conduta, avaliação, participação e recursos.
- `politica-de-cancelamento-e-reembolso`: prazos e condições fictícias para cancelamento e restituição.
- `guia-de-certificados`: requisitos, emissão, correção, validação e segunda via de certificados.
- `faq-de-cursos-e-matriculas`: respostas rápidas sobre matrícula, acesso, aulas, suporte, certificados, cancelamento e bolsas.
- `politica-de-privacidade`: tratamento fictício de dados, retenção, direitos, cookies e menores.

## Estrutura

Os fontes Markdown ficam em `corpus/sources/`. Os PDFs pesquisáveis gerados ficam em `corpus/documents/`. O manifesto fica em `corpus/manifest.json`, e o dataset inicial de avaliação fica em `corpus/evaluation/questions.json`.

## Geração dos PDFs

Os PDFs são gerados por `scripts/generate_corpus_pdfs.py` a partir dos Markdown. O script usa ReportLab, registra uma fonte Unicode já existente no sistema, preferencialmente DejaVu Sans, e não baixa nem versiona fontes.

Cada PDF recebe cabeçalho, título, versão, data de vigência, rodapé e numeração de página. O script evita inserir nome de usuário, diretório local ou metadados da máquina.

## Validação

O script `scripts/validate_corpus.py` verifica a existência dos Markdown e PDFs, validade dos PDFs, texto extraível por página, títulos, hashes SHA-256, manifesto, IDs únicos, caminhos, documentos habilitados e perguntas de avaliação.

## Manifesto

O manifesto lista cada documento com identificador, título, versão, data de vigência, caminhos relativos, categoria, idioma, hash SHA-256 do PDF final e flag `enabled`.

## Dataset de avaliação

O dataset contém perguntas diretas, perguntas que cruzam documentos, perguntas sem resposta no corpus e tentativas de prompt injection. As páginas esperadas são preenchidas somente após gerar e extrair texto dos PDFs.

## Como regenerar

Ative o ambiente virtual e execute:

```bash
python3 scripts/generate_corpus_pdfs.py
python3 scripts/validate_corpus.py
```

Após regenerar PDFs, revise se os hashes do manifesto foram atualizados e se as páginas esperadas do dataset continuam válidas.

## Como adicionar documento

Para adicionar um documento, crie o Markdown em `corpus/sources/`, inclua a entrada correspondente em `DOCUMENTS` no gerador, regenere PDFs e manifesto, atualize perguntas de avaliação e execute o validador.

## Limitações

O corpus não contém OCR, imagens complexas, tabelas extensas, anexos externos, documentos reais, dados pessoais reais ou regras juridicamente válidas. Ele foi desenhado para validação técnica controlada do MVP.

## Licenciamento do conteúdo

O conteúdo textual fictício criado neste repositório segue a licença MIT do projeto. As fontes tipográficas usadas na geração são localizadas no sistema e não são copiadas para o repositório.
