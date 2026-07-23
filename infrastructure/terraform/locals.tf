locals {
  name_prefix = "${var.project_name}-${var.environment}"

  common_tags = merge(
    {
      Project     = "EduDocs-AI"
      Environment = var.environment
      ManagedBy   = "Terraform"
      CostProfile = "Always-Free-Target"
    },
    var.common_tags,
  )

  selected_availability_domain = coalesce(
    var.availability_domain,
    try(data.oci_identity_availability_domains.available.availability_domains[0].name, null),
  )

  selected_image_ocid = coalesce(
    var.image_ocid,
    try(data.oci_core_images.ubuntu.images[0].id, null),
  )
}
