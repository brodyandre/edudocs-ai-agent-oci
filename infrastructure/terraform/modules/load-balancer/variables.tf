variable "compartment_ocid" {
  description = "OCID do compartment."
  type        = string
}

variable "name_prefix" {
  description = "Prefixo de nomes do Load Balancer."
  type        = string
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
  description = "Bandwidth minimo em Mbps. Always Free alvo: 10."
  type        = number
}

variable "maximum_bandwidth_in_mbps" {
  description = "Bandwidth maximo em Mbps. Always Free alvo: 10."
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
