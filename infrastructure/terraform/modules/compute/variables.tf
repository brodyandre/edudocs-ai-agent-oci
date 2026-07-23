variable "compartment_ocid" {
  description = "OCID do compartment."
  type        = string
}

variable "availability_domain" {
  description = "Availability domain selecionado."
  type        = string
}

variable "name_prefix" {
  description = "Prefixo de nomes dos recursos Compute."
  type        = string
}

variable "compute_shape" {
  description = "Shape Compute aprovado."
  type        = string
}

variable "compute_ocpus" {
  description = "Quantidade de OCPUs."
  type        = number
}

variable "compute_memory_gbs" {
  description = "Memoria em GB."
  type        = number
}

variable "boot_volume_size_gbs" {
  description = "Boot volume em GB."
  type        = number
}

variable "image_ocid" {
  description = "OCID da imagem selecionada."
  type        = string
}

variable "ssh_public_key_path" {
  description = "Caminho para a chave publica SSH local."
  type        = string
}

variable "public_subnet_id" {
  description = "OCID da subnet publica."
  type        = string
}

variable "nsg_ids" {
  description = "NSGs aplicados a VNIC."
  type        = list(string)
}

variable "admin_cidr" {
  description = "CIDR administrativo autorizado."
  type        = string
}

variable "cloud_init_template_path" {
  description = "Caminho do template cloud-init."
  type        = string
}

variable "freeform_tags" {
  description = "Tags livres aplicadas aos recursos."
  type        = map(string)
  default     = {}
}
