terraform {
  required_version = ">= 1.6.0"

  # Two providers: "aws" talks to the (emulated) AWS API, "random" generates a
  # unique suffix for the globally-unique S3 bucket name.
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}
