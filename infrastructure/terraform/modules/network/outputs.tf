output "vcn_id" {
  description = "OCID da VCN."
  value       = oci_core_vcn.this.id
}

output "public_subnet_id" {
  description = "OCID da subnet publica."
  value       = oci_core_subnet.public.id
}

output "nsg_id" {
  description = "OCID do NSG da aplicacao."
  value       = oci_core_network_security_group.app.id
}
