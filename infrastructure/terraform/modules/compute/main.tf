terraform {
  required_providers {
    oci = {
      source = "oracle/oci"
    }
  }
}

locals {
  hostname_label       = replace(var.name_prefix, "-", "")
  cloud_init_templates = dirname(var.cloud_init_template_path)
  application_root_dir = trimsuffix(var.application_root_dir, "/")
  compose_content = templatefile("${local.cloud_init_templates}/docker-compose.prod.yaml.tftpl", {
    nginx_image_ref            = var.nginx_image_ref
    application_container_port = var.application_container_port
    application_health_path    = var.application_health_path
  })
  nginx_content = templatefile("${local.cloud_init_templates}/nginx.conf.tftpl", {
    application_container_port = var.application_container_port
    application_health_path    = var.application_health_path
  })
  runtime_env_content = templatefile("${local.cloud_init_templates}/runtime.env.tftpl", {
    api_image_ref         = var.api_image_ref
    web_image_ref         = var.web_image_ref
    application_host_port = var.application_host_port
  })
  systemd_content = templatefile("${local.cloud_init_templates}/edudocs-compose.service.tftpl", {
    application_root_dir              = local.application_root_dir
    application_start_timeout_seconds = var.application_start_timeout_seconds
  })
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
      project_name                      = var.name_prefix
      admin_cidr                        = var.admin_cidr
      public_subnet_cidr                = var.public_subnet_cidr
      application_root_dir              = local.application_root_dir
      application_host_port             = var.application_host_port
      application_health_path           = var.application_health_path
      application_start_timeout_seconds = var.application_start_timeout_seconds
      compose_content                   = local.compose_content
      nginx_content                     = local.nginx_content
      runtime_env_content               = local.runtime_env_content
      systemd_content                   = local.systemd_content
    }))
  }

  lifecycle {
    precondition {
      condition     = var.compute_shape == "VM.Standard.E4.Flex"
      error_message = "A instancia deve usar VM.Standard.E4.Flex."
    }

    precondition {
      condition     = var.compute_ocpus == 1
      error_message = "compute_ocpus deve ser exatamente 1."
    }

    precondition {
      condition     = var.compute_memory_gbs == 8
      error_message = "compute_memory_gbs deve ser exatamente 8."
    }

    precondition {
      condition     = var.boot_volume_size_gbs == 50
      error_message = "boot_volume_size_gbs deve ser exatamente 50."
    }

    precondition {
      condition     = var.admin_cidr != "0.0.0.0/0"
      error_message = "admin_cidr nao pode ser 0.0.0.0/0."
    }

    precondition {
      condition     = var.deploy_application == true
      error_message = "deploy_application deve permanecer true nesta entrega."
    }

    precondition {
      condition     = can(regex("^ghcr\\.io/brodyandre/edudocs-ai-api@sha256:[0-9a-f]{64}$", var.api_image_ref))
      error_message = "api_image_ref deve ser uma referencia GHCR imutavel por digest."
    }

    precondition {
      condition     = can(regex("^ghcr\\.io/brodyandre/edudocs-ai-web@sha256:[0-9a-f]{64}$", var.web_image_ref))
      error_message = "web_image_ref deve ser uma referencia GHCR imutavel por digest."
    }

    precondition {
      condition     = var.application_host_port == 8080 && var.application_container_port == 8080
      error_message = "A aplicacao deve expor somente a porta 8080 para o backend do Load Balancer."
    }

    precondition {
      condition     = var.application_health_path == "/health"
      error_message = "application_health_path deve permanecer /health."
    }
  }
}
