# One provider block for both targets:
#   aws_endpoint = "http://localhost:4567"  -> every service goes to the local emulator (moto)
#   aws_endpoint = ""                       -> real AWS, normal credential chain
provider "aws" {
  region = var.region

  access_key                  = var.aws_endpoint != "" ? "test" : null
  secret_key                  = var.aws_endpoint != "" ? "test" : null
  skip_credentials_validation = var.aws_endpoint != ""
  skip_requesting_account_id  = var.aws_endpoint != ""
  skip_metadata_api_check     = var.aws_endpoint != ""
  s3_use_path_style           = var.aws_endpoint != ""

  dynamic "endpoints" {
    for_each = var.aws_endpoint != "" ? [1] : []
    content {
      ec2      = var.aws_endpoint
      ecr      = var.aws_endpoint
      eks      = var.aws_endpoint
      iam      = var.aws_endpoint
      kms      = var.aws_endpoint
      logs     = var.aws_endpoint
      s3       = var.aws_endpoint
      sts      = var.aws_endpoint
      dynamodb = var.aws_endpoint
    }
  }

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
      Owner       = "24BCS10151"
    }
  }
}
