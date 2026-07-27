# Bootstrap Do Compartment OCI

Este documento registra a pilha Terraform independente que prepara o compartment dedicado do EduDocs AI.

## Objetivo

A pilha em `infrastructure/terraform-bootstrap/compartment` deve criar exatamente um compartment filho da tenancy:

- Nome: `edudocs-ai-prod`
- Parent: tenancy validada no perfil OCI local
- Finalidade: hospedar o workload de produção do EduDocs AI
- State local real: `$HOME/.local/state/edudocs/compartment/terraform.tfstate`

Ela não cria VCN, subnet, Compute, Load Balancer, bucket, IAM policy, group, user, quota ou qualquer recurso de workload.

## Estado Preparatório

O código pode ser formatado, inicializado com `-backend=false`, validado e auditado no CI sem credenciais reais. Antes de qualquer mutação na OCI, o commit do código bootstrap deve estar em `main`, enviado para o GitHub e com o workflow `Quality` verde.

O `terraform.tfvars` real desta pilha é local, ignorado pelo Git e deve permanecer com permissão restrita. O arquivo versionado `terraform.tfvars.example` contém apenas placeholders.

## Fluxo Permitido

1. Validar código e política offline:

```bash
make compartment-bootstrap-check
```

2. Inicializar manualmente com backend local fora do repositório:

```bash
terraform -chdir=infrastructure/terraform-bootstrap/compartment init \
  -reconfigure \
  -backend-config="path=$HOME/.local/state/edudocs/compartment/terraform.tfstate"
```

3. Gerar plan salvo para arquivo local protegido.
4. Converter o plan para JSON e auditar:

```bash
make compartment-bootstrap-plan-check \
  COMPARTMENT_PLAN_JSON=/tmp/edudocs-compartment.tfplan.json \
  COMPARTMENT_TFVARS=infrastructure/terraform-bootstrap/compartment/terraform.tfvars
```

5. Aplicar somente o plan salvo e aprovado da pilha bootstrap.
6. Aguardar o compartment ficar `ACTIVE`.
7. Atualizar o `terraform.tfvars` local do workload principal para usar o OCID do compartment filho.
8. Gerar e auditar novo plan do workload principal sem executar `apply`.

## Guardrails

- `enable_delete = false`.
- `prevent_destroy = true`.
- `compartment_ocid` do workload principal não pode ser igual ao `tenancy_ocid`.
- O workflow de CI não recebe credenciais OCI e não executa `terraform plan`, `apply` ou `destroy`.
- Plan, state, tfvars real e outputs sensíveis não devem ser versionados.

## Relação Com O Workload Principal

O stack principal em `infrastructure/terraform` consome o compartment já existente. Ele cria os recursos de rede, Compute, Load Balancer e Object Storage opcional somente após um plan próprio, revisado e aprovado em etapa futura.

Na Entrega 10C, o apply permitido é restrito ao bootstrap do compartment. O apply do workload principal permanece proibido.
