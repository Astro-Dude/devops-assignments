# The bucket itself.
resource "aws_s3_bucket" "demo" {
  bucket        = var.bucket_name
  force_destroy = true # lets `terraform destroy` remove a non-empty bucket (demo only)

  tags = {
    Name        = var.bucket_name
    Environment = var.environment
    Project     = "Session18-S3-Demo"
  }
}

# Versioning: overwrites/deletes keep the previous object versions.
resource "aws_s3_bucket_versioning" "demo" {
  bucket = aws_s3_bucket.demo.id

  versioning_configuration {
    status = var.enable_versioning ? "Enabled" : "Suspended"
  }
}

# Default encryption at rest (SSE-S3 / AES-256) for every new object.
resource "aws_s3_bucket_server_side_encryption_configuration" "demo" {
  bucket = aws_s3_bucket.demo.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Block every form of public access.
resource "aws_s3_bucket_public_access_block" "demo" {
  bucket = aws_s3_bucket.demo.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# A small object so the bucket is not empty and versioning has something to track.
resource "aws_s3_object" "hello" {
  bucket       = aws_s3_bucket.demo.id
  key          = "hello.txt"
  content      = "Created by Terraform for Session 18 - ${var.owner}\n"
  content_type = "text/plain"

  # Upload only after default encryption is configured.
  depends_on = [aws_s3_bucket_server_side_encryption_configuration.demo]
}
