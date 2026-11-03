#!/bin/sh
# Remove the nginx site created by install.sh.
# Usage: remove.sh <domain>
set -eu

DOMAIN="${1:-}"
if [ -z "$DOMAIN" ]; then
  echo "usage: $0 <domain>" >&2
  exit 2
fi

NAME="mycryptotrader-${DOMAIN}"
rm -f "/etc/nginx/sites-enabled/${NAME}.conf"
rm -f "/etc/nginx/sites-available/${NAME}.conf"

nginx -t
systemctl reload nginx
echo "Removed nginx site for $DOMAIN"
