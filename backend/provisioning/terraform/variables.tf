variable "aws_region" {
  description = "The AWS region to create resources in."
  default     = "eu-west-3"
}

variable "instance_type" {
  description = "The type of EC2 instance to launch."
  default     = "t2.micro"
}

variable "ami_id" {
  description = "The AMI to use for the EC2 instance."
  default     = "ami-04ec97dc75ac850b1" # Ubuntu 24.04 LTS
}

variable "key_name" {
  description = "The name of the SSH key pair to use for the EC2 instance."
  default     = "provisioning-key"
}

variable "instance_name" {
  description = "The name of the EC2 instance."
  default     = "erudi-backend"
}
