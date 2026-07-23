output "instance_id" {
  description = "OCID da instancia."
  value       = oci_core_instance.app.id
}

output "display_name" {
  description = "Nome exibido da instancia."
  value       = oci_core_instance.app.display_name
}

output "public_ip" {
  description = "IP publico efemero da instancia."
  value       = oci_core_instance.app.public_ip
}

output "ssh_connection_hint" {
  description = "Comando SSH sugerido apos apply real."
  value       = "ssh ubuntu@${oci_core_instance.app.public_ip}"
}
