# Deployment OCI

Este documento descreve o caminho de deploy previsto para o EduDocs AI na OCI. A entrega atual valida apenas código Terraform e cloud-init; ela não cria recursos reais.

## Estado Atual

Concluído:

- Terraform em `infrastructure/terraform`.
- Módulos de rede, compute e object storage opcional.
- Cloud-init para preparar a VM base.
- Validação por `terraform fmt`, `terraform init -backend=false`, `terraform validate` e política local.
- CI sem credenciais e sem `plan/apply/destroy`.

Pendente:

- Credenciais OCI fora do Git.
- Confirmação de tenancy, compartment e home region.
- Confirmação de capacidade A1.
- Primeiro `terraform plan` real.
- Qualquer `terraform apply`.
- Publicação de imagens, deploy da aplicação, Groq real, domínio, HTTPS e screenshots OCI.

## Fluxo Seguro Futuro

1. Confirmar a conta OCI e a home region.
2. Confirmar o compartment de destino.
3. Confirmar disponibilidade de `VM.Standard.A1.Flex` com 2 OCPUs e 12 GB.
4. Definir `admin_cidr` com IP administrativo em `/32`.
5. Definir estratégia de state antes do primeiro plan real.
6. Criar `terraform.tfvars` local a partir de `infrastructure/terraform/terraform.tfvars.example`.
7. Rodar `make terraform-check`.
8. Somente após aprovação humana, rodar um primeiro `terraform plan` real.
9. Somente após revisão do plano, considerar `terraform apply`.

## Preparação Da Aplicação

A VM criada pelo Terraform fica pronta para receber um deploy futuro, mas o cloud-init não instala nem inicia o EduDocs AI. Isso evita misturar provisionamento de infraestrutura com publicação de aplicação e reduz risco de segredos acidentais.

Passos futuros esperados:

- Construir ou publicar imagens de API e web por processo aprovado.
- Criar arquivo de ambiente seguro fora do Git.
- Configurar Nginx para o host real.
- Configurar HTTPS após domínio real.
- Executar smoke test contra a URL pública.
- Produzir `docs/evidence/oci-application.png` e `docs/evidence/oci-instance-running.png`.

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
