# Bootstrap Do Compartment OCI

Este stack cria exclusivamente o compartment filho dedicado `edudocs-ai-prod`.
Ele é separado do stack principal em `infrastructure/terraform` e não referencia
state remoto, `terraform_remote_state`, módulos remotos ou recursos do workload.

## Escopo

O stack declara exatamente um recurso:

- `oci_identity_compartment.edudocs`

O parent é a tenancy raiz, usada apenas como escopo de identidade. Nenhum recurso
de aplicação, rede, Compute, Load Balancer, policy, quota, usuário, grupo, bucket
ou VCN é criado por este stack.

## Proteções

- `enable_delete = false`
- `prevent_destroy = true`
- backend `local` com caminho configurado no `terraform init`
- state real fora do repositório
- outputs sem tenancy OCID
- `compartment_ocid` marcado como sensível

## State Externo

Use um caminho local protegido e fora do Git:

```bash
BOOTSTRAP_STATE_PATH="$HOME/.local/state/edudocs/compartment/terraform.tfstate"
terraform -chdir=infrastructure/terraform-bootstrap/compartment init \
  -reconfigure \
  -backend-config="path=$BOOTSTRAP_STATE_PATH"
```

Preserve esse state. Ele registra o único compartment criado e não deve ser
copiado para o repositório.

## Validação Sem OCI

```bash
make compartment-bootstrap-check
```

Esse alvo executa fmt, init sem backend real, validate, política estática e
testes offline. Ele não executa plan real, apply ou destroy.
