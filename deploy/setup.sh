#!/usr/bin/env bash
# EC2 provisioning script for the Investment Committee web app.
# Target: Ubuntu 24.04 on t3.medium (2 vCPU, 4GB RAM, 20GB gp3)
set -euo pipefail

echo "=== Investment Committee — EC2 Setup ==="

# ── System packages ──────────────────────────────────────────────────────────
sudo apt-get update -y
sudo apt-get install -y \
  python3.12 python3.12-venv python3-pip \
  nginx certbot python3-certbot-nginx \
  git curl unzip

# ── Node.js (LTS) ───────────────────────────────────────────────────────────
if ! command -v node &>/dev/null; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi

# ── App directory ────────────────────────────────────────────────────────────
APP_DIR=/opt/ragent
sudo mkdir -p "$APP_DIR"
sudo chown "$USER:$USER" "$APP_DIR"

echo "Copy your project files to $APP_DIR, then run:"
echo "  cd $APP_DIR"
echo "  python3.12 -m venv .venv && source .venv/bin/activate"
echo "  pip install -r requirements.txt"
echo "  cd frontend && npm ci && npm run build && cd .."
echo "  cp deploy/.env.production .env"
echo "  # Edit .env with your API keys"
echo ""

# ── Systemd service ─────────────────────────────────────────────────────────
sudo cp "$APP_DIR/deploy/ragent.service" /etc/systemd/system/ragent.service
sudo systemctl daemon-reload
sudo systemctl enable ragent

# ── Nginx ────────────────────────────────────────────────────────────────────
sudo cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/ragent
sudo ln -sf /etc/nginx/sites-available/ragent /etc/nginx/sites-enabled/ragent
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

echo ""
echo "=== Done. Start the app with: sudo systemctl start ragent ==="
