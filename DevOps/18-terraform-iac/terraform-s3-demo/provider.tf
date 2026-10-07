terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

# ---------------------------------------------------------------------------
# AWS provider pointed at a LOCAL AWS emulator (moto server on :4566).
# No real AWS account is used. The dummy keys below are not secrets: the
# emulator accepts any value. To target real AWS, delete everything from
# access_key down to the end of the endpoints block and let the provider pick
# up real credentials from `aws configure` / environment variables.
# ---------------------------------------------------------------------------
provider "aws" {
  region = var.aws_region

  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
  s3_use_path_style           = true

  endpoints {
    s3  = var.aws_endpoint
    sts = var.aws_endpoint
    iam = var.aws_endpoint
  }

  default_tags {
    tags = {
      ManagedBy = "Terraform"
      Owner     = var.owner
    }
  }
}
