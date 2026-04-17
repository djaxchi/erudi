# Prerequisites

- [terraform](https://developer.hashicorp.com/terraform/install)
- [aws-cli](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- [ansible](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html#installing-and-upgrading-ansible)

# Configurations

## AWS

Add `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` as environment variables (Nabil will create an AWS user and generate those keys for you).

## Generate a SSH key to login into the VM

### On Windows

From Git Bash or a PowerShell:

`ssh-keygen -t ed25519 -f C:\Users\<user>\.ssh\id_ed25519_<name>_aws`

### On Linux

`ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_<name>_aws`

You have to copy the ssh public key in a new file under `ansible/roles/users/files/authorized_keys/<name>.pub` so it'll be added into the VM when provisioning it. See `nabil.pub`.

## Generate a Github token 

Go under `Settings > Developer settings > Personal access tokens > Tokens (classic) > Generate new token > Generate new token (classic)` on Github.

- Put the name you want (something explicit).
- Disable token expiration.
- Grant `repo` scope.

<!---->
<!-- To turn off/stop the VM: -->
<!---->
<!-- ``` -->
<!-- terraform apply -var="instance_state=stopped" -->
<!-- ``` -->
<!---->
<!-- ``` -->
<!-- terraform import aws_key_pair.generated_key terraform-provisioning-key -->
<!-- terraform import aws_key_pair.generated_key provisioning-key -->
<!-- terraform import aws_security_group.vm_sg sg-076c01faceef696f8 -->
<!-- ``` -->
