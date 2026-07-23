terraform {
  required_providers {
    oci = {
      source = "oracle/oci"
    }
  }
}

data "oci_objectstorage_namespace" "this" {
  count = var.create_backup_bucket ? 1 : 0
}

resource "oci_objectstorage_bucket" "backup" {
  count = var.create_backup_bucket ? 1 : 0

  compartment_id = var.compartment_ocid
  namespace      = data.oci_objectstorage_namespace.this[0].namespace
  name           = var.backup_bucket_name
  access_type    = "NoPublicAccess"
  storage_tier   = "Standard"
  freeform_tags  = var.freeform_tags
}
