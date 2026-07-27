# Deployment OCI

Este documento descreve o caminho de deploy previsto para o EduDocs AI na OCI. A entrega atual separa o bootstrap do compartment dedicado do workload principal, valida código Terraform, cloud-init e política local, e mantém o workload sem `apply`.

## Estado Atual

Concluído:

- Terraform em `infrastructure/terraform`.
- Stack bootstrap independente em `infrastructure/terraform-bootstrap/compartment` para criar somente `edudocs-ai-prod`.
- Módulos de rede, compute, load balancer e object storage opcional.
- OCI Flexible Load Balancer público declarado com 10/10 Mbps, listener HTTP 80, backend set, backend privado 8080 e health checker `/health`.
- Dois NSGs separados: Load Balancer público e aplicação privada.
- Cloud-init para instalar Docker, renderizar Compose produtivo, `runtime.env` não secreto, Nginx 8080 e unidade systemd.
- Workflow manual preparado e validado para publicar imagens API/Web multiarch no GHCR.
- Compose de produção preparado para usar referências imutáveis por digest e providers `fake`.
- Validação por `terraform fmt`, `terraform init -backend=false`, `terraform validate`, política local e `scripts/check_runtime_bootstrap.py`.
- Readiness OCI ajustada para exigir o compartment filho `edudocs-ai-prod` ativo antes do plan do workload.
- Primeiro `terraform plan` real gerado, salvo fora do Git e auditado por `scripts/check_terraform_plan.py`.
- CI sem credenciais e sem `plan/apply/destroy`.

Pendente:

- Commit e CI verde do bootstrap antes de qualquer mutação OCI.
- Plan bootstrap salvo e aprovado para criar somente `edudocs-ai-prod`.
- Apply restrito ao plan salvo do bootstrap do compartment.
- Novo plan do workload principal apontando para o compartment filho.
- Confirmação final de capacidade A1 antes de qualquer apply do workload.
- Confirmação final de elegibilidade do Flexible Load Balancer 10 Mbps na tenancy antes de qualquer apply do workload.
- Estratégia de state aprovada para operação real do workload.
- Qualquer `terraform apply` do workload principal.
- IP real do Load Balancer, Groq real, domínio, HTTPS e screenshots OCI.

## Fluxo Seguro Futuro

1. Confirmar que o código bootstrap do compartment está em `main` e com CI verde.
2. Gerar, auditar e aprovar o plan salvo da pilha `terraform-bootstrap/compartment`.
3. Aplicar somente o plan salvo que cria `edudocs-ai-prod`.
4. Aguardar `edudocs-ai-prod` ficar `ACTIVE`.
5. Confirmar `API_IMAGE_REF` e `WEB_IMAGE_REF` por digest pelo artefato `edudocs-container-release`.
6. Confirmar que as imagens GHCR estão públicas e aceitam pull anônimo.
7. Manter `terraform.tfvars` local fora do Git com profile `EDUDOCS`, CIDR administrativo em `/32`, chave SSH, digests GHCR e OCID do compartment filho.
8. Rodar `make oci-readiness`.
9. Rodar `make terraform-check`.
10. Gerar `terraform plan` real do workload para arquivo local em `/tmp`.
11. Gerar JSON do plan com `terraform show -json`.
12. Auditar com `make terraform-plan-check TERRAFORM_PLAN_JSON=/tmp/edudocs-oci.tfplan.json TERRAFORM_TFVARS=infrastructure/terraform/terraform.tfvars`.
13. Revisar novamente capacidade A1, Free Tier, state e plano salvo.
14. Somente após revisão e aprovação humana, considerar `terraform apply` do workload em etapa futura.
15. Nunca usar `-auto-approve`.
16. Durante o apply aprovado do workload, o cloud-init instala Docker, faz pull anônimo dos digests, inicia `edudocs-compose.service` e aguarda `/health`.
17. Validar `/health` pelo Load Balancer.
18. Abrir `http://<IP-PUBLICO-DO-LOAD-BALANCER>`.

## Preparação Da Aplicação

O bootstrap da aplicação é declarativo e renderizado pelo Terraform para a VM. Ele não usa segredos, não clona repositório, não faz `docker login`, não usa `latest` e não depende de comando manual dentro da instância.

Contrato atual do bootstrap:

- Usar imagens API e web publicadas no GHCR por digest.
- Renderizar `/opt/edudocs/runtime.env` com `API_IMAGE_REF`, `WEB_IMAGE_REF`, `EDUDOCS_LLM_PROVIDER=fake`, `EDUDOCS_EMBEDDING_PROVIDER=fake` e `NGINX_PORT=8080`.
- Renderizar `/opt/edudocs/docker-compose.yml` com API e web sem portas publicadas no host.
- Iniciar Nginx em Docker escutando `8080:8080`.
- Criar `/var/lib/edudocs/application-ready` e `/var/lib/edudocs/cloud-init-complete` após `http://127.0.0.1:8080/health` responder.
- Executar a primeira validação pública em `http://<load_balancer_public_ip>`.
- Configurar DNS para uma URL nominal posteriormente.
- Configurar HTTPS após domínio real em etapa futura.
- Executar smoke test contra o Load Balancer.
- Produzir `docs/evidence/oci-application.png` e `docs/evidence/oci-instance-running.png`.

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

`terraform plan` é permitido somente para arquivo local, com revisão e auditoria JSON. Nesta entrega, o único `apply` permitido é o do plan salvo da pilha bootstrap do compartment; `apply` do workload principal e `destroy` não fazem parte desta etapa.
