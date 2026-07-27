# Auditoria Do Plan OCI

Data da auditoria: 2026-07-27.

## Escopo

A Entrega 10C separou o bootstrap do compartment dedicado do workload principal.

Foi aplicado somente o plan salvo da pilha `infrastructure/terraform-bootstrap/compartment`, depois do commit `f4ac0b1` e CI verde. Esse apply criou exatamente o compartment filho `edudocs-ai-prod`.

O workload principal em `infrastructure/terraform` teve um novo `terraform plan` real gerado e auditado em JSON, mas não houve `apply`, `destroy`, import, alteração de state do workload ou deploy da aplicação.

Arquivos locais usados e ignorados pelo Git:

- `infrastructure/terraform-bootstrap/compartment/terraform.tfvars`
- `infrastructure/terraform/terraform.tfvars`
- `deploy/oci/runtime.env`
- `/tmp/edudocs-compartment-20260727151440.tfplan`
- `/tmp/edudocs-compartment-20260727151440.tfplan.json`
- `/tmp/edudocs-oci-dedicated-20260727151750.tfplan`
- `/tmp/edudocs-oci-dedicated-20260727151750.tfplan.json`

## Bootstrap Do Compartment

Resultado aprovado:

- Stack: `infrastructure/terraform-bootstrap/compartment`.
- Commit do código bootstrap: `f4ac0b1`.
- Recurso criado: `oci_identity_compartment.edudocs`.
- Nome do compartment: `edudocs-ai-prod`.
- Parent: tenancy validada, sem expor OCID.
- Estado OCI após criação: `ACTIVE`.
- OCID: mantido sensível e mascarado nas saídas.
- State: `$HOME/.local/state/edudocs/compartment/terraform.tfstate`, fora do repositório e com permissão `600`.
- Apply executado: somente do plan salvo do bootstrap.
- Workload no apply bootstrap: nenhum.
- IAM policy, group, user, quota, VCN, subnet, Compute, Load Balancer e bucket no bootstrap: nenhum.

Auditoria do plan bootstrap:

```bash
make compartment-bootstrap-plan-check \
  COMPARTMENT_PLAN_JSON=/tmp/edudocs-compartment-20260727151440.tfplan.json \
  COMPARTMENT_TFVARS=infrastructure/terraform-bootstrap/compartment/terraform.tfvars
```

Resultado:

| Ação | Quantidade |
| --- | ---: |
| create | 1 |
| update | 0 |
| replace | 0 |
| delete | 0 |

## Readiness OCI

- OCI CLI: validado localmente.
- Perfil: `EDUDOCS`.
- Home region: `sa-saopaulo-1`.
- Região assinada: `READY`.
- Availability domain: `SA-SAOPAULO-1-AD-1`.
- Compartment alvo: `edudocs-ai-prod`.
- Compartment alvo: `ACTIVE`, filho direto da tenancy.
- Root compartment como alvo do workload: proibido.
- CIDR administrativo: IPv4 público em `/32`, mantido mascarado.
- Chave SSH da VM: `~/.ssh/edudocs_oci_ed25519.pub`.
- Imagens GHCR: referências imutáveis por digest, validadas pelo manifesto de release.

## Resultado Do Plan Do Workload

O novo plan do workload foi auditado com:

```bash
make terraform-plan-check \
  TERRAFORM_PLAN_JSON=/tmp/edudocs-oci-dedicated-20260727151750.tfplan.json \
  TERRAFORM_TFVARS=infrastructure/terraform/terraform.tfvars
```

Resultado: aprovado.

Resumo:

- Recursos gerenciados: 16.
- Ações: 16 creates.
- Root compartment hits: 0.
- Recursos de identity, quota ou compartment no workload: 0.
- Apply do workload: não executado.

Recursos planejados para criação:

| Tipo | Quantidade |
| --- | ---: |
| `oci_core_instance` | 1 |
| `oci_core_internet_gateway` | 1 |
| `oci_core_network_security_group` | 2 |
| `oci_core_network_security_group_security_rule` | 5 |
| `oci_core_route_table` | 1 |
| `oci_core_subnet` | 1 |
| `oci_core_vcn` | 1 |
| `oci_load_balancer_backend` | 1 |
| `oci_load_balancer_backend_set` | 1 |
| `oci_load_balancer_listener` | 1 |
| `oci_load_balancer_load_balancer` | 1 |

## Verificações De Política

- Sem `delete`, `replace` ou `update` de recursos existentes no workload.
- Sem `terraform apply` no workload.
- Sem `terraform destroy`.
- Sem `-auto-approve`.
- Sem `-target`.
- Sem NAT Gateway.
- Sem WAF.
- Sem OKE.
- Sem banco gerenciado.
- Sem GPU.
- Sem Reserved Public IP.
- Sem Network Load Balancer.
- Sem bucket criado por padrão.
- Compute limitado a `VM.Standard.A1.Flex`.
- Compute: 2 OCPUs e 12 GB de memória.
- Boot volume: 50 GB.
- Load Balancer `flexible` com 10 Mbps mínimo e 10 Mbps máximo.
- Listener público somente HTTP 80 no Load Balancer.
- Backend privado esperado na porta 8080.
- Health checker HTTP 8080 em `/health`.
- Portas 3000, 8000 e 8080 não expostas publicamente.
- SSH restrito ao CIDR administrativo em `/32`.
- Bootstrap sem `docker login`, sem clone de repositório, sem `latest` e sem segredo de LLM.
- Plan JSON sem marcadores de segredo.

## Estado Após Auditoria

O compartment dedicado `edudocs-ai-prod` foi criado e validado como `ACTIVE`.

Nenhum recurso do workload principal foi criado. O próximo passo permitido em etapa futura é revisar novamente capacidade A1, elegibilidade Always Free do Load Balancer, state do workload e o plan salvo antes de qualquer `terraform apply` do workload.
