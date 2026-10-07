variable "aws_region" {
  description = "Region to deploy into."
  type        = string
  default     = "ap-south-1"
}

variable "aws_endpoint" {
  description = "Local AWS emulator endpoint (only needed because there is no real AWS account)."
  type        = string
  default     = "http://localhost:4566"
}

variable "project" {
  description = "Name prefix for every resource."
  type        = string
  default     = "s19-web"
}

variable "owner" {
  description = "Owner tag."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block of the VPC."
  type        = string
  default     = "10.20.0.0/16"

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0)) && tonumber(split("/", var.vpc_cidr)[1]) <= 24
    error_message = "vpc_cidr must be a valid IPv4 CIDR block of /24 or larger."
  }
}

variable "public_subnets" {
  description = "Public subnets: AZ suffix => CIDR."
  type        = map(string)
  default = {
    a = "10.20.1.0/24"
    b = "10.20.2.0/24"
  }
}

variable "private_subnets" {
  description = "Private subnets: AZ suffix => CIDR."
  type        = map(string)
  default = {
    a = "10.20.11.0/24"
    b = "10.20.12.0/24"
  }
}

variable "instance_type" {
  description = "EC2 instance type for the web server."
  type        = string
  default     = "t3.micro"
}

variable "admin_cidr" {
  description = "Only this CIDR may SSH to the web server."
  type        = string
  default     = "203.0.113.10/32"
}
