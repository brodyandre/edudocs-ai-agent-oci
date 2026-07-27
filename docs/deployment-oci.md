# Deployment OCI

Este documento descreve o caminho de deploy previsto para o EduDocs AI na OCI. A entrega atual valida código Terraform, cloud-init, bootstrap declarativo da aplicação e o primeiro `terraform plan` real; ela não cria recursos reais.

## Estado Atual

Concluído:

- Terraform em `infrastructure/terraform`.
- Módulos de rede, compute, load balancer e object storage opcional.
- OCI Flexible Load Balancer público declarado com 10/10 Mbps, listener HTTP 80, backend set, backend privado 8080 e health checker `/health`.
- Dois NSGs separados: Load Balancer público e aplicação privada.
- Cloud-init para instalar Docker, renderizar Compose produtivo, `runtime.env` não secreto, Nginx 8080 e unidade systemd.
- Workflow manual preparado e validado para publicar imagens API/Web multiarch no GHCR.
- Compose de produção preparado para usar referências imutáveis por digest e providers `fake`.
- Validação por `terraform fmt`, `terraform init -backend=false`, `terraform validate`, política local e `scripts/check_runtime_bootstrap.py`.
- Readiness OCI validada com perfil `EDUDOCS`, home region `sa-saopaulo-1`, AD disponível e root compartment da tenancy como alvo.
- Primeiro `terraform plan` real gerado, salvo fora do Git e auditado por `scripts/check_terraform_plan.py`.
- CI sem credenciais e sem `plan/apply/destroy`.

Pendente:

- Confirmação final de capacidade A1 imediatamente antes do apply.
- Confirmação final de elegibilidade do Flexible Load Balancer 10 Mbps na tenancy imediatamente antes do apply.
- Estratégia de state aprovada para operação real.
- Qualquer `terraform apply`.
- IP real do Load Balancer, Groq real, domínio, HTTPS e screenshots OCI.

## Fluxo Seguro Futuro

1. Confirmar `API_IMAGE_REF` e `WEB_IMAGE_REF` por digest pelo artefato `edudocs-container-release`.
2. Confirmar que as imagens GHCR estão públicas e aceitam pull anônimo.
3. Manter `terraform.tfvars` local fora do Git com profile `EDUDOCS`, CIDR administrativo em `/32`, chave SSH e digests GHCR.
4. Rodar `make oci-readiness`.
5. Rodar `make terraform-check`.
6. Gerar `terraform plan` real para arquivo local em `/tmp`.
7. Gerar JSON do plan com `terraform show -json`.
8. Auditar com `make terraform-plan-check TERRAFORM_PLAN_JSON=/tmp/edudocs-oci.tfplan.json`.
9. Revisar novamente capacidade A1, Free Tier, state e plano salvo.
10. Somente após revisão e aprovação humana, considerar `terraform apply`.
11. Nunca usar `-auto-approve`.
12. Durante o apply aprovado, o cloud-init instala Docker, faz pull anônimo dos digests, inicia `edudocs-compose.service` e aguarda `/health`.
13. Validar `/health` pelo Load Balancer.
14. Abrir `http://<IP-PUBLICO-DO-LOAD-BALANCER>`.

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

`terraform plan` é permitido somente para arquivo local, com revisão e auditoria JSON. `apply` e `destroy` dependem de aprovação explícita posterior e não fazem parte desta entrega.
