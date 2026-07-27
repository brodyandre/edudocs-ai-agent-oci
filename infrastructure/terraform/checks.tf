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
