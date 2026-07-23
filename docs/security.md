# Segurança

## 1. Princípios de segurança

O projeto deve aplicar privilégio mínimo, separação de responsabilidades, configuração por ambiente, logs sanitizados e recusa de operações que dependam de segredos ausentes ou inválidos.

## 2. Tratamento de segredos

Tokens, senhas, chaves OCI, chaves Groq e credenciais nunca devem ser gravados no repositório. Segredos devem ser fornecidos por variáveis de ambiente, cofre de segredos ou configuração segura do ambiente de execução.

## 3. Variáveis de ambiente

O arquivo `.env.example` deve conter apenas nomes de variáveis e valores demonstrativos não sensíveis. Arquivos `.env` reais permanecem ignorados pelo Git.

## 4. Proibição de segredos no frontend

O frontend não deve receber chaves de API, tokens privados ou credenciais de infraestrutura. Chamadas a provedores externos devem passar pela API backend.

## 5. Limites de entrada

A API planejada deve limitar tamanho de perguntas, quantidade de requisições e formatos aceitos. Entradas grandes ou malformadas devem ser rejeitadas com erro controlado.

## 6. Validação de perguntas

Perguntas devem ser normalizadas e validadas antes da execução do grafo. Conteúdo vazio, excessivo ou com comandos incompatíveis com o escopo deve ser recusado ou tratado de forma segura.

## 7. Validação dos PDFs

PDFs do corpus devem ser fictícios, controlados e armazenados em diretório próprio. A ingestão deve validar extensão, tamanho, leitura por PyMuPDF e ausência de necessidade de credenciais.

## 8. CORS

A política de CORS deve permitir apenas origens necessárias para execução local e deploy. Permissões amplas podem ser usadas temporariamente apenas em desenvolvimento consciente e documentado.

## 9. Rate limiting

O MVP deve prever limitação de taxa na API ou no Nginx para reduzir abuso, loops de interface e consumo indevido do provedor de LLM.

## 10. Timeouts

Chamadas de recuperação, geração e rede devem ter timeouts definidos. Falhas por timeout devem retornar mensagens controladas e não expor detalhes internos.

O provedor Groq usa timeout explícito por configuração e retries limitados. Timeouts são mapeados para erro HTTP 504 no endpoint de chat.

## 11. Logs estruturados e sanitizados

Logs devem evitar perguntas completas quando houver risco de conteúdo sensível. Quando necessário, registrar identificadores, tempos, contagens e erros sanitizados.

O endpoint `POST /api/chat` registra apenas `request_id`, rota, status, latência, provider, quantidade de evidências, `answerable` e tipo de erro. Não registra chave Groq, prompt integral, resposta integral, cabeçalhos sensíveis, variáveis de ambiente ou conteúdo integral dos PDFs.

## 12. Proteção contra prompt injection

Documentos recuperados são dados, não instruções. O prompt deve reforçar que comandos encontrados nos PDFs não podem alterar regras do sistema, exfiltrar segredos ou desviar do escopo.

Além do prompt, o agente valida fontes a partir de chunks recuperados e recusa quando não há sustentação documental. Pedidos para ignorar documentos, revelar prompt, revelar segredos ou usar conhecimento externo não devem produzir resposta factual sem evidência.

## 13. Dependências

Dependências devem ser mínimas, fixadas quando apropriado e revisadas antes da entrega. Ferramentas de auditoria podem ser usadas sem prometer ausência total de vulnerabilidades.

## 14. Auditoria npm

Auditoria executada em 23 de julho de 2026:

- `npm --prefix apps/web audit --omit=dev`: 0 vulnerabilidades.
- `npm --prefix apps/web audit`: 0 vulnerabilidades.

O achado histórico em `next -> postcss` foi removido com override global para `postcss ^8.5.22`, evitando a cópia aninhada vulnerável em `node_modules/next/node_modules/postcss`. A política do CI continua bloqueando vulnerabilidades `high`, `critical` ou achados fora da baseline explicitamente aceita pelo script.

## 15. Imagens Docker

As imagens planejadas devem usar bases oficiais ou confiáveis, camadas enxutas e versões compatíveis com ARM64. Segredos não devem ser copiados para imagens.

## 16. Usuário não root

Containers de aplicação devem executar com usuário não root sempre que possível. Diretórios de escrita devem ter permissões específicas para o processo da aplicação.

## 17. Regras de rede OCI

O Terraform OCI libera SSH apenas para `admin_cidr` e HTTP/HTTPS para o proxy quando habilitados. Portas de desenvolvimento como 3000, 8000 e 8080 não devem ser expostas diretamente na OCI.

## 18. SSH restrito

Acesso SSH à instância OCI deve ser limitado por chave, usuário apropriado e origem controlada. Senhas de SSH não devem ser usadas.

## 19. HTTPS

O acesso público planejado deve usar HTTPS. A emissão e renovação de certificados devem ser tratadas na etapa de deploy, sem inserir chaves privadas no repositório.

## 20. Atualizações e correções

Dependências, imagens e pacotes do sistema devem receber atualizações compatíveis com a estabilidade do projeto. Correções de segurança relevantes devem ter prioridade.

## 21. CI e segredos

Os workflows de CI usam `permissions: contents: read`, providers `fake` e não recebem `GROQ_API_KEY`. A verificação `scripts/check_repository_hygiene.py` bloqueia arquivos sensíveis versionados, state/plans Terraform, chaves privadas, tokens comuns e valores reais de `GROQ_API_KEY` sem imprimir o segredo detectado.

## 22. Limitações do MVP

O MVP não implementa autenticação, multiusuário, cofre de segredos integrado, WAF, auditoria completa, criptografia customizada de índice ou políticas corporativas avançadas.
