terraform {
  required_version = ">= 1.15.0, < 1.16.0"

  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 8.23.0"
    }
  }
}
