terraform {
  required_providers {
    oci = {
      source = "oracle/oci"
    }
  }
}

locals {
  hostname_label = replace(var.name_prefix, "-", "")
}

resource "oci_core_instance" "app" {
  availability_domain = var.availability_domain
  compartment_id      = var.compartment_ocid
  shape               = var.compute_shape
  display_name        = "${var.name_prefix}-app"
  freeform_tags       = var.freeform_tags

  shape_config {
    ocpus         = var.compute_ocpus
    memory_in_gbs = var.compute_memory_gbs
  }

  source_details {
    source_type             = "image"
    source_id               = var.image_ocid
    boot_volume_size_in_gbs = var.boot_volume_size_gbs
  }

  create_vnic_details {
    assign_public_ip = true
    subnet_id        = var.public_subnet_id
    hostname_label   = substr(local.hostname_label, 0, 15)
    nsg_ids          = var.nsg_ids
    display_name     = "${var.name_prefix}-app-vnic"
  }

  metadata = {
    ssh_authorized_keys = file(pathexpand(var.ssh_public_key_path))
    user_data = base64encode(templatefile(var.cloud_init_template_path, {
      project_name = var.name_prefix
    }))
  }

  lifecycle {
    precondition {
      condition     = var.compute_shape == "VM.Standard.A1.Flex"
      error_message = "A instancia deve usar VM.Standard.A1.Flex."
    }

    precondition {
      condition     = var.compute_ocpus > 0 && var.compute_ocpus <= 2
      error_message = "compute_ocpus deve ficar entre 0 e 2."
    }

    precondition {
      condition     = var.compute_memory_gbs > 0 && var.compute_memory_gbs <= 12
      error_message = "compute_memory_gbs deve ficar entre 0 e 12."
    }

    precondition {
      condition     = var.boot_volume_size_gbs >= 50 && var.boot_volume_size_gbs <= 100
      error_message = "boot_volume_size_gbs deve ficar entre 50 e 100."
    }

    precondition {
      condition     = var.admin_cidr != "0.0.0.0/0"
      error_message = "admin_cidr nao pode ser 0.0.0.0/0."
    }
  }
}
