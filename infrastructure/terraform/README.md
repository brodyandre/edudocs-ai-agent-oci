# Terraform OCI

Este diretório prepara a infraestrutura OCI do EduDocs AI sem criar recursos durante a validação local ou no CI.

## Escopo

O código define:

- VCN, Internet Gateway, route table, subnet pública e NSG.
- Uma instância `VM.Standard.A1.Flex` com 2 OCPUs, 12 GB de memória e boot volume de 50 GB.
- Cloud-init para preparar Docker Engine, Docker Compose plugin, diretórios em `/opt/edudocs` e marcador de conclusão.
- Bucket privado opcional para backups, desabilitado por padrão.

O código não executa deploy da aplicação, não publica imagem, não configura domínio, não emite HTTPS e não grava segredos.

## Pré-requisitos Antes De Um Plan Real

Antes do primeiro `terraform plan` real e antes de qualquer `apply`, confirme:

- Credenciais OCI configuradas fora do Git, por exemplo em `~/.oci/config`.
- Tenancy e compartment corretos.
- Home region escolhida para evitar criação acidental em região errada.
- Capacidade A1 disponível na availability domain escolhida.
- `admin_cidr` com IP administrativo em `/32`, nunca `0.0.0.0/0`.
- Estratégia de state aprovada. O backend local é aceitável apenas para validação isolada; para uso real, defina uma estratégia segura de state antes do primeiro apply.
- Chave pública SSH local existente e autorizada para acesso administrativo.

## Validação Sem Credenciais

Os comandos abaixo não criam recursos e são seguros para CI:

```bash
make terraform-check
```

Equivalente manual:

```bash
terraform -chdir=infrastructure/terraform fmt -recursive -check
terraform -chdir=infrastructure/terraform init -backend=false
terraform -chdir=infrastructure/terraform validate
python3 scripts/check_terraform_policy.py
```

Não rode `terraform plan`, `terraform apply` ou `terraform destroy` nesta etapa.

## Variáveis

Use `terraform.tfvars.example` como referência e crie um `terraform.tfvars` local fora do Git quando for validar contra uma tenancy real.

Valores sem default por segurança:

- `tenancy_ocid`
- `compartment_ocid`
- `region`
- `ssh_public_key_path`
- `admin_cidr`

Valores conservadores com default:

- `compute_shape = "VM.Standard.A1.Flex"`
- `compute_ocpus = 2`
- `compute_memory_gbs = 12`
- `boot_volume_size_gbs = 50`
- `create_backup_bucket = false`

## Rede

O NSG libera apenas:

- TCP 22 a partir de `admin_cidr`.
- TCP 80 quando `enable_http = true`.
- TCP 443 quando `enable_https = true`.
- Egress para atualizações, DNS, HTTPS e provedores externos configurados fora do Terraform.

Portas de desenvolvimento como 3000, 8000 e 8080 não são públicas na OCI.

## Cloud-init

O template `../cloud-init/app-server.yaml.tftpl` prepara a VM de forma idempotente:

- Instala Docker Engine e Docker Compose plugin via repositório apt oficial.
- Habilita e inicia Docker.
- Adiciona o usuário `ubuntu` ao grupo `docker`.
- Cria `/opt/edudocs`, `/opt/edudocs/config`, `/opt/edudocs/data`, `/opt/edudocs/data/index` e `/opt/edudocs/logs`.
- Escreve `/var/lib/edudocs/cloud-init-complete`.
- Registra logs em `/var/log/edudocs-cloud-init.log`.

O template não clona GitHub, não baixa imagens, não cria `.env`, não injeta chave Groq, não inicia Docker Compose e não configura HTTPS.

## Bucket Opcional

`create_backup_bucket` fica `false` por padrão. Quando habilitado, o bucket é privado, usa storage tier `Standard` e não cria objetos, PARs, policies públicas, replicação ou regras destrutivas.

## State

Este repositório não versiona `terraform.tfvars`, `tfstate` ou planos. O lockfile `.terraform.lock.hcl` é versionado para fixar o provedor.

Para uso real, defina a estratégia de state antes do primeiro `terraform plan` real.
