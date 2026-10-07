terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region     = var.aws_region
  access_key = var.aws_access_key
  secret_key = var.aws_secret_key

  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  s3_use_path_style           = true

  default_tags {
    tags = {
      Project     = var.project_prefix
      Session     = "19"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }

  endpoints {
    ec2 = var.aws_endpoint_url
    s3  = var.aws_endpoint_url
    sts = var.aws_endpoint_url
    iam = var.aws_endpoint_url
  }
}
