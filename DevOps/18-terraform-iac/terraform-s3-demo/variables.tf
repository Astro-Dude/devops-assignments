variable "aws_region" {
  description = "AWS region the bucket is created in."
  type        = string
  default     = "ap-south-1"
}

variable "aws_endpoint" {
  description = "Endpoint of the local AWS emulator. Only used because there is no real AWS account."
  type        = string
  default     = "http://localhost:4566"
}

variable "bucket_name" {
  description = "Globally unique S3 bucket name (3-63 chars, lowercase, digits, hyphens)."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$", var.bucket_name))
    error_message = "Bucket name must be 3-63 characters of lowercase letters, digits and hyphens."
  }
}

variable "environment" {
  description = "Environment tag (dev / staging / prod)."
  type        = string
  default     = "dev"
}

variable "owner" {
  description = "Owner tag applied to every resource via default_tags."
  type        = string
}

variable "enable_versioning" {
  description = "Keep every version of every object."
  type        = bool
  default     = true
}
