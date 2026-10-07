output "vpc_id" {
  description = "Id of the VPC every other resource hangs off."
  value       = aws_vpc.main.id
}

output "vpc_cidr" {
  description = "Address range of the VPC."
  value       = aws_vpc.main.cidr_block
}

output "public_subnet_id" {
  description = "Id of the public subnet."
  value       = aws_subnet.public.id
}

output "public_subnet_az" {
  description = "Availability Zone the public subnet lives in."
  value       = aws_subnet.public.availability_zone
}

output "private_subnet_ids" {
  description = "Map of role name to private subnet id, built from the for_each instances."
  value       = { for k, s in aws_subnet.private : k => s.id }
}

output "private_subnet_azs" {
  description = "Map of role name to Availability Zone, proving the private subnets are spread across AZs."
  value       = { for k, s in aws_subnet.private : k => s.availability_zone }
}

output "internet_gateway_id" {
  description = "Id of the internet gateway attached to the VPC."
  value       = aws_internet_gateway.main.id
}

output "public_route_table_id" {
  description = "Id of the route table that carries the 0.0.0.0/0 route."
  value       = aws_route_table.public.id
}

output "web_security_group_id" {
  description = "Id of the edge security group."
  value       = aws_security_group.web.id
}

output "app_security_group_id" {
  description = "Id of the private application security group."
  value       = aws_security_group.app.id
}

output "network_acl_id" {
  description = "Id of the custom network ACL attached to the public subnet."
  value       = aws_network_acl.public.id
}

output "instance_id" {
  description = "Id of the EC2 instance."
  value       = aws_instance.web.id
}

output "instance_private_ip" {
  description = "Private IPv4 address of the EC2 instance inside the VPC."
  value       = aws_instance.web.private_ip
}

output "instance_public_ip" {
  description = "Public IPv4 address assigned to the EC2 instance."
  value       = aws_instance.web.public_ip
}

output "ami_id" {
  description = "AMI id resolved by the aws_ami data source."
  value       = data.aws_ami.amazon_linux.id
}

output "artifacts_bucket" {
  description = "Name of the S3 artifacts bucket."
  value       = aws_s3_bucket.artifacts.bucket
}

output "artifacts_bucket_arn" {
  description = "ARN of the S3 artifacts bucket."
  value       = aws_s3_bucket.artifacts.arn
}

output "app_admin_token" {
  description = "Admin token handed to the application. Marked sensitive, so the bulk terraform output listing and the plan and apply logs redact it."
  value       = var.app_admin_token
  sensitive   = true
}

output "resource_summary" {
  description = "One-line inventory of what this configuration owns."
  value = {
    subnets_total   = 1 + length(aws_subnet.private)
    security_groups = 2
    environment     = var.environment
    region          = var.aws_region
  }
}
