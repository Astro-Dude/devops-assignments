# ---------------------------------------------------------------------------
# AWS provider aimed at the LOCAL AWS emulator (moto server, localhost:4566).
# No real AWS account is used; the keys are dummies the emulator accepts.
#
# For real AWS: delete access_key ... endpoints {} and authenticate with
# `aws configure` / AWS_PROFILE / an assumed role. Nothing else changes.
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
    ec2 = var.aws_endpoint
    iam = var.aws_endpoint
    s3  = var.aws_endpoint
    sts = var.aws_endpoint
  }

  # Applied to every taggable resource this provider creates.
  default_tags {
    tags = {
      Project   = var.project
      Session   = "19"
      ManagedBy = "Terraform"
      Owner     = var.owner
    }
  }
}

provider "random" {}
