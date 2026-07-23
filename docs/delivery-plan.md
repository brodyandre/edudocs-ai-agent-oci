# Plano de Entregas

## Entregáveis oficiais do Challenge

| Entregável | Status atual | Critério de aceite |
| --- | --- | --- |
| Repositório público | Concluído | Repositório acessível no GitHub como público. |
| Histórico de commits | Em andamento | Commits pequenos, descritivos e em PT-BR. |
| Estrutura organizada | Concluído | Diretórios para apps, corpus, docs, infraestrutura e scripts. |
| README | Em andamento | README com descrição, escopo, status e links técnicos. |
| Descrição geral | Em andamento | Problema, público e objetivo documentados. |
| Arquitetura | Em andamento | Documento técnico com componentes, fluxos e diagrama Mermaid. |
| Tecnologias | Em andamento | Stack planejada documentada sem afirmar implementação pronta. |
| Execução local | Pendente | Docker Compose validado localmente. |
| Exemplos de perguntas | Pendente | Perguntas alinhadas ao corpus fictício. |
| Exemplos de respostas | Pendente | Respostas com citações e recusas quando necessário. |
| Agente funcional | Pendente | Fluxo RAG executável com provedor real e falso. |
| Leitura e processamento de PDF | Pendente | Ingestão local validada com metadados e índice. |
| Terraform OCI | Concluído | Código validável sem credenciais reais, sem `plan` e sem `apply`. |
| Load Balancer OCI | Concluído no código | Flexible Load Balancer 10 Mbps, backend set, backend privado e listener HTTP declarados. |
| Deploy OCI | Pendente | Infraestrutura aplicada e aplicação disponível. |
| Link público | Pendente | URL pública real após deploy. |
| Captura de tela | Pendente | Evidência visual salva em `docs/evidence/`. |

## Checklist por entrega

- Repositório: criar repo público, configurar `main`, manter workspace limpo.
- Documentação: arquitetura, pipeline RAG, segurança, plano de entregas e README coerente.
- Corpus: criar PDFs fictícios, registrar versões e preparar perguntas de avaliação.
- Ingestão: extrair texto, normalizar, criar chunks, gerar embeddings e persistir índice.
- Recuperação: implementar busca semântica, busca lexical, fusão e deduplicação.
- Agente: orquestrar com LangGraph, avaliar suficiência e gerar resposta com citações.
- Testes: usar provedor falso determinístico e evitar consumo externo nos testes.
- Interface: criar fluxo simples para perguntar e visualizar resposta com fontes.
- Execução local: validar Docker Compose.
- Deploy: revisar primeiro plan real, provisionar OCI com Terraform, publicar imagens ARM64, iniciar Nginx na VM e validar via Load Balancer.
- Evidências: registrar comandos, exemplos, link público e captura de tela final.

## Definição de pronto

Uma entrega é considerada pronta quando possui implementação ou documentação correspondente, validação executada, ausência de segredos, arquivos em UTF-8 sem BOM, links relativos válidos e nenhum texto afirmando funcionalidades não concluídas.

## Dependências

- Corpus fictício antes dos exemplos de perguntas e respostas.
- Ingestão antes da recuperação.
- Recuperação antes do agente funcional.
- Provedor falso antes de testes confiáveis.
- API antes da interface integrada.
- Docker Compose antes do deploy.
- Terraform, Load Balancer e Nginx antes do link público; credenciais, compartment, home region, capacidade A1, elegibilidade do LB 10 Mbps, CIDR administrativo e state antes do primeiro plan real.

## Riscos

- Escopo crescer além do MVP.
- PDFs fictícios não cobrirem perguntas suficientes.
- Extração de texto gerar chunks pouco úteis.
- Dependências terem problemas em ARM64.
- Provedor externo introduzir instabilidade.
- Deploy consumir tempo maior que o previsto.

## Sequência recomendada

1. Finalizar documentação técnica e critérios de aceite.
2. Criar corpus fictício e matriz de perguntas.
3. Implementar ingestão de PDFs.
4. Implementar índice local e metadados.
5. Implementar recuperação híbrida.
6. Implementar grafo RAG com provedor falso.
7. Integrar Groq por interface de provedor.
8. Criar API FastAPI.
9. Criar interface Next.js.
10. Validar execução local com Docker Compose.
11. Validar Terraform OCI sem credenciais reais.
12. Confirmar credenciais OCI e revisar o primeiro plan real.
13. Provisionar OCI, configurar Nginx e registrar evidências finais.

## Critérios de aceite

- O repositório público está atualizado na branch `main`.
- A documentação descreve arquitetura, pipeline, segurança e plano de entrega.
- A aplicação local executa por comandos documentados quando implementada.
- O agente responde com base no corpus fictício e cita documento e página.
- O agente recusa respostas sem evidência suficiente.
- Testes automatizados usam provedor falso determinístico.
- Nenhum segredo é versionado.
- O deploy público na OCI só é declarado após validação real.
- A captura de tela final representa a aplicação em execução.
