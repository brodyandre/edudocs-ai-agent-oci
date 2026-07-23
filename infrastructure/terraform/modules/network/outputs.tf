output "vcn_id" {
  description = "OCID da VCN."
  value       = oci_core_vcn.this.id
}

output "public_subnet_id" {
  description = "OCID da subnet publica."
  value       = oci_core_subnet.public.id
}

output "app_nsg_id" {
  description = "OCID do NSG da aplicacao."
  value       = oci_core_network_security_group.app.id
}

output "load_balancer_nsg_id" {
  description = "OCID do NSG do Load Balancer."
  value       = oci_core_network_security_group.load_balancer.id
}

output "nsg_id" {
  description = "OCID do NSG da aplicacao, mantido por compatibilidade."
  value       = oci_core_network_security_group.app.id
}
