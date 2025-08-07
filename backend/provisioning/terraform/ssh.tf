resource "tls_private_key" "ssh_key" {
  algorithm = "ED25519"
}

resource "aws_key_pair" "generated_key" {
  key_name   = var.key_name
  public_key = tls_private_key.ssh_key.public_key_openssh
}

resource "local_file" "private_key_pem" {
  content         = tls_private_key.ssh_key.private_key_openssh
  filename        = "${path.module}/provisioning-key.pem"
  file_permission = "0600"
}

