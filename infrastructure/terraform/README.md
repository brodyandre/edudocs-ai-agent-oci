# Terraform OCI

Este diretório prepara o workload OCI do EduDocs AI dentro de um compartment filho dedicado. Validações locais e CI continuam sem criar recursos; um `terraform plan` real pode ser gerado manualmente para arquivo local e auditado sem `apply`.

O compartment `edudocs-ai-prod` é criado por uma pilha independente em `../terraform-bootstrap/compartment`, com state local separado fora do repositório. Este diretório principal não cria compartments e não deve usar o root compartment da tenancy como alvo. O state principal do workload também deve ficar fora do repositório e ser acessado por `../../scripts/terraform_workload.sh`.

## Escopo

O código define:

- VCN, Internet Gateway, route table, subnet pública e dois NSGs.
- Uma instância `VM.Standard.A1.Flex` com 2 OCPUs, 12 GB de memória e boot volume de 50 GB.
- Um OCI Flexible Load Balancer público com 10 Mbps mínimo e 10 Mbps máximo.
- Listener HTTP porta 80, backend set `ROUND_ROBIN`, backend no IP privado da VM porta 8080 e health checker `GET /health`.
- Cloud-init para instalar Docker, renderizar `docker-compose.yml`, `runtime.env`, Nginx, unidade systemd e aguardar o health check da aplicação.
- Bucket privado opcional para backups, desabilitado por padrão.

O código declara o bootstrap da aplicação por imagens GHCR públicas e imutáveis por digest, usando `FakeProvider` por padrão e sem gravar segredos no Terraform, no cloud-init ou no user data. A validação local e o CI não criam recursos, não fazem `apply`, não configuram domínio e não emitem HTTPS.

## Pré-requisitos Antes De Um Plan Real Ou Apply

Antes do primeiro `terraform plan` real e antes de qualquer `apply`, confirme:

- Credenciais OCI configuradas fora do Git, por exemplo em `~/.oci/config`.
- Tenancy e compartment filho dedicado corretos. `compartment_ocid` deve apontar para um OCID de `compartment`, nunca para a tenancy/root.
- Home region escolhida para evitar criação acidental em região errada.
- Capacidade A1 disponível na availability domain escolhida.
- Elegibilidade do OCI Flexible Load Balancer 10 Mbps confirmada na tenancy.
- `admin_cidr` com IP administrativo em `/32`, nunca `0.0.0.0/0`.
- State principal externo inicializado pelo wrapper `../../scripts/terraform_workload.sh`, sem caminho de state versionado e sem state dentro do repositório.
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
python3 scripts/check_workload_state_policy.py
python3 scripts/check_runtime_bootstrap.py
```

Esses comandos não exigem credenciais reais e não executam `terraform plan`.

## Plan Real Auditado

Para o primeiro plan real da fase 10B, foram usados arquivos locais ignorados pelo Git:

- `infrastructure/terraform/terraform.tfvars`
- `deploy/oci/runtime.env`

Fluxo usado:

```bash
source "$HOME/.config/edudocs/oci.env"
make oci-readiness
terraform -chdir=infrastructure/terraform plan -input=false -out=/tmp/edudocs-oci.tfplan
terraform -chdir=infrastructure/terraform show -json /tmp/edudocs-oci.tfplan > /tmp/edudocs-oci.tfplan.json
make terraform-plan-check TERRAFORM_PLAN_JSON=/tmp/edudocs-oci.tfplan.json
```

O plan foi auditado sem `apply` e sem versionar tfvars, state ou plan. Consulte [Auditoria do plan OCI](../../docs/oci-plan-audit.md).

Na Entrega 10C, após a criação aprovada do compartment por bootstrap, este plan foi regenerado com `compartment_ocid` apontando para `edudocs-ai-prod`. O workload principal continua sem `apply` nesta etapa.

## Variáveis

Use `terraform.tfvars.example` como referência e crie um `terraform.tfvars` local fora do Git quando for validar contra uma tenancy real.

Valores sem default por segurança:

- `tenancy_ocid`
- `compartment_ocid`
- `region`
- `ssh_public_key_path`
- `admin_cidr`
- `api_image_ref`
- `web_image_ref`

`compartment_ocid` aceita somente OCID de compartment filho dedicado. O check `dedicated_workload_compartment` bloqueia `compartment_ocid == tenancy_ocid` e mantém `environment = "production"` no workload.

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
- `nginx_image_ref = "nginxinc/nginx-unprivileged:1.27.4-alpine"`
- `deploy_application = true`
- `application_host_port = 8080`
- `application_container_port = 8080`
- `application_health_path = "/health"`
- `application_root_dir = "/opt/edudocs"`
- `application_start_timeout_seconds = 600`
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

O template `../cloud-init/app-server.yaml.tftpl` prepara a VM de forma idempotente e usa templates auxiliares em `infrastructure/cloud-init`:

- Instala Docker Engine e Docker Compose plugin via repositório apt oficial.
- Habilita e inicia Docker.
- Escreve `/opt/edudocs/docker-compose.yml`, `/opt/edudocs/nginx.conf` e `/opt/edudocs/runtime.env`.
- Mantém `runtime.env` com permissão `0600` e apenas valores não secretos: refs de imagem, `FakeProvider` e porta Nginx.
- Cria a unidade `edudocs-compose.service`, executa `docker compose config`, faz pull anônimo das imagens por digest e inicia a stack.
- Publica somente o Nginx local em `8080`; API `8000` e web `3000` ficam na rede interna do Compose.
- Aguarda `http://127.0.0.1:8080/health`.
- Escreve `/var/lib/edudocs/application-ready`.
- Escreve `/var/lib/edudocs/cloud-init-complete`.
- Registra logs em `/var/log/edudocs-cloud-init.log`.

Os templates não fazem `docker login`, não clonam GitHub, não criam `.env`, não injetam chave Groq, não usam `latest`, não usam provisioners Terraform e não configuram HTTPS.

## Bucket Opcional

`create_backup_bucket` fica `false` por padrão. Quando habilitado, o bucket é privado, usa storage tier `Standard` e não cria objetos, PARs, policies públicas, replicação ou regras destrutivas.

## State

Este repositório não versiona `terraform.tfvars`, `tfstate` ou planos. O lockfile `.terraform.lock.hcl` é versionado para fixar o provedor.

Para uso real, confirme a estratégia de state antes de qualquer novo `terraform plan` real e antes de qualquer `apply`. A pilha bootstrap do compartment usa state separado em `$HOME/.local/state/edudocs/compartment/terraform.tfstate`.

O workload principal usa backend `local` sem caminho versionado. O caminho real é injetado pelo wrapper:

```bash
scripts/terraform_workload.sh init
scripts/terraform_workload.sh validate
scripts/terraform_workload.sh state-list
```

Locais externos padrão:

- State: `$HOME/.local/state/edudocs/workload/terraform.tfstate`
- `TF_DATA_DIR`: `$HOME/.local/share/edudocs/terraform-workload`

O apply do workload deve usar somente `scripts/terraform_workload.sh apply-saved-plan` com plan salvo em `/tmp`, permissão `600`, auditoria aprovada e confirmação humana literal.
