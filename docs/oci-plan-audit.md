# Auditoria Do Plan OCI

Data da auditoria: 2026-07-27.

## Escopo

Foi executado o primeiro `terraform plan` real da infraestrutura OCI, sem `apply`, sem `destroy`, sem import, sem alteração de state remoto e sem versionar arquivos locais.

Arquivos locais usados e ignorados pelo Git:

- `infrastructure/terraform/terraform.tfvars`
- `deploy/oci/runtime.env`
- `/tmp/edudocs-oci.tfplan`
- `/tmp/edudocs-oci.tfplan.json`

## Readiness OCI

- OCI CLI: validado localmente.
- Perfil: `EDUDOCS`.
- Home region: `sa-saopaulo-1`.
- Região assinada: `READY`.
- Availability domain: `SA-SAOPAULO-1-AD-1`.
- Compartment alvo: root compartment da tenancy, pois não foram retornados compartments filhos ativos.
- CIDR administrativo: IPv4 público em `/32`, mantido mascarado.
- Chave SSH da VM: `~/.ssh/edudocs_oci_ed25519.pub`.
- Imagens GHCR: referências imutáveis por digest, validadas pelo manifesto de release.

## Resultado Do Plan

O plan foi auditado com:

```bash
make terraform-plan-check TERRAFORM_PLAN_JSON=/tmp/edudocs-oci.tfplan.json
```

Resultado: aprovado.

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

- Sem `delete`, `replace` ou `update` de recursos existentes.
- Sem `terraform apply`.
- Sem `terraform destroy`.
- Sem `-auto-approve`.
- Sem NAT Gateway.
- Sem WAF.
- Sem OKE.
- Sem banco gerenciado.
- Sem GPU.
- Sem Reserved Public IP.
- Sem Network Load Balancer.
- Sem bucket criado por padrão.
- Compute limitado a `VM.Standard.A1.Flex`.
- Load Balancer `flexible` com 10 Mbps mínimo e 10 Mbps máximo.
- Listener público somente HTTP 80 no Load Balancer.
- Backend privado esperado na porta 8080.
- Portas 3000, 8000 e 8080 não expostas publicamente.
- SSH restrito ao CIDR administrativo em `/32`.
- Bootstrap sem `docker login`, sem clone de repositório, sem `latest` e sem segredo de LLM.

## Estado Após Auditoria

Nenhum recurso OCI foi criado nesta etapa. O próximo passo permitido é revisar capacidade A1, elegibilidade Always Free do Load Balancer, estratégia de state e então decidir explicitamente sobre um `terraform apply` futuro.
