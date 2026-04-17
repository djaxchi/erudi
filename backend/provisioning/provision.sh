#!/bin/bash

set -e

cd terraform

echo "Importation des tokens AWS."
set -a
source terraform/.env
set +a

echo "Importation des variables Terraform."
# terraform import aws_key_pair.generated_key terraform-provisioning-key
# terraform import aws_key_pair.generated_key provisioning-key
# terraform import aws_security_group.vm_sg sg-076c01faceef696f8

echo "Destruction de l'instance"
terraform destroy

echo "🚀 Lancement du provisioning..."

terraform init
terraform apply -auto-approve
cd ..

./generate_inventory.sh

ANSIBLE_HOST_KEY_CHECKING=False \
ansible-playbook -i ansible/inventory.ini ansible/playbook.yml --vault-password-file ansible/vault_password.txt

