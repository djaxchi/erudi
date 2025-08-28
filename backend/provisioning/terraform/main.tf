provider "aws" {
  region = var.aws_region
}

data "aws_vpc" "default" {
  default = true
}

resource "aws_security_group" "vm_sg" {
  name        = "openvpn-access-server-sg"
  description = "Security group for OpenVPN Access Server"
  vpc_id      = data.aws_vpc.default.id

  # SSH
  ingress {
    description = "SSH administration"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["80.214.222.47/32"] # <-- Admin IP
  }

  # Admin Web UI 
  ingress {
    description = "Admin Web UI"
    from_port   = 943
    to_port     = 943
    protocol    = "tcp"
    cidr_blocks = ["80.214.222.47/32"] # <-- Admin IP
  }

  # HTTPS / Client Web UI / OpenVPN TCP en multi-daemon (TCP 443)
  ingress {
    description = "HTTPS / Client Web UI / OpenVPN TCP"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # OpenVPN UDP (UDP 1194)
  ingress {
    description = "OpenVPN UDP"
    from_port   = 1194
    to_port     = 1194
    protocol    = "udp"
    cidr_blocks = ["0.0.0.0/0"]
  }


  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "app_server" {
  ami                         = var.ami_id
  instance_type               = var.instance_type
  key_name                    = aws_key_pair.generated_key.key_name
  vpc_security_group_ids      = [aws_security_group.vm_sg.id]

  tags = {
    Name = var.instance_name
  }
}
