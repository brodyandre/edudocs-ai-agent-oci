variable "compartment_ocid" {
  description = "OCID do compartment."
  type        = string
}

variable "create_backup_bucket" {
  description = "Cria o bucket privado opcional."
  type        = bool
}

variable "backup_bucket_name" {
  description = "Nome do bucket privado opcional."
  type        = string
  default     = null
}

variable "freeform_tags" {
  description = "Tags livres aplicadas aos recursos."
  type        = map(string)
  default     = {}
}
