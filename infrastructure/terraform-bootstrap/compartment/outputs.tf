output "compartment_name" {
  description = "Nome publico do compartment dedicado."
  value       = oci_identity_compartment.edudocs.name
}

output "compartment_ocid" {
  description = "OCID do compartment dedicado. Mantido sensivel para evitar exposicao acidental."
  value       = oci_identity_compartment.edudocs.id
  sensitive   = true
}

output "compartment_lifecycle_state" {
  description = "Estado atual do compartment dedicado."
  value       = oci_identity_compartment.edudocs.state
}

output "parent_tenancy_reference" {
  description = "Confirma que o parent declarado e a tenancy, sem expor o OCID."
  value       = oci_identity_compartment.edudocs.compartment_id == var.tenancy_ocid
}
