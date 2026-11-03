#!/bin/sh
# Install an nginx reverse-proxy site for FreqUI.
# Usage: install.sh <domain> [upstream_port] [auth_user] [auth_password]
set -eu

DOMAIN="${1:-}"
PORT="${2:-18080}"
AUTH_USER="${3:-}"
AUTH_PASSWORD="${4:-}"

if [ -z "$DOMAIN" ]; then
  echo "usage: $0 <domain> [port] [auth_user] [auth_password]" >&2
  exit 2
fi
if ! printf '%s' "$DOMAIN" | grep -Eq '^[A-Za-z0-9.-]+$'; then
  echo "invalid domain: $DOMAIN" >&2
  exit 2
fi
if ! printf '%s' "$PORT" | grep -Eq '^[0-9]+$'; then
  echo "invalid port: $PORT" >&2
  exit 2
fi

SITES_AVAILABLE=/etc/nginx/sites-available
SITES_ENABLED=/etc/nginx/sites-enabled
NAME="mycryptotrader-${DOMAIN}"
CONF="${SITES_AVAILABLE}/${NAME}.conf"
LINK="${SITES_ENABLED}/${NAME}.conf"
HTPASSWD=/etc/nginx/.htpasswd-mycryptotrader

if [ ! -d "$SITES_AVAILABLE" ]; then
  echo "$SITES_AVAILABLE not found (Debian/Ubuntu nginx expected)" >&2
  exit 1
fi
mkdir -p "$SITES_ENABLED"

AUTH_LINES=""
if [ -n "$AUTH_USER" ] && [ -n "$AUTH_PASSWORD" ]; then
  printf '%s:%s\n' "$AUTH_USER" "$(openssl passwd -apr1 "$AUTH_PASSWORD")" > "$HTPASSWD"
  chmod 640 "$HTPASSWD"
  chown root:www-data "$HTPASSWD" 2>/dev/null || true
  AUTH_LINES="auth_basic \"myCryptoTrader\";
        auth_basic_user_file $HTPASSWD;"
else
  echo "WARNING: nginx basic auth is disabled." >&2
  echo "         Change the FreqUI password before exposing this UI publicly." >&2
fi

BACKUP=""
if [ -f "$CONF" ]; then
  BACKUP="$(mktemp)"
  cp "$CONF" "$BACKUP"
fi

cat > "$CONF" <<EOF
# Managed by myCryptoTrader. Regenerate with: make nginx DOMAIN=$DOMAIN
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        $AUTH_LINES
        proxy_pass http://127.0.0.1:$PORT;

        proxy_http_version 1.1;

        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # FreqUI live updates (WebSocket)
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

ln -sfn "$CONF" "$LINK"

if ! nginx -t; then
  rm -f "$LINK"
  if [ -n "$BACKUP" ]; then
    cp "$BACKUP" "$CONF"
  else
    rm -f "$CONF"
  fi
  echo "nginx -t failed; changes rolled back" >&2
  exit 1
fi

systemctl reload nginx

case "$DOMAIN" in
  *.local|*.internal|*.lan|*.home.arpa)
    cat <<EOF
Enabled: http://$DOMAIN -> 127.0.0.1:$PORT
Local domain detected: add "<server-ip> $DOMAIN" to the hosts file on each client.
HTTPS: Let's Encrypt cannot issue for $DOMAIN; use a real domain or mkcert/self-signed.
EOF
    ;;
  *)
    cat <<EOF
Enabled: http://$DOMAIN -> 127.0.0.1:$PORT
Next:
  1) point DNS A/AAAA record for $DOMAIN to this server
  2) make nginx-tls DOMAIN=$DOMAIN EMAIL=you@example.com
EOF
    ;;
esac
