output "backup_bucket_name" {
  description = "Nome do bucket privado opcional."
  value       = try(oci_objectstorage_bucket.backup[0].name, null)
}
