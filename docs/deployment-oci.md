# Deployment OCI

Este documento descreve o caminho de deploy previsto para o EduDocs AI na OCI. A entrega atual valida apenas código Terraform e cloud-init; ela não cria recursos reais.

## Estado Atual

Concluído:

- Terraform em `infrastructure/terraform`.
- Módulos de rede, compute, load balancer e object storage opcional.
- OCI Flexible Load Balancer público declarado com 10/10 Mbps, listener HTTP 80, backend set, backend privado 8080 e health checker `/health`.
- Dois NSGs separados: Load Balancer público e aplicação privada.
- Cloud-init para preparar a VM base.
- Validação por `terraform fmt`, `terraform init -backend=false`, `terraform validate` e política local.
- CI sem credenciais e sem `plan/apply/destroy`.

Pendente:

- Credenciais OCI fora do Git.
- Confirmação de tenancy, compartment e home region.
- Confirmação de capacidade A1.
- Confirmação de elegibilidade do Flexible Load Balancer 10 Mbps na tenancy.
- Primeiro `terraform plan` real.
- Qualquer `terraform apply`.
- Publicação de imagens, start da aplicação, IP real do Load Balancer, Groq real, domínio, HTTPS e screenshots OCI.

## Fluxo Seguro Futuro

1. Confirmar a conta OCI e a home region.
2. Confirmar o compartment de destino.
3. Confirmar disponibilidade de `VM.Standard.A1.Flex` com 2 OCPUs e 12 GB.
4. Confirmar elegibilidade do OCI Flexible Load Balancer com mínimo 10 Mbps e máximo 10 Mbps.
5. Definir `admin_cidr` com IP administrativo em `/32`.
6. Definir estratégia de state antes do primeiro plan real.
7. Criar `terraform.tfvars` local a partir de `infrastructure/terraform/terraform.tfvars.example`.
8. Rodar `make terraform-check`.
9. Somente após aprovação humana, rodar um primeiro `terraform plan` real.
10. Somente após revisão do plano, considerar `terraform apply`.

## Preparação Da Aplicação

A VM criada pelo Terraform fica pronta para receber um deploy futuro, mas o cloud-init não instala nem inicia o EduDocs AI. Isso evita misturar provisionamento de infraestrutura com publicação de aplicação e reduz risco de segredos acidentais.

Passos futuros esperados:

- Construir ou publicar imagens de API e web por processo aprovado.
- Criar arquivo de ambiente seguro fora do Git.
- Publicar imagens ARM64 por processo aprovado.
- Iniciar Nginx em Docker na VM escutando `8080:8080`.
- Executar a primeira validação em `http://<load_balancer_public_ip>`.
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
