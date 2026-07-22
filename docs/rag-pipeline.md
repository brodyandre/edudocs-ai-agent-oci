# Pipeline RAG

## 1. Conceito de RAG aplicado ao projeto

RAG combina recuperação de evidências com geração de texto. No EduDocs AI, a resposta planejada deve ser limitada ao conteúdo recuperado dos PDFs educacionais fictícios e acompanhada de citações por documento e página.

## 2. Leitura dos PDFs página a página

A ingestão planejada usa PyMuPDF para abrir cada PDF e extrair texto por página. A página é a menor unidade de referência para citação e auditoria.

## 3. Normalização de texto

O texto extraído deve passar por normalização de espaços, quebras de linha, hifenização simples, marcadores e caracteres invisíveis. A normalização não deve alterar o sentido do documento.

## 4. Detecção de seções

Quando o texto indicar títulos, numeração ou padrões consistentes, o pipeline deve associar cada trecho a uma seção. Se a seção não for detectada com segurança, o metadado deve receber valor neutro e não inventado.

## 5. Estratégia de chunking

Os chunks devem preservar coesão semântica, respeitando páginas e seções sempre que possível. O tamanho será configurável para equilibrar contexto suficiente e custo de geração.

## 6. Sobreposição entre chunks

A sobreposição reduz perda de contexto entre divisões. O valor deve ser pequeno e configurável, evitando duplicação excessiva no índice.

## 7. Metadados obrigatórios

Cada chunk deve guardar:

- documento;
- título;
- versão;
- página;
- seção;
- índice do chunk;
- hash.

## 8. Geração dos embeddings

Os embeddings são acessados por uma interface desacoplada. A implementação determinística `FakeEmbeddingProvider` é usada em testes e na construção local inicial para evitar rede, downloads de modelos e consumo externo. A implementação `SentenceTransformerEmbeddingProvider` existe para uso posterior com modelo configurável e carregamento preguiçoso.

O modelo documentado para uso real é `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, por ser pequeno, multilíngue e adequado a português em cenários de prototipação. Ele não é baixado durante importação de módulos nem durante testes.

## 9. Persistência

O índice vetorial e os metadados são persistidos localmente em `corpus/index/active`. O pipeline grava embeddings em `.npz`, metadados em JSON, artefatos lexicais de TF-IDF e um manifesto do índice com fingerprint do corpus, fingerprint de configuração e versão do formato.

Artefatos gerados não são versionados no Git. A reconstrução deve partir dos PDFs, do manifesto do corpus e da configuração.

## 10. Busca semântica

A busca semântica compara o embedding da pergunta com embeddings dos chunks para encontrar trechos conceitualmente próximos, mesmo quando as palavras não são idênticas.

## 11. Busca lexical

A busca lexical usa TF-IDF ou BM25 para capturar correspondências diretas de termos, siglas, nomes de seções e expressões específicas.

## 12. Fusão dos resultados

Os resultados semânticos e lexicais devem ser combinados por estratégia determinística, como soma ponderada ou Reciprocal Rank Fusion. A ponderação deve ser ajustável.

Na implementação inicial, a recuperação local combina similaridade cosseno dos embeddings normalizados com pontuação TF-IDF normalizada.

## 13. Deduplicação

Chunks repetidos ou muito próximos devem ser deduplicados por hash e por combinação de documento, página e índice do chunk. A deduplicação evita citações redundantes.

## 14. Avaliação de suficiência

Antes de chamar o LLM, o grafo deve avaliar se os trechos recuperados respondem à pergunta. Critérios podem incluir pontuação mínima, diversidade de fontes e presença de termos relevantes.

Na implementação atual, a suficiência é determinística: exige evidências acima de `EDUDOCS_MIN_RETRIEVAL_SCORE`, presença mínima de termos relevantes e diversidade de documentos quando a pergunta indicar comparação ou cruzamento documental.

## 15. Nova tentativa de recuperação

Se o primeiro conjunto de evidências for fraco, o grafo pode reformular a consulta e tentar nova recuperação. O número de tentativas deve ser limitado para controlar latência.

O limite atual é de duas recuperações por pergunta. A reformulação usa expansão controlada de sinônimos do domínio e não depende de LLM.

O endpoint de chat usa o `CompiledStateGraph` como fonte única de execução: o serviço monta o estado inicial e chama `graph.invoke`, enquanto decisões de rota, retry, suficiência, geração, validação de citações e fallback ficam dentro do grafo.

## 16. Geração da resposta

A geração deve receber pergunta, trechos selecionados e instruções para responder apenas com base nas evidências. O provedor de LLM será chamado por uma interface isolada.

Os provedores implementados são `FakeProvider`, usado em testes e smoke local, e `GroqProvider`, carregado apenas quando selecionado por configuração. O provider falso permite simular sucesso, indisponibilidade, timeout, rate limit, resposta vazia e citações inválidas.

## 17. Citações por documento e página

Toda afirmação relevante da resposta deve ser apoiada por citações no formato definido pela aplicação, contendo pelo menos documento e página. Citações não devem apontar para páginas sem evidência usada.

As fontes retornadas pelo endpoint são montadas a partir dos chunks efetivamente recuperados e validados contra o manifesto. O sistema não aceita documento, página ou trecho inventado pelo provedor.

## 18. Recusa quando não houver evidência

Quando os trechos recuperados não forem suficientes, o agente deve recusar a resposta de forma clara, sem inventar conteúdo e sem sugerir que consultou documentos inexistentes.

## 19. Proteção contra prompt injection documental

Trechos de documentos devem ser tratados como dados, não como instruções. O prompt deve separar regras do sistema, pergunta do usuário e contexto recuperado, ignorando comandos encontrados dentro dos PDFs.

O prompt do sistema instrui o provedor a usar somente evidências, não revelar instruções internas, não obedecer comandos presentes nos documentos e não usar conhecimento externo. A consulta também remove tentativas óbvias de comandar o sistema antes da recuperação.

## 20. Avaliação determinística

O conjunto `corpus/evaluation/questions.json` é executado por `python -m app.evaluation.cli run` com provider falso e índice local ativo. A avaliação mede recuperação isolada, execução do agente real via grafo LangGraph compilado, validade de citações, recusas, prompt injection, latência e erros técnicos.

Os relatórios padrão são `corpus/evaluation/results/latest.json` e `docs/evaluation-report.md`. O modo `--strict` usa thresholds configurados no avaliador e falha apenas quando critérios obrigatórios ficam abaixo do limite, preservando métricas negativas no relatório.

## 21. Limitações

O pipeline planejado não cobre OCR, documentos manuscritos, tabelas complexas, imagens embutidas, atualização incremental avançada ou avaliação automática de qualidade nesta etapa inicial.
