check "dedicated_workload_compartment" {
  assert {
    condition = (
      var.compartment_ocid != var.tenancy_ocid
      && can(regex("^ocid1\\.compartment\\.oc1\\.", var.compartment_ocid))
      && var.environment == "production"
    )
    error_message = "O workload production deve usar um compartment filho dedicado, nunca o root compartment da tenancy."
  }
}

check "load_balancer_backend_set_name" {
  assert {
    condition = (
      local.load_balancer_backend_set_name == "edudocs-ai-prod-backend-set"
      && length(local.load_balancer_backend_set_name) >= 1
      && length(local.load_balancer_backend_set_name) <= 32
      && !can(regex("\\s", local.load_balancer_backend_set_name))
      && can(regex("^[A-Za-z0-9_-]+$", local.load_balancer_backend_set_name))
    )
    error_message = "O nome do backend set do Load Balancer deve ser edudocs-ai-prod-backend-set, com 1 a 32 caracteres validos e sem espacos."
  }
}
