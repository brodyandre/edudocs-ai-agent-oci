# Terraform OCI

Este diretório prepara a infraestrutura OCI do EduDocs AI sem criar recursos durante a validação local ou no CI.

## Escopo

O código define:

- VCN, Internet Gateway, route table, subnet pública e dois NSGs.
- Uma instância `VM.Standard.A1.Flex` com 2 OCPUs, 12 GB de memória e boot volume de 50 GB.
- Um OCI Flexible Load Balancer público com 10 Mbps mínimo e 10 Mbps máximo.
- Listener HTTP porta 80, backend set `ROUND_ROBIN`, backend no IP privado da VM porta 8080 e health checker `GET /health`.
- Cloud-init para preparar Docker Engine, Docker Compose plugin, diretórios em `/opt/edudocs` e marcador de conclusão.
- Bucket privado opcional para backups, desabilitado por padrão.

O código não executa deploy da aplicação, não publica imagem, não configura domínio, não emite HTTPS e não grava segredos.

## Pré-requisitos Antes De Um Plan Real

Antes do primeiro `terraform plan` real e antes de qualquer `apply`, confirme:

- Credenciais OCI configuradas fora do Git, por exemplo em `~/.oci/config`.
- Tenancy e compartment corretos.
- Home region escolhida para evitar criação acidental em região errada.
- Capacidade A1 disponível na availability domain escolhida.
- Elegibilidade do OCI Flexible Load Balancer 10 Mbps confirmada na tenancy.
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
- `enable_load_balancer = true`
- `load_balancer_shape = "flexible"`
- `load_balancer_min_bandwidth_mbps = 10`
- `load_balancer_max_bandwidth_mbps = 10`
- `load_balancer_listener_port = 80`
- `load_balancer_backend_port = 8080`
- `load_balancer_health_path = "/health"`
- `create_backup_bucket = false`

## Rede

O módulo de rede cria dois NSGs separados:

NSG do Load Balancer:

- Ingress TCP 80 de `0.0.0.0/0`.
- Egress TCP 8080 destinado ao NSG da aplicação.

NSG da aplicação:

- TCP 22 a partir de `admin_cidr`.
- TCP 8080 somente com origem no NSG do Load Balancer.
- Egress para atualizações, DNS, HTTPS e provedores externos configurados fora do Terraform.

Portas de desenvolvimento como 3000 e 8000 não são públicas na OCI. A porta 8080 não é pública diretamente; ela recebe apenas tráfego privado originado pelo Load Balancer.

## Load Balancer

O endpoint público futuro será exposto apenas pelo Load Balancer:

```text
http://<load_balancer_public_ip>
```

O health endpoint futuro será:

```text
http://<load_balancer_public_ip>/health
```

Esses valores são outputs conhecidos somente após um apply real. O Terraform não fixa IP público, não cria Reserved IP, não cria Network Load Balancer, não cria WAF, não cria certificado e não configura HTTPS nesta entrega.

## Cloud-init

O template `../cloud-init/app-server.yaml.tftpl` prepara a VM de forma idempotente:

- Instala Docker Engine e Docker Compose plugin via repositório apt oficial.
- Habilita e inicia Docker.
- Adiciona o usuário `ubuntu` ao grupo `docker`.
- Cria `/opt/edudocs`, `/opt/edudocs/config`, `/opt/edudocs/data`, `/opt/edudocs/data/index` e `/opt/edudocs/logs`.
- Escreve `/var/lib/edudocs/cloud-init-complete`.
- Registra logs em `/var/log/edudocs-cloud-init.log`.

O template não clona GitHub, não baixa imagens, não cria `.env`, não injeta chave Groq, não inicia Docker Compose e não configura HTTPS.

Uma etapa posterior publicará imagens ARM64, criará a configuração segura fora do Git e automatizará o bootstrap da aplicação.

## Bucket Opcional

`create_backup_bucket` fica `false` por padrão. Quando habilitado, o bucket é privado, usa storage tier `Standard` e não cria objetos, PARs, policies públicas, replicação ou regras destrutivas.

## State

Este repositório não versiona `terraform.tfvars`, `tfstate` ou planos. O lockfile `.terraform.lock.hcl` é versionado para fixar o provedor.

Para uso real, defina a estratégia de state antes do primeiro `terraform plan` real.
