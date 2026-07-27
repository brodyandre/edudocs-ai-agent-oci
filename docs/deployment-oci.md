# Deployment OCI

Este documento descreve o caminho de deploy previsto para o EduDocs AI na OCI. A entrega atual valida código Terraform, cloud-init e bootstrap declarativo da aplicação; ela não cria recursos reais.

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
- CI sem credenciais e sem `plan/apply/destroy`.

Pendente:

- Credenciais OCI fora do Git.
- Confirmação de tenancy, compartment e home region.
- Confirmação de capacidade A1.
- Confirmação de elegibilidade do Flexible Load Balancer 10 Mbps na tenancy.
- Primeiro `terraform plan` real.
- Qualquer `terraform apply`.
- IP real do Load Balancer, Groq real, domínio, HTTPS e screenshots OCI.

## Fluxo Seguro Futuro

1. Confirmar `API_IMAGE_REF` e `WEB_IMAGE_REF` por digest pelo artefato `edudocs-container-release`.
2. Confirmar que as imagens GHCR estão públicas e aceitam pull anônimo.
3. Confirmar a conta OCI, tenancy, compartment, home region, capacidade A1 e Free Tier.
4. Confirmar elegibilidade do OCI Flexible Load Balancer com mínimo 10 Mbps e máximo 10 Mbps.
5. Definir `admin_cidr` com IP administrativo em `/32`.
6. Definir estratégia de state antes do primeiro plan real.
7. Criar `terraform.tfvars` local a partir de `infrastructure/terraform/terraform.tfvars.example`.
8. Rodar `make terraform-check`.
9. Somente após aprovação humana, rodar um primeiro `terraform plan` real.
10. Revisar o plan.
11. Somente após revisão do plano, considerar `terraform apply`.
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

## Política Do Plan Futuro

A allowlist do primeiro plan real deve aceitar apenas:

- `oci_load_balancer_load_balancer`
- `oci_load_balancer_backend_set`
- `oci_load_balancer_backend`
- `oci_load_balancer_listener`
- recursos Core já declarados para VCN, subnet, Internet Gateway, route table, NSGs e regras NSG
- uma instância Compute
- bucket privado somente quando explicitamente habilitado

O plan futuro deve reprovar se não houver Load Balancer, se houver mais de um Load Balancer, se a banda ultrapassar 10 Mbps, se aparecer recurso pago inesperado, ou se houver delete/replace inesperado.

## UFW

O pacote `ufw` é instalado pela preparação da VM, mas não é habilitado automaticamente. O controle primário de exposição fica no NSG da OCI. Antes de habilitar UFW manualmente, confirme regras equivalentes para SSH administrativo e HTTP/HTTPS necessários.

## Comandos Proibidos Nesta Entrega

Não execute nesta entrega:

```bash
terraform plan
terraform apply
terraform destroy
terraform apply -auto-approve
terraform destroy -auto-approve
```

Esses comandos dependem de credenciais reais e revisão explícita.
