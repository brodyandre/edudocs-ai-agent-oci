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

output "private_ip" {
  description = "IP privado da instancia usado pelo backend do Load Balancer."
  value       = oci_core_instance.app.private_ip
}

output "ssh_connection_hint" {
  description = "Comando SSH sugerido apos apply real."
  value       = "ssh ubuntu@${oci_core_instance.app.public_ip}"
}
