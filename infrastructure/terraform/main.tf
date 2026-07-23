module "network" {
  source = "./modules/network"

  compartment_ocid   = var.compartment_ocid
  name_prefix        = local.name_prefix
  vcn_cidr           = var.vcn_cidr
  public_subnet_cidr = var.public_subnet_cidr
  admin_cidr         = var.admin_cidr
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
  nsg_ids                  = [module.network.app_nsg_id]
  admin_cidr               = var.admin_cidr
  cloud_init_template_path = "${path.module}/../cloud-init/app-server.yaml.tftpl"
  freeform_tags            = local.common_tags
}

module "load_balancer" {
  source = "./modules/load-balancer"

  compartment_ocid          = var.compartment_ocid
  name_prefix               = local.name_prefix
  public_subnet_id          = module.network.public_subnet_id
  load_balancer_nsg_id      = module.network.load_balancer_nsg_id
  app_nsg_id                = module.network.app_nsg_id
  backend_private_ip        = module.compute.private_ip
  load_balancer_shape       = var.load_balancer_shape
  minimum_bandwidth_in_mbps = var.load_balancer_min_bandwidth_mbps
  maximum_bandwidth_in_mbps = var.load_balancer_max_bandwidth_mbps
  listener_port             = var.load_balancer_listener_port
  backend_port              = var.load_balancer_backend_port
  health_path               = var.load_balancer_health_path
  freeform_tags             = local.common_tags
}

module "object_storage" {
  source = "./modules/object-storage"

  compartment_ocid     = var.compartment_ocid
  create_backup_bucket = var.create_backup_bucket
  backup_bucket_name   = var.backup_bucket_name
  freeform_tags        = local.common_tags
}
