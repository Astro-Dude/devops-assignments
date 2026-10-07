output "vpc_id" {
  description = "ID of the VPC."
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "Public subnet IDs by AZ suffix."
  value       = { for k, s in aws_subnet.public : k => s.id }
}

output "private_subnet_ids" {
  description = "Private subnet IDs by AZ suffix."
  value       = { for k, s in aws_subnet.private : k => s.id }
}

output "security_group_id" {
  description = "Web security group."
  value       = aws_security_group.web.id
}

output "ami_used" {
  description = "AMI the instance was launched from (found by the data source)."
  value       = "${data.aws_ami.al2023.id} (${data.aws_ami.al2023.name})"
}

output "instance_id" {
  description = "EC2 instance ID."
  value       = aws_instance.web.id
}

output "instance_public_ip" {
  description = "Public IP of the web server."
  value       = aws_instance.web.public_ip
}

output "instance_private_ip" {
  description = "Private IP of the web server."
  value       = aws_instance.web.private_ip
}

output "bucket_name" {
  description = "Assets bucket."
  value       = aws_s3_bucket.assets.bucket
}

output "web_url" {
  description = "Where the site would be served on real AWS."
  value       = "http://${aws_instance.web.public_ip}/"
}
