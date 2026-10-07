# Look the AMI up instead of hard-coding a region-specific ID.
data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023*-x86_64"]
  }
}

resource "aws_instance" "web" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public["a"].id
  vpc_security_group_ids = [aws_security_group.web.id]
  iam_instance_profile   = aws_iam_instance_profile.web.name

  # On boot: install nginx and pull the page from the S3 bucket (uses the role).
  user_data = templatefile("${path.module}/files/user_data.sh.tftpl", {
    bucket = aws_s3_bucket.assets.bucket
    region = var.aws_region
  })

  root_block_device {
    volume_size           = 10
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = true
  }

  metadata_options {
    http_tokens = "required" # IMDSv2 only
  }

  # Explicit dependency: nothing in this block references the IGW or the
  # route-table association, but user_data needs internet access at boot
  # (dnf install nginx). Without depends_on, Terraform could start the
  # instance before the public route exists.
  depends_on = [
    aws_internet_gateway.main,
    aws_route_table_association.public,
  ]

  tags = { Name = "${var.project}-ec2" }
}
