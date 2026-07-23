output "load_balancer_id" {
  description = "OCID do Load Balancer."
  value       = oci_load_balancer_load_balancer.this.id
}

output "load_balancer_public_ip" {
  description = "IP publico atribuido pela OCI ao Load Balancer apos apply real."
  value       = try(oci_load_balancer_load_balancer.this.ip_addresses[0], null)
}

output "load_balancer_url" {
  description = "URL HTTP futura do Load Balancer apos apply real."
  value       = try("http://${oci_load_balancer_load_balancer.this.ip_addresses[0]}", null)
}

output "load_balancer_health_url" {
  description = "URL futura do health endpoint via Load Balancer apos apply real."
  value       = try("http://${oci_load_balancer_load_balancer.this.ip_addresses[0]}/health", null)
}

output "backend_set_name" {
  description = "Nome do backend set do Load Balancer."
  value       = oci_load_balancer_backend_set.app.name
}

output "listener_name" {
  description = "Nome do listener HTTP do Load Balancer."
  value       = oci_load_balancer_listener.http.name
}
