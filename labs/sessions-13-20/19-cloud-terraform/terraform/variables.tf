variable "aws_region" {
  description = "Region every resource in this project is created in. A region is a geographic area; the subnets below pick Availability Zones inside it."
  type        = string
  default     = "us-east-1"

  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-[0-9]$", var.aws_region))
    error_message = "aws_region must look like us-east-1 or ap-south-1."
  }
}

variable "aws_endpoint_url" {
  description = "API endpoint all AWS service calls are sent to. Point this at LocalStack for local work, or set it to an empty override and delete the endpoints block for real AWS."
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

variable "project_prefix" {
  description = "Prefix stamped on the name of every resource so this homework is easy to find and easy to delete."
  type        = string
  default     = "hw19"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,19}$", var.project_prefix))
    error_message = "project_prefix must be lowercase, start with a letter, and be 2 to 20 characters long."
  }
}

variable "environment" {
  description = "Environment name. Applied to every resource through the provider default_tags block."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of dev, staging or prod."
  }
}

variable "vpc_cidr" {
  description = "Address range of the whole VPC. Every subnet CIDR has to fit inside this."
  type        = string
  default     = "10.19.0.0/16"

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0)) && tonumber(split("/", var.vpc_cidr)[1]) <= 16
    error_message = "vpc_cidr must be a valid IPv4 CIDR with a prefix length of /16 or shorter."
  }
}

variable "public_subnet_cidr" {
  description = "Address range of the single public subnet."
  type        = string
  default     = "10.19.1.0/24"

  validation {
    condition     = can(cidrhost(var.public_subnet_cidr, 0))
    error_message = "public_subnet_cidr must be a valid IPv4 CIDR."
  }
}

variable "public_subnet_az_suffix" {
  description = "Letter of the Availability Zone the public subnet lives in, appended to aws_region."
  type        = string
  default     = "a"
}

variable "private_subnets" {
  description = "Private subnets to create, keyed by role. Each entry becomes one subnet in its own Availability Zone through for_each."
  type = map(object({
    cidr      = string
    az_suffix = string
  }))
  default = {
    app = {
      cidr      = "10.19.11.0/24"
      az_suffix = "b"
    }
    data = {
      cidr      = "10.19.12.0/24"
      az_suffix = "c"
    }
  }

  validation {
    condition     = length(var.private_subnets) >= 1
    error_message = "Define at least one private subnet."
  }

  validation {
    condition     = alltrue([for s in values(var.private_subnets) : can(cidrhost(s.cidr, 0))])
    error_message = "Every private subnet cidr must be a valid IPv4 CIDR."
  }
}

variable "instance_type" {
  description = "EC2 instance size for the web node."
  type        = string
  default     = "t3.micro"

  validation {
    condition     = contains(["t2.micro", "t3.micro", "t3.small"], var.instance_type)
    error_message = "instance_type must be one of t2.micro, t3.micro or t3.small."
  }
}

variable "ami_name_filter" {
  description = "Exact AMI name the aws_ami data source looks up. On real AWS this would be a wildcard such as al2023-ami-*-x86_64."
  type        = string
  default     = "amzn-ami-hvm-2018.03.0.20231218.0-x86_64-gp2"
}

variable "ami_owner" {
  description = "Account id that owns the AMI. 137112412989 is the Amazon Linux publisher."
  type        = string
  default     = "137112412989"
}

variable "allowed_http_cidrs" {
  description = "Source ranges allowed to reach ports 80 and 443 on the web security group."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "allowed_ssh_cidr" {
  description = "Source range allowed to reach port 22. Deliberately not 0.0.0.0/0."
  type        = string
  default     = "10.19.0.0/16"

  validation {
    condition     = can(cidrhost(var.allowed_ssh_cidr, 0))
    error_message = "allowed_ssh_cidr must be a valid IPv4 CIDR."
  }
}

variable "app_port" {
  description = "Port the private application tier listens on."
  type        = number
  default     = 8080

  validation {
    condition     = var.app_port > 0 && var.app_port <= 65535
    error_message = "app_port must be between 1 and 65535."
  }
}

variable "app_admin_token" {
  description = "Token written into the application config object in S3. Marked sensitive so Terraform keeps it out of plan and output text."
  type        = string
  default     = "replace-me"
  sensitive   = true
}

variable "enable_versioning" {
  description = "Whether the artifacts bucket keeps old object versions."
  type        = bool
  default     = true
}
