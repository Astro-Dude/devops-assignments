# Internet-facing load balancer (created by ingress-nginx / AWS LB controller).
resource "aws_security_group" "alb" {
  name        = "${local.name}-alb"
  description = "Public HTTP/HTTPS to the TicketHub ingress load balancer"
  vpc_id      = aws_vpc.main.id
  tags        = { Name = "${local.name}-alb-sg" }
}

resource "aws_vpc_security_group_ingress_rule" "alb_https" {
  security_group_id = aws_security_group.alb.id
  description       = "HTTPS from the internet (public web app)"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  security_group_id = aws_security_group.alb.id
  description       = "HTTP from the internet, redirected to HTTPS by ingress-nginx"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "alb_to_nodes" {
  security_group_id            = aws_security_group.alb.id
  description                  = "Forward to ingress NodePorts on the worker nodes"
  referenced_security_group_id = aws_security_group.nodes.id
  from_port                    = 30000
  to_port                      = 32767
  ip_protocol                  = "tcp"
}

# Worker nodes: only the load balancer and the nodes themselves may reach them.
resource "aws_security_group" "nodes" {
  name        = "${local.name}-nodes"
  description = "EKS worker nodes"
  vpc_id      = aws_vpc.main.id
  tags        = { Name = "${local.name}-nodes-sg" }
}

resource "aws_vpc_security_group_ingress_rule" "nodes_from_alb" {
  security_group_id            = aws_security_group.nodes.id
  description                  = "NodePorts from the load balancer only"
  referenced_security_group_id = aws_security_group.alb.id
  from_port                    = 30000
  to_port                      = 32767
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "nodes_self" {
  security_group_id            = aws_security_group.nodes.id
  description                  = "Pod-to-pod / node-to-node traffic"
  referenced_security_group_id = aws_security_group.nodes.id
  ip_protocol                  = "-1"
}

resource "aws_vpc_security_group_egress_rule" "nodes_https" {
  security_group_id = aws_security_group.nodes.id
  description       = "HTTPS only: pull images from GHCR/ECR, reach AWS APIs (via NAT)"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "nodes_in_vpc" {
  security_group_id = aws_security_group.nodes.id
  description       = "Anything inside the VPC (DNS resolver, pods, control plane ENIs)"
  cidr_ipv4         = var.vpc_cidr
  ip_protocol       = "-1"
}
