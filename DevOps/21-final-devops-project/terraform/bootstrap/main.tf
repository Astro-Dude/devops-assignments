# Creates the remote-state bucket the main stack uses (chicken-and-egg: this stack keeps local state).
terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

variable "region" {
  type    = string
  default = "ap-south-1"
}

variable "aws_endpoint" {
  type    = string
  default = ""
}

provider "aws" {
  region                      = var.region
  access_key                  = var.aws_endpoint != "" ? "test" : null
  secret_key                  = var.aws_endpoint != "" ? "test" : null
  skip_credentials_validation = var.aws_endpoint != ""
  skip_requesting_account_id  = var.aws_endpoint != ""
  skip_metadata_api_check     = var.aws_endpoint != ""
  s3_use_path_style           = var.aws_endpoint != ""
  dynamic "endpoints" {
    for_each = var.aws_endpoint != "" ? [1] : []
    content {
      s3  = var.aws_endpoint
      sts = var.aws_endpoint
      kms = var.aws_endpoint
    }
  }
}

resource "aws_kms_key" "tfstate" {
  description             = "tickethub terraform state encryption"
  enable_key_rotation     = true
  deletion_window_in_days = 7
}

resource "aws_s3_bucket" "tfstate" {
  bucket        = "tickethub-tfstate-24bcs10151"
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  versioning_configuration {
    status = "Enabled" # every state write is recoverable
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.tfstate.arn
    }
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket                  = aws_s3_bucket.tfstate.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

output "state_bucket" {
  value = aws_s3_bucket.tfstate.bucket
}
