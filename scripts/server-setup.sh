#!/bin/bash
# Executar UMA VEZ no servidor Oracle Linux como opc
set -e

# Docker
sudo dnf config-manager --add-repo=https://download.docker.com/linux/centos/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin git
sudo systemctl enable --now docker
sudo usermod -aG docker opc

# Firewall: libera portas 80 e 443
sudo firewall-cmd --permanent --add-port=80/tcp
sudo firewall-cmd --permanent --add-port=443/tcp
sudo firewall-cmd --reload

echo ""
echo "IMPORTANTE: faça logout e login novamente para ativar o grupo docker."
echo "Depois execute:"
echo ""
echo "  cd /home/opc"
echo "  git clone https://github.com/henriquecalandra/proteinaja-backend.git"
echo "  git clone https://github.com/henriquecalandra/proteinaja-frontend.git"
echo "  cp /home/opc/proteinaja-backend/.env.example /home/opc/proteinaja-backend/.env"
echo "  nano /home/opc/proteinaja-backend/.env   # preencha as variáveis"
echo "  cd /home/opc/proteinaja-backend"
echo "  docker compose up -d --build"
