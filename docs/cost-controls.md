# Controles De Custo

O Terraform foi ajustado para um deploy temporário PAYG mínimo e explícito em E4 Flex. Limites, disponibilidade e custo dependem da tenancy, região, capacidade E4 e políticas da OCI.

## Controles Aplicados

- Shape travado em `VM.Standard.E4.Flex`.
- Workload restrito ao compartment filho dedicado `edudocs-ai-prod`; root/tenancy não é alvo permitido.
- Default de 1 OCPU.
- Default de 8 GB de memória.
- Boot volume travado em 50 GB.
- Um único OCI Flexible Load Balancer.
- Shape do Load Balancer travado em `flexible`.
- Bandwidth mínimo do Load Balancer travado em 10 Mbps.
- Bandwidth máximo do Load Balancer travado em 10 Mbps.
- Sem Network Load Balancer.
- Sem WAF.
- Sem Reserved Public IP.
- Sem múltiplos listeners desnecessários.
- Sem múltiplos backends.
- Sem certificados nesta fase.
- Sem NAT Gateway.
- Sem OKE.
- Sem banco gerenciado.
- Sem GPU.
- Bucket de backup desabilitado por padrão.
- Bucket opcional sempre privado.
- Sem lifecycle destrutivo automático em Object Storage.
- Publicação no GHCR não altera a configuração de custo OCI.
- Sem registry privado que exija credencial na VM.
- Sem artefato adicional obrigatório na OCI.
- Sem Object Storage obrigatório para a aplicação.

## Pontos Que Exigem Confirmação Manual

Antes de qualquer `apply`:

- Verifique se a home region é a região pretendida.
- Verifique se `edudocs-ai-prod` existe, está `ACTIVE` e é filho direto da tenancy.
- Verifique se a capacidade E4 Flex 1/8 está disponível.
- Verifique se PAYG e orçamento estão ativos.
- Verifique se a tenancy aceita OCI Flexible Load Balancer 10/10 Mbps antes de qualquer apply.
- Verifique limites e cotas do compartment.
- Verifique se o boot volume proposto cabe no orçamento.
- Verifique se o bucket opcional é necessário.
- Revise tags e ownership dos recursos.
- Verifique se as imagens GHCR estão públicas antes de depender de pull anônimo na VM.

## Política No Repositório

O script `scripts/check_terraform_policy.py` bloqueia padrões de risco como:

- `terraform apply` ou `terraform destroy` em workflow.
- Uso de `-auto-approve`.
- Shape diferente de E4 Flex.
- CPU ou memória acima dos limites conservadores.
- SSH público para `0.0.0.0/0`.
- Portas públicas de desenvolvimento.
- Network Load Balancer, WAF, Reserved IP, NAT Gateway, OKE, banco ou GPU.
- Mais de um Load Balancer.
- Flexible Load Balancer acima de 10 Mbps.
- Listener diferente de HTTP 80 ou backend diferente de 8080.
- HTTP/HTTPS público direto na VM.
- Bucket público.
- Segredos evidentes em Terraform ou cloud-init.
- Versionamento de tfvars reais, state ou planos.
- Uso da tenancy/root como `compartment_ocid` do workload.
- Apply do workload fora de saved plan aprovado.

## Estado E Planos

O primeiro `terraform plan` real anterior foi salvo fora do Git e auditado por `scripts/check_terraform_plan.py`. A Entrega 11H substitui o perfil ativo para E4 Flex PAYG 1/8/50; um novo plan real desse perfil ainda deve ser gerado e auditado antes de qualquer `apply`.

Na Entrega 10C, a criação do compartment ficou isolada em `infrastructure/terraform-bootstrap/compartment` e gerou exatamente um recurso `oci_identity_compartment`. O novo plan do workload apontou todos os recursos para o compartment filho dedicado e não foi aplicado nessa etapa.

Na preparação da Entrega 11, o workload ganhou backend local explícito sem caminho versionado, wrapper para state principal externo e política de apply somente por saved plan. O apply real continua condicionado à revisão de capacidade E4 Flex 1/8, orçamento PAYG, elegibilidade do Load Balancer 10/10 Mbps, state vazio e confirmação humana literal.

Arquivos `terraform.tfvars`, `*.tfstate`, `*.tfplan` e `tfplan` não devem ser versionados. O arquivo `.terraform.lock.hcl` deve ser versionado para fixar o provedor validado.
