# Evidencias

Este diretorio guarda capturas reais usadas no README para demonstrar a experiencia local, a validacao de qualidade e a demonstracao OCI PAYG temporaria do EduDocs AI.

As evidencias OCI sao historicas: a demonstracao foi concluida, a VM foi parada antes do teardown e o workload temporario foi removido em 03/08/2026. O endpoint publico temporario nao esta mais disponivel. As capturas permanecem versionadas para auditoria, portfolio e rastreabilidade do Challenge.

As capturas OCI registram somente informacoes sanitizadas para portfolio:

- aplicacao publica acessivel pelo Load Balancer;
- instancia OCI em execucao;
- Load Balancer ativo;
- backend set com backend saudavel;
- orcamento PAYG ativo com alerta de gasto real;
- Terraform sem mudancas apos recuperacao consciente do estado.

O teardown preservou o compartment, o budget, o state separado do bootstrap, os backups externos do state, o repositorio Git, as imagens GHCR e estas evidencias.

Nao versionar neste diretorio arquivos com OCIDs completos, IP privado, CIDR administrativo, enderecos de contato, dados de pagamento, credenciais, arquivos locais de variaveis, arquivos de ambiente, estado do Terraform ou planos Terraform.
