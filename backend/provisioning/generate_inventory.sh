#!/bin/bash

set -e

# Aller dans le dossier Terraform pour extraire l'IP
cd terraform
IP=$(terraform output -raw instance_public_ip)
cd ..

# Générer l'inventaire Ansible
cat <<EOF > ansible/inventory.ini
[vm]
vm1 ansible_host=$IP ansible_user=ubuntu ansible_ssh_private_key_file=terraform/provisioning-key.pem
EOF

echo "✅ Fichier ansible/inventory.ini généré avec l'adresse IP : $IP"

