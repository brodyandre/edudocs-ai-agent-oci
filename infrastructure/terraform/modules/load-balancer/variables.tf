variable "compartment_ocid" {
  description = "OCID do compartment."
  type        = string
}

variable "name_prefix" {
  description = "Prefixo de nomes do Load Balancer."
  type        = string
}

variable "backend_set_name" {
  description = "Nome imutavel do backend set do Load Balancer."
  type        = string

  validation {
    condition = (
      var.backend_set_name == "edudocs-ai-prod-backend-set"
      && length(var.backend_set_name) >= 1
      && length(var.backend_set_name) <= 32
      && !can(regex("\\s", var.backend_set_name))
      && can(regex("^[A-Za-z0-9_-]+$", var.backend_set_name))
    )
    error_message = "backend_set_name deve ser edudocs-ai-prod-backend-set, com 1 a 32 caracteres validos e sem espacos."
  }
}

variable "public_subnet_id" {
  description = "OCID da subnet publica regional usada pelo Load Balancer."
  type        = string
}

variable "load_balancer_nsg_id" {
  description = "OCID do NSG exclusivo do Load Balancer."
  type        = string
}

variable "app_nsg_id" {
  description = "OCID do NSG da aplicacao, usado para garantir separacao entre NSGs."
  type        = string
}

variable "backend_private_ip" {
  description = "IP privado da VM backend."
  type        = string
}

variable "load_balancer_shape" {
  description = "Shape do OCI Flexible Load Balancer."
  type        = string
}

variable "minimum_bandwidth_in_mbps" {
  description = "Bandwidth minimo em Mbps. Perfil minimo aprovado: 10."
  type        = number
}

variable "maximum_bandwidth_in_mbps" {
  description = "Bandwidth maximo em Mbps. Perfil minimo aprovado: 10."
  type        = number
}

variable "listener_port" {
  description = "Porta publica HTTP do listener."
  type        = number
}

variable "backend_port" {
  description = "Porta privada do backend Nginx na VM."
  type        = number
}

variable "health_path" {
  description = "Caminho HTTP usado pelo health checker."
  type        = string
}

variable "freeform_tags" {
  description = "Tags livres aplicadas aos recursos."
  type        = map(string)
  default     = {}
}
