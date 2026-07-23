# Guia de capturas do EduDocs AI

Este guia orienta a producao das capturas reais usadas no README. Nenhuma imagem deve ser criada como simulacao: cada arquivo precisa representar a aplicacao ou a evidencia tecnica no estado em que foi capturada.

## 1. Objetivo

Registrar evidencias visuais contextualizadas do EduDocs AI para demonstrar interface, respostas com fontes, recusas seguras, documentos disponiveis, CI, Docker e, futuramente, deploy OCI.

## 2. Padrao visual

- Use a interface em tema claro conforme o design atual.
- Evite cortar textos importantes.
- Nao exponha tokens, variaveis sensiveis, caminhos privados ou dados pessoais.
- Prefira capturas com conteudo legivel em vez de telas muito amplas.

## 3. Resolucao recomendada

- Desktop: 1440 x 1000 ou proporcao proxima.
- Mobile opcional: 390 x 844 para validacao responsiva.
- GitHub Actions e terminal: largura suficiente para mostrar status sem revelar caminhos locais desnecessarios.

## 4. Zoom

Use zoom do navegador em 100%. Se o texto ficar pequeno em terminal, aumente a fonte do terminal antes da captura em vez de ampliar a imagem depois.

## 5. Como iniciar a aplicacao

Caminho recomendado:

```bash
docker compose up -d --build
```

Acesse:

```text
http://localhost:8080
```

Ao terminar:

```bash
docker compose down
```

## 6. Como validar antes de capturar

Execute:

```bash
python3 scripts/smoke_test.py
npm --prefix apps/web run test
```

Confirme que a pagina inicial carrega, que o painel de documentos aparece e que as respostas exibem a secao "De onde veio a resposta" quando houver suporte no corpus.

## 7. Como capturar cada tela

### Home e hero

Arquivo:

```text
docs/evidence/home-hero.png
```

Capture o primeiro bloco da aplicacao com o texto "Pergunte aos documentos. Entenda a resposta." e o icone documental visivel.

### Resposta com fontes

Arquivo:

```text
docs/evidence/answer-with-sources.png
```

Pergunta sugerida:

```text
Em quanto tempo o certificado digital deve ficar disponível depois da validação dos requisitos?
```

Capture a resposta e a secao "De onde veio a resposta".

### Pergunta sem suporte

Arquivo:

```text
docs/evidence/unsupported-question.png
```

Pergunta sugerida:

```text
Qual é o telefone real de atendimento da EduDocs Academy?
```

Capture a recusa segura sem apresentar a imagem como erro.

### Painel de documentos

Arquivo:

```text
docs/evidence/documents-panel.png
```

Capture a area que lista os cinco documentos do corpus e seus estados.

### GitHub Actions

Arquivo:

```text
docs/evidence/github-actions.png
```

Capture a pagina de Actions do repositorio mostrando os workflows Quality, API CI, Web CI e Containers CI.

### Docker smoke

Arquivo:

```text
docs/evidence/docker-smoke.png
```

Capture o terminal apos:

```bash
docker compose ps
python3 scripts/smoke_test.py
```

### Aplicacao na OCI

Arquivo:

```text
docs/evidence/oci-application.png
```

Produza somente apos deploy real em OCI. Nao use `localhost` nem imagem simulada.

### Instancia OCI em execucao

Arquivo:

```text
docs/evidence/oci-instance-running.png
```

Produza somente apos provisionamento real e acesso ao console ou CLI da OCI.

## 8. Nome exato de cada arquivo

- `docs/evidence/home-hero.png`
- `docs/evidence/answer-with-sources.png`
- `docs/evidence/unsupported-question.png`
- `docs/evidence/documents-panel.png`
- `docs/evidence/github-actions.png`
- `docs/evidence/docker-smoke.png`
- `docs/evidence/oci-application.png`
- `docs/evidence/oci-instance-running.png`

## 9. Onde cada imagem aparece no README

- `home-hero.png`: Demonstração da experiência.
- `answer-with-sources.png`: Como o agente responde.
- `unsupported-question.png`: Quando a informação não existe.
- `documents-panel.png`: Documentos disponíveis.
- `github-actions.png`: GitHub Actions.
- `docker-smoke.png`: Docker e execução integrada.
- `oci-application.png`: Infraestrutura OCI.
- `oci-instance-running.png`: Infraestrutura OCI.

## 10. Como copiar arquivos do Windows para o WSL2

Exemplo:

```bash
cp /mnt/c/Users/USER/Pictures/home-hero.png docs/evidence/home-hero.png
```

Depois valide:

```bash
file docs/evidence/home-hero.png
```

## 11. Como sincronizar o README

```bash
python3 scripts/sync_readme_evidence.py
```

O script atualiza apenas os blocos delimitados por marcadores `EVIDENCE`.

## 12. Como validar

```bash
python3 scripts/check_readme.py
python3 scripts/check_utf8.py
git diff --check
```

## 13. Como criar o commit

Adicione explicitamente os arquivos alterados. Nao use `git add .`.

```bash
git add README.md docs/evidence/home-hero.png
git commit -m "docs: adiciona evidencias visuais reais"
```

## 14. Cuidados com dados sensiveis

- Nao capture tokens, chaves, cookies, headers ou arquivos `.env`.
- Nao capture configuracoes privadas da OCI.
- Nao capture caminhos locais completos quando eles nao forem relevantes.
- Revise a imagem antes de versionar.

## 15. Capturas futuras de OCI

As capturas `oci-application.png` e `oci-instance-running.png` ficam reservadas para depois do deploy real. Enquanto nao existirem, o README deve mostrar pendencia contextual, sem link quebrado e sem sugerir que a OCI ja foi implantada.
