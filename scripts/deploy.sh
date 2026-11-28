#!/usr/bin/env bash
# Day 3: run AyurSaarthi permanently at https://aayu.svasthaayu.in
# Run on the server from /root/ayursaarthi:  bash scripts/deploy.sh
set -euo pipefail
DOMAIN=aayu.svasthaayu.in
IP=$(curl -4 -s https://api.ipify.org || hostname -I | awk '{print $1}')

echo "== 1. DNS check =="
RESOLVED=$(getent ahostsv4 "$DOMAIN" | awk 'NR==1{print $1}' || true)
echo "$DOMAIN -> ${RESOLVED:-nothing}   (this server: $IP)"
if [ "$RESOLVED" != "$IP" ]; then
  echo "STOP: the DNS A record for $DOMAIN does not point to $IP yet."
  echo "Add it (docs/DAY3.md, Step 1), wait 5-15 minutes, and run this script again."
  exit 1
fi

echo "== 2. Stop the test copy started with nohup (if any) =="
pkill -f "app.ui" || true
pkill -f "uvicorn api.main" || true

echo "== 3. Build data =="
. .venv/bin/activate
python -m ingest.ingest --include-draft
python -m kg.build_kg --include-draft

echo "== 4. Install services (start on boot, restart on crash) =="
cp deploy/ayursaarthi-ui.service deploy/ayursaarthi-api.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now ayursaarthi-ui ayursaarthi-api
systemctl enable --now ollama

echo "== 5. Caddy (HTTPS) =="
if ! command -v caddy >/dev/null; then
  apt-get update -y
  if ! apt-get install -y caddy; then
    echo "caddy not in Ubuntu's list: adding Caddy's official repository"
    apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor --yes -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -y && apt-get install -y caddy
  fi
fi
mkdir -p /var/log/caddy
cp deploy/Caddyfile /etc/caddy/Caddyfile
caddy validate --config /etc/caddy/Caddyfile
systemctl enable caddy && systemctl restart caddy

echo "== 6. Wait for the app, then test =="
for i in $(seq 1 30); do
  curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:7860/ | grep -q 200 && break
  sleep 3
done
sleep 5
echo "UI local:   $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:7860/)"
echo "API local:  $(curl -s http://127.0.0.1:8000/health)"
echo "Public:     $(curl -s -o /dev/null -w '%{http_code}' https://$DOMAIN/)"
echo "Public API: $(curl -s https://$DOMAIN/api/health)"
echo
echo "Done. Open https://$DOMAIN  (API docs: https://$DOMAIN/api/docs)"
