# Roteiro Do Vídeo De Demonstração PAYG

## Objetivo

Registrar a demonstração curta do EduDocs AI publicado temporariamente na OCI PAYG, sem expor OCIDs, IPs privados, CIDR administrativo, credenciais, fingerprints, estado do Terraform, plans ou chaves.

## Sequência Sugerida

1. Mostrar a instância OCI em estado `RUNNING`, com shape `VM.Standard.E4.Flex`, 1 OCPU, 8 GB de memória e boot volume de 50 GB.
2. Mostrar o Load Balancer ativo e o backend saudável, sem revelar identificadores sensíveis.
3. Abrir a aplicação pelo endpoint público do Load Balancer.
4. Validar a tela inicial e a experiência principal para usuários não técnicos.
5. Enviar uma pergunta suportada, por exemplo: `Como solicito certificado?`
6. Mostrar a resposta com fontes e páginas citadas.
7. Enviar uma pergunta não suportada, por exemplo: `Qual é a previsão do tempo em Marte hoje?`
8. Mostrar que o sistema responde de forma segura sem inventar fontes.
9. Mostrar a lista de documentos disponíveis.
10. Encerrar informando que o deploy é temporário e será parado após a coleta das evidências.

## Capturas Necessárias

- `docs/evidence/oci-application.png`: aplicação pública funcionando via Load Balancer.
- `docs/evidence/oci-instance-running.png`: instância OCI em execução no console.

## Cuidados

- Não mostrar OCIDs completos.
- Não mostrar IP privado.
- Não mostrar CIDR administrativo.
- Não mostrar arquivos locais de variáveis, arquivos de ambiente, estado do Terraform, plans, chaves ou fingerprints.
- Não abrir telas de billing com dados sensíveis.
