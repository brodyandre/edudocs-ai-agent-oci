# Deployment OCI

Este documento registra o ciclo controlado do workload temporário PAYG do EduDocs AI na OCI: preparação, demonstração, evidências e encerramento. A configuração Terraform permanece versionada e reprodutível, mas o workload temporário validado em 03/08/2026 foi removido após a demonstração.

## Estado Atual

Concluído:

- Terraform em `infrastructure/terraform`.
- Stack bootstrap independente em `infrastructure/terraform-bootstrap/compartment` aplicada para criar somente `edudocs-ai-prod`.
- Módulos de rede, compute, load balancer e object storage opcional.
- OCI Flexible Load Balancer público validado com 10/10 Mbps, listener HTTP 80, backend set, backend privado 8080 e health checker `/health`.
- Dois NSGs separados: Load Balancer público e aplicação privada.
- Cloud-init para instalar Docker, renderizar Compose produtivo, arquivo de ambiente não secreto, Nginx 8080 e unidade systemd.
- Workflow manual preparado e validado para publicar imagens API/Web multiarch no GHCR.
- Compose de produção preparado para usar referências imutáveis por digest e providers `fake`.
- Validação por `terraform fmt`, `terraform init -backend=false`, `terraform validate`, política local e `scripts/check_runtime_bootstrap.py`.
- Readiness OCI ajustada para exigir o compartment filho `edudocs-ai-prod` ativo antes do plan do workload.
- Primeiro apply do workload executado uma única vez, com falha parcial preservando o estado.
- Recuperação consciente do estado aplicada uma única vez, criando somente backend set, backend e listener.
- Aplicação pública validada pelo Load Balancer em 03/08/2026.
- VM parada antes do teardown.
- Workload temporário removido por saved destroy plan auditado, aplicado uma única vez.
- State principal final sem recursos gerenciados.
- Backend local explícito preparado para o workload, com state principal externo e wrapper `scripts/terraform_workload.sh`.
- CI sem credenciais e sem `plan/apply/destroy`.
- Compartment `edudocs-ai-prod` validado como `ACTIVE`.
- Budget `edudocs-ai-demo-payg` preservado como `ACTIVE`.
- Evidências de deploy preservadas em `docs/evidence`.

Pendente:

- Groq real fora do ambiente de teste.
- Domínio próprio e HTTPS para uma futura publicação.
- Observabilidade e controles de uso para qualquer ambiente duradouro.
- Cost Analysis pode levar algum tempo para refletir totalmente o encerramento dos recursos removidos.

## Fluxo Seguro Para Nova Publicação

1. Confirmar `API_IMAGE_REF` e `WEB_IMAGE_REF` por digest pelo artefato `edudocs-container-release`.
2. Confirmar que as imagens GHCR estão públicas e aceitam pull anônimo.
3. Manter variáveis locais fora do Git com profile `EDUDOCS`, origem administrativa restrita, chave SSH, digests GHCR e compartment filho.
4. Rodar `make oci-readiness`.
5. Rodar `make workload-pre-apply-check`.
6. Rodar `make terraform-check`.
7. Gerar `terraform plan` real do workload para arquivo local em `/tmp` usando `scripts/terraform_workload.sh`.
8. Gerar JSON do plan com `scripts/terraform_workload.sh show-json`.
9. Auditar com `make terraform-plan-check TERRAFORM_PLAN_JSON=/tmp/edudocs-oci.tfplan.json TERRAFORM_TFVARS=infrastructure/terraform/terraform.tfvars`.
10. Revisar novamente capacidade E4 Flex 1/8, orçamento PAYG, state vazio e plano salvo.
11. Somente após revisão e aprovação humana literal, considerar `scripts/terraform_workload.sh apply-saved-plan`.
12. Nunca usar `-auto-approve`.
13. Durante um apply aprovado do workload, o cloud-init instala Docker, faz pull anônimo dos digests, inicia `edudocs-compose.service` e aguarda `/health`.
14. Validar `/health` pelo Load Balancer.
15. Validar o endpoint temporário do Load Balancer sem registrar o endereço público no repositório.

## Preparação Da Aplicação

O bootstrap da aplicação é declarativo e renderizado pelo Terraform para a VM. Ele não usa segredos, não clona repositório, não faz `docker login`, não usa `latest` e não depende de comando manual dentro da instância.

Contrato atual do bootstrap:

- Usar imagens API e web publicadas no GHCR por digest.
- Renderizar arquivo de ambiente não secreto com referências imutáveis de API/Web, providers falsos e `NGINX_PORT=8080`.
- Renderizar `/opt/edudocs/docker-compose.yml` com API e web sem portas publicadas no host.
- Iniciar Nginx em Docker escutando `8080:8080`.
- Criar `/var/lib/edudocs/application-ready` e `/var/lib/edudocs/cloud-init-complete` após `http://127.0.0.1:8080/health` responder.
- Executar a validação pública pelo endpoint temporário do Load Balancer.
- Configurar DNS para uma URL nominal posteriormente.
- Configurar HTTPS após domínio real em etapa futura.
- Executar smoke test contra o Load Balancer.
- Produzir ou preservar evidências sanitizadas em `docs/evidence`.

## Teardown Controlado 11J

Após a demonstração, o teardown controlado removeu somente recursos do workload gerenciados pelo state principal:

- instância Compute;
- OCI Flexible Load Balancer;
- listener;
- backend;
- backend set;
- VCN;
- subnet;
- Internet Gateway;
- route table;
- NSGs;
- regras de NSG.

Não foram removidos:

- compartment `edudocs-ai-prod`;
- budget `edudocs-ai-demo-payg`;
- state separado do bootstrap do compartment;
- backups externos do state;
- evidências em `docs/evidence`;
- imagens GHCR;
- repositório e histórico Git;
- configurações da conta OCI.

O endpoint público temporário deixou de estar disponível. Um plan normal posterior pode propor recriação dos recursos porque a configuração continua versionada; isso não é falha do teardown e não deve ser aplicado sem nova autorização explícita.

## Política Do Plan

A allowlist do plan real aceita apenas:

- `oci_load_balancer_load_balancer`
- `oci_load_balancer_backend_set`
- `oci_load_balancer_backend`
- `oci_load_balancer_listener`
- recursos Core já declarados para VCN, subnet, Internet Gateway, route table, NSGs e regras NSG
- uma instância Compute
- bucket privado somente quando explicitamente habilitado

O plan deve reprovar se não houver Load Balancer, se houver mais de um Load Balancer, se a banda ultrapassar 10 Mbps, se aparecer recurso pago inesperado, ou se houver delete/replace inesperado.

O plan do workload também deve reprovar se qualquer recurso com `compartment_id` apontar para a tenancy/root ou para valor diferente do compartment filho informado no `terraform.tfvars` local.

## UFW

O pacote `ufw` é instalado pela preparação da VM, mas não é habilitado automaticamente. O controle primário de exposição fica no NSG da OCI. Antes de habilitar UFW manualmente, confirme regras equivalentes para SSH administrativo e HTTP/HTTPS necessários.

## Comandos Proibidos Nesta Entrega

Não execute nesta entrega:

```bash
terraform apply
terraform destroy
terraform apply -auto-approve
terraform destroy -auto-approve
```

`terraform plan` é permitido somente para arquivo local, com revisão e auditoria JSON. O apply do workload principal deve usar `scripts/terraform_workload.sh apply-saved-plan` e depende de confirmação humana literal descrita em [Runbook de apply do workload OCI](oci-workload-apply-runbook.md). `destroy`, `import` e mutações manuais de state não fazem parte desta etapa.
