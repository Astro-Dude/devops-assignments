# terraform init -backend-config=backend-emulator.hcl
# State bucket + lock table are created by ./bootstrap against the same emulator.
bucket         = "tickethub-tfstate-24bcs10151"
key            = "dev/terraform.tfstate"
region         = "ap-south-1"
encrypt        = true
use_lockfile   = true
use_path_style = true
access_key     = "test"
secret_key     = "test"
endpoints = {
  s3  = "http://localhost:4567"
  sts = "http://localhost:4567"
}
skip_credentials_validation = true
skip_requesting_account_id  = true
skip_metadata_api_check     = true
skip_region_validation      = true
