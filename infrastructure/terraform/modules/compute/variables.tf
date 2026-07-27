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

variable "public_subnet_cidr" {
  description = "CIDR da subnet publica usada pelo Load Balancer."
  type        = string
}

variable "cloud_init_template_path" {
  description = "Caminho do template cloud-init."
  type        = string
}

variable "api_image_ref" {
  description = "Referencia imutavel da imagem publica GHCR da API."
  type        = string
}

variable "web_image_ref" {
  description = "Referencia imutavel da imagem publica GHCR do Web."
  type        = string
}

variable "nginx_image_ref" {
  description = "Imagem publica fixa do proxy Nginx unprivileged."
  type        = string
}

variable "deploy_application" {
  description = "Controla o bootstrap declarativo da aplicacao."
  type        = bool
}

variable "application_host_port" {
  description = "Porta local da VM usada pelo Nginx e pelo backend do Load Balancer."
  type        = number
}

variable "application_container_port" {
  description = "Porta interna do container Nginx."
  type        = number
}

variable "application_health_path" {
  description = "Caminho de health da aplicacao."
  type        = string
}

variable "application_root_dir" {
  description = "Diretorio raiz da aplicacao na VM."
  type        = string
}

variable "application_start_timeout_seconds" {
  description = "Tempo maximo de espera pelo health check no bootstrap."
  type        = number
}

variable "freeform_tags" {
  description = "Tags livres aplicadas aos recursos."
  type        = map(string)
  default     = {}
}
