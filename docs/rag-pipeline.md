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

Os embeddings serão gerados por modelo multilíngue local configurável. A escolha do modelo deve considerar português, compatibilidade ARM64 e execução local.

## 9. Persistência

O índice vetorial e os metadados serão persistidos localmente em `corpus/index/`. Artefatos gerados não devem ser versionados no Git.

## 10. Busca semântica

A busca semântica compara o embedding da pergunta com embeddings dos chunks para encontrar trechos conceitualmente próximos, mesmo quando as palavras não são idênticas.

## 11. Busca lexical

A busca lexical usa TF-IDF ou BM25 para capturar correspondências diretas de termos, siglas, nomes de seções e expressões específicas.

## 12. Fusão dos resultados

Os resultados semânticos e lexicais devem ser combinados por estratégia determinística, como soma ponderada ou Reciprocal Rank Fusion. A ponderação deve ser ajustável.

## 13. Deduplicação

Chunks repetidos ou muito próximos devem ser deduplicados por hash e por combinação de documento, página e índice do chunk. A deduplicação evita citações redundantes.

## 14. Avaliação de suficiência

Antes de chamar o LLM, o grafo deve avaliar se os trechos recuperados respondem à pergunta. Critérios podem incluir pontuação mínima, diversidade de fontes e presença de termos relevantes.

## 15. Nova tentativa de recuperação

Se o primeiro conjunto de evidências for fraco, o grafo pode reformular a consulta e tentar nova recuperação. O número de tentativas deve ser limitado para controlar latência.

## 16. Geração da resposta

A geração deve receber pergunta, trechos selecionados e instruções para responder apenas com base nas evidências. O provedor de LLM será chamado por uma interface isolada.

## 17. Citações por documento e página

Toda afirmação relevante da resposta deve ser apoiada por citações no formato definido pela aplicação, contendo pelo menos documento e página. Citações não devem apontar para páginas sem evidência usada.

## 18. Recusa quando não houver evidência

Quando os trechos recuperados não forem suficientes, o agente deve recusar a resposta de forma clara, sem inventar conteúdo e sem sugerir que consultou documentos inexistentes.

## 19. Proteção contra prompt injection documental

Trechos de documentos devem ser tratados como dados, não como instruções. O prompt deve separar regras do sistema, pergunta do usuário e contexto recuperado, ignorando comandos encontrados dentro dos PDFs.

## 20. Limitações

O pipeline planejado não cobre OCR, documentos manuscritos, tabelas complexas, imagens embutidas, atualização incremental avançada ou avaliação automática de qualidade nesta etapa inicial.
