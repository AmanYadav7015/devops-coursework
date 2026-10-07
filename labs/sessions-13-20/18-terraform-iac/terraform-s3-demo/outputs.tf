output "bucket_name" {
  description = "Name of the bucket Terraform created."
  value       = aws_s3_bucket.demo.bucket
}

output "bucket_arn" {
  description = "ARN of the bucket."
  value       = aws_s3_bucket.demo.arn
}

output "bucket_region" {
  description = "Region the bucket lives in."
  value       = aws_s3_bucket.demo.region
}

output "versioning_status" {
  description = "Current versioning status of the bucket."
  value       = aws_s3_bucket_versioning.demo.versioning_configuration[0].status
}

output "encryption_algorithm" {
  description = "Server-side encryption algorithm applied to new objects."
  value       = one(aws_s3_bucket_server_side_encryption_configuration.demo.rule).apply_server_side_encryption_by_default[0].sse_algorithm
}
