#!/bin/sh
set -eu

BUNDLE_DIR=${1:-}
PLATFORM_DIR=/etc/kyrion/platform
TLS_DIR=$PLATFORM_DIR/tls
CERTIFICATE=$TLS_DIR/server.crt
PRIVATE_KEY=$TLS_DIR/server.key

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this script with sudo and the prepared HTTPS bundle directory." >&2
  exit 1
fi
if [ -z "$BUNDLE_DIR" ] || [ ! -f "$BUNDLE_DIR/compose.platform.yml" ] || [ ! -f "$BUNDLE_DIR/Caddyfile" ]; then
  echo "Usage: pin-platform-certificate.sh HTTPS_BUNDLE_DIR" >&2
  exit 1
fi
if ! command -v openssl >/dev/null 2>&1; then
  echo "OpenSSL is required to create the pinned local server certificate." >&2
  exit 1
fi

install -d -o root -g root -m 0700 "$TLS_DIR"
if [ ! -f "$CERTIFICATE" ] || [ ! -f "$PRIVATE_KEY" ]; then
  openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 397 \
    -subj "/CN=kyrion-node.local/O=Kyrion Local" \
    -addext "subjectAltName=DNS:kyrion-node.local,IP:192.168.1.116" \
    -addext "basicConstraints=critical,CA:FALSE" \
    -addext "keyUsage=critical,digitalSignature,keyEncipherment" \
    -addext "extendedKeyUsage=serverAuth" \
    -keyout "$PRIVATE_KEY" -out "$CERTIFICATE"
  chmod 0600 "$PRIVATE_KEY"
  chmod 0644 "$CERTIFICATE"
fi

install -o root -g root -m 0644 "$BUNDLE_DIR/Caddyfile" "$PLATFORM_DIR/Caddyfile"
install -o root -g root -m 0644 "$BUNDLE_DIR/compose.platform.yml" "$PLATFORM_DIR/compose.yml"

docker-compose --env-file "$PLATFORM_DIR/platform.env" -f "$PLATFORM_DIR/compose.yml" up -d --no-build caddy
attempt=0
until curl --fail --silent --cacert "$CERTIFICATE" https://kyrion-node.local/ >/dev/null; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 12 ]; then
    docker-compose --env-file "$PLATFORM_DIR/platform.env" -f "$PLATFORM_DIR/compose.yml" logs --tail=100 caddy
    echo "Pinned Kyrion HTTPS certificate did not become healthy." >&2
    exit 1
  fi
  sleep 5
done

export_user=${SUDO_USER:-root}
export_home=$(getent passwd "$export_user" | cut -d: -f6)
install -o "$export_user" -g "$export_user" -m 0644 "$CERTIFICATE" "$export_home/kyrion-server.crt"
echo "Pinned public server certificate: $export_home/kyrion-server.crt"
echo "Renew before: $(openssl x509 -in "$CERTIFICATE" -noout -enddate | cut -d= -f2-)"
