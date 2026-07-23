output "vcn_id" {
  description = "OCID da VCN."
  value       = module.network.vcn_id
}

output "public_subnet_id" {
  description = "OCID da subnet publica."
  value       = module.network.public_subnet_id
}

output "nsg_id" {
  description = "OCID do NSG da aplicacao."
  value       = module.network.nsg_id
}

output "app_nsg_id" {
  description = "OCID do NSG da aplicacao."
  value       = module.network.app_nsg_id
}

output "load_balancer_nsg_id" {
  description = "OCID do NSG do Load Balancer."
  value       = module.network.load_balancer_nsg_id
}

output "instance_id" {
  description = "OCID da instancia Compute."
  value       = module.compute.instance_id
}

output "display_name" {
  description = "Nome exibido da instancia Compute."
  value       = module.compute.display_name
}

output "public_ip" {
  description = "IP publico efemero da instancia Compute."
  value       = module.compute.public_ip
}

output "private_ip" {
  description = "IP privado da instancia Compute usado pelo backend do Load Balancer."
  value       = module.compute.private_ip
}

output "load_balancer_id" {
  description = "OCID do Load Balancer."
  value       = module.load_balancer.load_balancer_id
}

output "load_balancer_public_ip" {
  description = "IP publico do Load Balancer, conhecido apos apply real."
  value       = module.load_balancer.load_balancer_public_ip
}

output "load_balancer_url" {
  description = "URL HTTP futura do Load Balancer, conhecida apos apply real."
  value       = module.load_balancer.load_balancer_url
}

output "load_balancer_health_url" {
  description = "URL futura do health endpoint via Load Balancer, conhecida apos apply real."
  value       = module.load_balancer.load_balancer_health_url
}

output "load_balancer_backend_set_name" {
  description = "Nome do backend set do Load Balancer."
  value       = module.load_balancer.backend_set_name
}

output "load_balancer_listener_name" {
  description = "Nome do listener HTTP do Load Balancer."
  value       = module.load_balancer.listener_name
}

output "selected_availability_domain" {
  description = "Availability domain selecionado para a instancia."
  value       = local.selected_availability_domain
}

output "selected_image_ocid" {
  description = "OCID da imagem selecionada para a instancia."
  value       = local.selected_image_ocid
}

output "ssh_connection_hint" {
  description = "Comando SSH sugerido depois de um apply real."
  value       = module.compute.ssh_connection_hint
}

output "backup_bucket_name" {
  description = "Nome do bucket privado opcional, ou null quando desabilitado."
  value       = module.object_storage.backup_bucket_name
}
