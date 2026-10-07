# Bucket names are global, so add a random suffix (second provider in use).
resource "random_id" "bucket_suffix" {
  byte_length = 3
}

resource "aws_s3_bucket" "assets" {
  bucket        = "${var.project}-assets-${random_id.bucket_suffix.hex}"
  force_destroy = true # lab only: allow destroy while objects exist

  tags = { Name = "${var.project}-assets" }
}

resource "aws_s3_bucket_versioning" "assets" {
  bucket = aws_s3_bucket.assets.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "assets" {
  bucket = aws_s3_bucket.assets.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "assets" {
  bucket                  = aws_s3_bucket.assets.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# The page the web server downloads at boot.
resource "aws_s3_object" "index" {
  bucket       = aws_s3_bucket.assets.id
  key          = "site/index.html"
  content_type = "text/html"
  content = templatefile("${path.module}/files/index.html.tftpl", {
    project = var.project
    owner   = var.owner
  })

  depends_on = [aws_s3_bucket_server_side_encryption_configuration.assets]
}
