# Runbook De Apply Do Workload OCI

Este runbook descreve o fluxo controlado para aplicar o workload principal do EduDocs AI na OCI.

## Estado Atual

O compartment dedicado `edudocs-ai-prod` já existe e permanece gerenciado por uma pilha separada em `infrastructure/terraform-bootstrap/compartment`.

O primeiro `apply-saved-plan` PAYG do workload principal foi executado uma única vez e falhou parcialmente durante a criação do backend set do Load Balancer. O state principal foi preservado, o state do compartment permaneceu separado e não houve segundo apply automático, destroy, import, alteração manual de state ou criação manual pela OCI.

Recursos parciais do workload ficaram ativos na OCI, incluindo a VM `VM.Standard.E4.Flex` 1/8 e o Load Balancer flex 10/10. A recuperação exige código corrigido, novo plan salvo baseado no state parcial real, auditoria em modo recovery e novo checkpoint humano antes de qualquer apply de recuperação.

## State Principal

O state do workload principal deve ficar fora do repositório:

- Diretório: `$HOME/.local/state/edudocs/workload`
- Arquivo: `$HOME/.local/state/edudocs/workload/terraform.tfstate`
- Permissão do diretório: `700`
- Permissão do state após criação: `600`

O diretório de dados do Terraform também fica fora do repositório:

- `TF_DATA_DIR=$HOME/.local/share/edudocs/terraform-workload`

O state do compartment continua separado:

- `$HOME/.local/state/edudocs/compartment/terraform.tfstate`

## Wrapper Obrigatório

Use `scripts/terraform_workload.sh` para o stack principal. Ele configura backend local externo, `TF_DATA_DIR` externo, permissões restritas e recusa state dentro do repositório.

Comandos permitidos:

- `init`
- `validate`
- `state-list`
- `plan`
- `show-json`
- `show-text`
- `apply-saved-plan`
- `output-json`
- `post-apply-plan`

Comandos destrutivos ou mutações de state não são parte deste runbook.

## Plan Salvo

O apply do workload exige:

- planfile explícito;
- planfile em `/tmp`;
- permissão `600`;
- auditoria JSON aprovada;
- revisão humana do texto do plan;
- confirmação humana literal antes do apply.

Não use `-auto-approve`, `-target`, `refresh=false`, pipe de `yes` ou apply sem plan salvo.

## Confirmação Humana

Antes do apply, apresente um resumo sanitizado e solicite exatamente:

```text
Digite APLICAR PLANO OCI 11 para autorizar o apply do saved plan aprovado.
```

Qualquer outra resposta deve interromper o apply.

## Política De Falhas

Em caso de falha:

- preserve o state principal;
- preserve o state do compartment;
- não execute `destroy`;
- não execute novo apply automaticamente;
- não execute `import`;
- não altere state manualmente;
- não faça fallback para recurso pago;
- não altere shape, memória ou bandwidth para contornar capacidade.

Quando houver recurso parcial, a recuperação deve ser planejada em outra entrega.

## Recuperação Do Apply Parcial PAYG

Causa confirmada da falha parcial:

- Recurso: `oci_load_balancer_backend_set`.
- Nome recusado: `edudocs-ai-production-backend-set`.
- Comprimento: 33 caracteres.
- Limite da OCI: máximo de 32 caracteres.

Correção adotada:

- Nome aprovado: `edudocs-ai-prod-backend-set`.
- Comprimento: 27 caracteres.
- Charset: letras, números, `_` e `-`, sem espaços.
- Origem: local explícito do root module passado ao módulo de Load Balancer.
- Guardrails: validação Terraform no root, validação da variável do módulo e auditoria de plan em modo `partial-apply-recovery`.

A recuperação não deve recriar VM, Load Balancer principal, VCN, subnet, Internet Gateway, NSGs, shape, CPU, memória, boot volume, bandwidth ou compartment. O novo plan de recuperação deve conter somente creates dos recursos do Load Balancer que estiverem ausentes no state real.

## Runtime Inicial

A aplicação deve iniciar com providers falsos:

- `EDUDOCS_LLM_PROVIDER=fake`
- `EDUDOCS_EMBEDDING_PROVIDER=fake`

Groq real, domínio próprio, HTTPS, certificados, redirect HTTP para HTTPS, observabilidade avançada, backend remoto de state e pipeline automático de deploy permanecem pendentes.
