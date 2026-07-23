module "network" {
  source = "./modules/network"

  compartment_ocid   = var.compartment_ocid
  name_prefix        = local.name_prefix
  vcn_cidr           = var.vcn_cidr
  public_subnet_cidr = var.public_subnet_cidr
  admin_cidr         = var.admin_cidr
  enable_http        = var.enable_http
  enable_https       = var.enable_https
  freeform_tags      = local.common_tags
}

module "compute" {
  source = "./modules/compute"

  compartment_ocid         = var.compartment_ocid
  availability_domain      = local.selected_availability_domain
  name_prefix              = local.name_prefix
  compute_shape            = var.compute_shape
  compute_ocpus            = var.compute_ocpus
  compute_memory_gbs       = var.compute_memory_gbs
  boot_volume_size_gbs     = var.boot_volume_size_gbs
  image_ocid               = local.selected_image_ocid
  ssh_public_key_path      = var.ssh_public_key_path
  public_subnet_id         = module.network.public_subnet_id
  nsg_ids                  = [module.network.nsg_id]
  admin_cidr               = var.admin_cidr
  cloud_init_template_path = "${path.module}/../cloud-init/app-server.yaml.tftpl"
  freeform_tags            = local.common_tags
}

module "object_storage" {
  source = "./modules/object-storage"

  compartment_ocid     = var.compartment_ocid
  create_backup_bucket = var.create_backup_bucket
  backup_bucket_name   = var.backup_bucket_name
  freeform_tags        = local.common_tags
}
