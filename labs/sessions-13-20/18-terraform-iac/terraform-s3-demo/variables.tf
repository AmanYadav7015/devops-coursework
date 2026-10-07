variable "aws_region" {
  description = "Region the bucket is created in."
  type        = string
  default     = "us-east-1"
}

variable "aws_endpoint_url" {
  description = "Endpoint the AWS provider talks to. Points at LocalStack for this lab."
  type        = string
  default     = "http://localhost:4566"
}

variable "aws_access_key" {
  description = "Access key id. LocalStack accepts any non-empty value."
  type        = string
  default     = "test"
}

variable "aws_secret_key" {
  description = "Secret access key. LocalStack accepts any non-empty value."
  type        = string
  default     = "test"
  sensitive   = true
}

variable "bucket_name" {
  description = "Globally unique name of the S3 bucket."
  type        = string

  validation {
    condition     = can(regex("^hw18-", var.bucket_name))
    error_message = "Bucket name must start with hw18- so this lab never collides with other labs."
  }
}

variable "environment" {
  description = "Environment tag applied to every resource."
  type        = string
  default     = "dev"
}

variable "enable_versioning" {
  description = "Whether object versioning is enabled on the bucket."
  type        = bool
  default     = true
}
