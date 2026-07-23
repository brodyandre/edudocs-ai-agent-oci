# Controles De Custo

O Terraform foi desenhado para mirar um perfil Always Free conservador, sem prometer gratuidade real. Limites e disponibilidade dependem da tenancy, região, disponibilidade A1 e políticas da OCI.

## Controles Aplicados

- Shape travado em `VM.Standard.A1.Flex`.
- Default de 2 OCPUs.
- Default de 12 GB de memória.
- Boot volume default de 50 GB, com validação até 100 GB.
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

## Pontos Que Exigem Confirmação Manual

Antes de qualquer `plan` real:

- Verifique se a home region é a região pretendida.
- Verifique se a capacidade A1 está disponível.
- Verifique se a tenancy aceita OCI Flexible Load Balancer 10/10 Mbps antes de qualquer apply.
- Verifique limites e cotas do compartment.
- Verifique se o boot volume proposto cabe no orçamento.
- Verifique se o bucket opcional é necessário.
- Revise tags e ownership dos recursos.

## Política No Repositório

O script `scripts/check_terraform_policy.py` bloqueia padrões de risco como:

- `terraform apply` ou `terraform destroy` em workflow.
- Uso de `-auto-approve`.
- Shape diferente de A1 Flex.
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

## Estado E Planos

Arquivos `terraform.tfvars`, `*.tfstate`, `*.tfplan` e `tfplan` não devem ser versionados. O arquivo `.terraform.lock.hcl` deve ser versionado para fixar o provedor validado.
