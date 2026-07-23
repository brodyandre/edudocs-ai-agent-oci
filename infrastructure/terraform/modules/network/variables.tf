variable "compartment_ocid" {
  description = "OCID do compartment."
  type        = string
}

variable "name_prefix" {
  description = "Prefixo de nomes dos recursos de rede."
  type        = string
}

variable "vcn_cidr" {
  description = "CIDR da VCN."
  type        = string
}

variable "public_subnet_cidr" {
  description = "CIDR da subnet publica."
  type        = string
}

variable "admin_cidr" {
  description = "CIDR administrativo autorizado para SSH."
  type        = string
}

variable "enable_http" {
  description = "Habilita entrada HTTP."
  type        = bool
}

variable "enable_https" {
  description = "Habilita entrada HTTPS."
  type        = bool
}

variable "freeform_tags" {
  description = "Tags livres aplicadas aos recursos."
  type        = map(string)
  default     = {}
}
