locals {
  required_tags = {
    Project     = "EduDocs-AI"
    Environment = "production"
    ManagedBy   = "Terraform"
    Purpose     = "Application-Workload"
    CostProfile = "Always-Free-Target"
  }

  common_tags = merge(local.required_tags, var.common_tags)
}

resource "oci_identity_compartment" "edudocs" {
  compartment_id = var.tenancy_ocid
  name           = var.compartment_name
  description    = var.compartment_description
  enable_delete  = false
  freeform_tags  = local.common_tags

  lifecycle {
    prevent_destroy = true
  }
}
