terraform {
  required_providers {
    oci = {
      source = "oracle/oci"
    }
  }
}

locals {
  backend_set_name = "${var.name_prefix}-backend-set"
  listener_name    = "${var.name_prefix}-http"
}

resource "oci_load_balancer_load_balancer" "this" {
  compartment_id             = var.compartment_ocid
  display_name               = "${var.name_prefix}-lb"
  shape                      = var.load_balancer_shape
  is_private                 = false
  subnet_ids                 = [var.public_subnet_id]
  network_security_group_ids = [var.load_balancer_nsg_id]
  is_request_id_enabled      = true
  request_id_header          = "X-Request-Id"
  freeform_tags              = var.freeform_tags

  shape_details {
    minimum_bandwidth_in_mbps = var.minimum_bandwidth_in_mbps
    maximum_bandwidth_in_mbps = var.maximum_bandwidth_in_mbps
  }

  lifecycle {
    precondition {
      condition     = var.load_balancer_shape == "flexible"
      error_message = "O Load Balancer deve usar shape flexible."
    }

    precondition {
      condition     = var.minimum_bandwidth_in_mbps == 10
      error_message = "O bandwidth minimo do Load Balancer deve ser exatamente 10 Mbps."
    }

    precondition {
      condition     = var.maximum_bandwidth_in_mbps == 10
      error_message = "O bandwidth maximo do Load Balancer deve ser exatamente 10 Mbps."
    }

    precondition {
      condition     = var.maximum_bandwidth_in_mbps <= 10
      error_message = "O Load Balancer nao pode exceder 10 Mbps nesta arquitetura."
    }

    precondition {
      condition     = var.load_balancer_nsg_id != var.app_nsg_id
      error_message = "O Load Balancer e a aplicacao devem usar NSGs separados."
    }
  }
}

resource "oci_load_balancer_backend_set" "app" {
  load_balancer_id = oci_load_balancer_load_balancer.this.id
  name             = local.backend_set_name
  policy           = "ROUND_ROBIN"

  health_checker {
    protocol          = "HTTP"
    port              = var.backend_port
    url_path          = var.health_path
    return_code       = 200
    interval_ms       = 10000
    timeout_in_millis = 3000
    retries           = 3
  }

  lifecycle {
    precondition {
      condition     = var.backend_port == 8080
      error_message = "O health checker deve consultar o backend na porta 8080."
    }

    precondition {
      condition     = var.health_path == "/health"
      error_message = "O health checker deve usar /health nesta entrega."
    }
  }
}

resource "oci_load_balancer_backend" "app" {
  load_balancer_id = oci_load_balancer_load_balancer.this.id
  backendset_name  = oci_load_balancer_backend_set.app.name
  ip_address       = var.backend_private_ip
  port             = var.backend_port
  weight           = 1
  backup           = false
  drain            = false
  offline          = false

  lifecycle {
    precondition {
      condition     = var.backend_port == 8080
      error_message = "O backend do Load Balancer deve usar a porta 8080."
    }

    precondition {
      condition = (
        can(regex("^(10\\.|172\\.(1[6-9]|2[0-9]|3[0-1])\\.|192\\.168\\.)", var.backend_private_ip))
        || var.backend_private_ip == ""
      )
      error_message = "O backend deve usar IP privado da VM."
    }
  }
}

resource "oci_load_balancer_listener" "http" {
  load_balancer_id         = oci_load_balancer_load_balancer.this.id
  name                     = local.listener_name
  default_backend_set_name = oci_load_balancer_backend_set.app.name
  protocol                 = "HTTP"
  port                     = var.listener_port

  lifecycle {
    precondition {
      condition     = var.listener_port == 80
      error_message = "O listener HTTP deve usar a porta 80 nesta entrega."
    }
  }
}
