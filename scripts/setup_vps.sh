#!/usr/bin/env bash
# One-time VPS setup for AyurSaarthi (Ubuntu 22.04/24.04 on Hostinger KVM).
# Run as a sudo user:  bash scripts/setup_vps.sh
set -euo pipefail

echo "== Resources =="; free -h; nproc; df -h /

echo "== Packages =="
sudo apt-get update -y
sudo apt-get install -y git python3-venv python3-pip curl ufw docker.io docker-compose-v2 || \
  sudo apt-get install -y git python3-venv python3-pip curl ufw docker.io docker-compose-plugin
sudo usermod -aG docker "$USER" || true

echo "== Swap (helps on 8 GB plans) =="
if ! swapon --show | grep -q swapfile; then
  sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile
  sudo mkswap /swapfile && sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi

echo "== Firewall: only SSH, HTTP, HTTPS (Ollama 11434 stays private) =="
sudo ufw allow OpenSSH; sudo ufw allow 80; sudo ufw allow 443
sudo ufw --force enable

echo "== Ollama =="
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama
ollama pull hf.co/A-Aryam/AyurParam-GGUF:Q4_K_M

echo "== Python env =="
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -r requirements.txt

echo "Done. Log out and back in once (docker group). Next: python -m scripts.test_model"
