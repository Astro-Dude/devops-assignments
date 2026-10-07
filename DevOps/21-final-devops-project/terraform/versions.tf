terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
  # Remote state in the S3 bucket created by ./bootstrap.
  # terraform init -backend-config=backend-emulator.hcl   (local AWS emulator)
  # terraform init -backend-config=backend-aws.hcl        (real account)
  backend "s3" {}
}
