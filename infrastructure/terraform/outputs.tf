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
