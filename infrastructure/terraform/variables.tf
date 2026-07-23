variable "tenancy_ocid" {
  description = "OCID da tenancy OCI. Deve ser informado por tfvars local, variavel TF_VAR_tenancy_ocid ou prompt seguro."
  type        = string

  validation {
    condition     = can(regex("^ocid1\\.tenancy\\.oc1\\.", var.tenancy_ocid))
    error_message = "tenancy_ocid deve parecer um OCID de tenancy OCI."
  }
}

variable "compartment_ocid" {
  description = "OCID do compartment onde a infraestrutura sera preparada."
  type        = string

  validation {
    condition     = can(regex("^ocid1\\.compartment\\.oc1\\.", var.compartment_ocid))
    error_message = "compartment_ocid deve parecer um OCID de compartment OCI."
  }
}

variable "region" {
  description = "Regiao OCI, preferencialmente a home region validada antes do primeiro plan real."
  type        = string

  validation {
    condition     = length(trimspace(var.region)) > 0
    error_message = "region nao pode ficar vazia."
  }
}

variable "config_file_profile" {
  description = "Perfil do arquivo de configuracao OCI local, sem versionar credenciais."
  type        = string
  default     = "DEFAULT"

  validation {
    condition     = can(regex("^[A-Za-z0-9_-]+$", var.config_file_profile))
    error_message = "config_file_profile deve conter apenas letras, numeros, hifen ou sublinhado."
  }
}

variable "project_name" {
  description = "Nome curto usado em recursos OCI."
  type        = string
  default     = "edudocs-ai"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,30}$", var.project_name))
    error_message = "project_name deve ser seguro para labels: minusculo, hifens, 3 a 31 caracteres."
  }
}

variable "environment" {
  description = "Ambiente logico dos recursos."
  type        = string
  default     = "production"

  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "environment deve ser development, staging ou production."
  }
}

variable "availability_domain" {
  description = "Availability domain opcional. Quando nulo, usa o primeiro AD retornado pela tenancy."
  type        = string
  default     = null
}

variable "compute_shape" {
  description = "Shape Compute aprovado para alvo Always Free."
  type        = string
  default     = "VM.Standard.A1.Flex"

  validation {
    condition     = var.compute_shape == "VM.Standard.A1.Flex"
    error_message = "compute_shape deve ser exatamente VM.Standard.A1.Flex."
  }
}

variable "compute_ocpus" {
  description = "OCPUs da instancia A1 Flex. Limite conservador desta entrega: ate 2."
  type        = number
  default     = 2

  validation {
    condition     = var.compute_ocpus > 0 && var.compute_ocpus <= 2
    error_message = "compute_ocpus deve ser maior que 0 e no maximo 2."
  }
}

variable "compute_memory_gbs" {
  description = "Memoria em GB da instancia A1 Flex. Limite conservador desta entrega: ate 12 GB."
  type        = number
  default     = 12

  validation {
    condition     = var.compute_memory_gbs > 0 && var.compute_memory_gbs <= 12
    error_message = "compute_memory_gbs deve ser maior que 0 e no maximo 12."
  }
}

variable "boot_volume_size_gbs" {
  description = "Tamanho do boot volume em GB."
  type        = number
  default     = 50

  validation {
    condition     = var.boot_volume_size_gbs >= 50 && var.boot_volume_size_gbs <= 100
    error_message = "boot_volume_size_gbs deve ficar entre 50 e 100."
  }
}

variable "image_ocid" {
  description = "OCID opcional de imagem ARM compativel. Quando nulo, a imagem Ubuntu sera descoberta por data source."
  type        = string
  default     = null

  validation {
    condition     = var.image_ocid == null || can(regex("^ocid1\\.image\\.oc1\\.", var.image_ocid))
    error_message = "image_ocid deve parecer um OCID de imagem OCI quando informado."
  }
}

variable "image_operating_system" {
  description = "Sistema operacional usado na descoberta automatica de imagem."
  type        = string
  default     = "Canonical Ubuntu"
}

variable "image_operating_system_version" {
  description = "Versao do sistema operacional usado na descoberta automatica de imagem."
  type        = string
  default     = "24.04"
}

variable "ssh_public_key_path" {
  description = "Caminho local para a chave publica SSH. Exemplo: ~/.ssh/id_ed25519.pub."
  type        = string

  validation {
    condition     = length(trimspace(var.ssh_public_key_path)) > 0
    error_message = "ssh_public_key_path nao pode ficar vazio."
  }
}

variable "admin_cidr" {
  description = "CIDR IPv4 administrativo autorizado a acessar SSH. Nunca use 0.0.0.0/0."
  type        = string

  validation {
    condition     = can(cidrhost(var.admin_cidr, 0)) && var.admin_cidr != "0.0.0.0/0"
    error_message = "admin_cidr deve ser um CIDR IPv4 especifico e nao pode ser 0.0.0.0/0."
  }
}

variable "vcn_cidr" {
  description = "CIDR da VCN."
  type        = string
  default     = "10.20.0.0/16"

  validation {
    condition     = can(cidrhost(var.vcn_cidr, 0))
    error_message = "vcn_cidr deve ser um CIDR valido."
  }
}

variable "public_subnet_cidr" {
  description = "CIDR da subnet publica."
  type        = string
  default     = "10.20.10.0/24"

  validation {
    condition     = can(cidrhost(var.public_subnet_cidr, 0))
    error_message = "public_subnet_cidr deve ser um CIDR valido."
  }
}

variable "enable_http" {
  description = "Quando true, libera entrada TCP 80 no NSG publico."
  type        = bool
  default     = true
}

variable "enable_https" {
  description = "Quando true, libera entrada TCP 443 no NSG publico."
  type        = bool
  default     = true
}

variable "create_backup_bucket" {
  description = "Cria um bucket privado opcional para backups futuros."
  type        = bool
  default     = false
}

variable "backup_bucket_name" {
  description = "Nome do bucket privado quando create_backup_bucket for true."
  type        = string
  default     = null

  validation {
    condition = (
      !var.create_backup_bucket
      || (
        var.backup_bucket_name != null
        && can(regex("^[a-z0-9][a-z0-9-]{2,62}$", var.backup_bucket_name))
      )
    )
    error_message = "backup_bucket_name deve ser informado e conter 3 a 63 caracteres minusculos, numeros ou hifens quando o bucket for habilitado."
  }
}

variable "common_tags" {
  description = "Tags livres adicionais aplicadas aos recursos."
  type        = map(string)
  default     = {}
}
