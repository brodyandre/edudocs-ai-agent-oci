variable "tenancy_ocid" {
  description = "OCID da tenancy OCI usada como parent direto do compartment dedicado."
  type        = string

  validation {
    condition     = can(regex("^ocid1\\.tenancy\\.oc1\\.", var.tenancy_ocid))
    error_message = "tenancy_ocid deve parecer um OCID de tenancy OCI."
  }
}

variable "region" {
  description = "Home region OCI onde o compartment sera gerenciado."
  type        = string

  validation {
    condition     = length(trimspace(var.region)) > 0
    error_message = "region nao pode ficar vazia."
  }
}

variable "config_file_profile" {
  description = "Perfil local do arquivo ~/.oci/config."
  type        = string
  default     = "EDUDOCS"

  validation {
    condition     = can(regex("^[A-Za-z0-9_-]+$", var.config_file_profile))
    error_message = "config_file_profile deve conter apenas letras, numeros, hifen ou sublinhado."
  }
}

variable "compartment_name" {
  description = "Nome fixo do compartment dedicado do workload."
  type        = string
  default     = "edudocs-ai-prod"

  validation {
    condition = (
      var.compartment_name == "edudocs-ai-prod"
      && !contains(["root", "tenancy"], lower(var.compartment_name))
      && !strcontains(var.compartment_name, "/")
      && !strcontains(var.compartment_name, "\n")
      && !strcontains(var.compartment_name, "\r")
    )
    error_message = "compartment_name deve ser exatamente edudocs-ai-prod, sem root, tenancy, barra ou newline."
  }
}

variable "compartment_description" {
  description = "Descricao nao sensivel do compartment dedicado."
  type        = string
  default     = "Recursos de producao do projeto EduDocs AI."

  validation {
    condition     = length(trimspace(var.compartment_description)) > 0
    error_message = "compartment_description nao pode ficar vazia."
  }
}

variable "common_tags" {
  description = "Tags livres nao sensiveis adicionais."
  type        = map(string)
  default     = {}
}
