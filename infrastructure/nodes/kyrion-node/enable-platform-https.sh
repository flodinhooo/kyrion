#!/bin/sh
set -eu

BUNDLE_DIR=${1:-}
PLATFORM_DIR=/etc/kyrion/platform
CADDY_STATE=/var/lib/kyrion/caddy
TLS_DIR=$PLATFORM_DIR/tls
CERTIFICATE=$TLS_DIR/server.crt
PRIVATE_KEY=$TLS_DIR/server.key

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this script with sudo and the prepared HTTPS bundle directory." >&2
  exit 1
fi
if [ -z "$BUNDLE_DIR" ] || [ ! -d "$BUNDLE_DIR" ]; then
  echo "Usage: enable-platform-https.sh BUNDLE_DIR" >&2
  exit 1
fi
for file in compose.platform.yml Caddyfile caddy-arm64.tar; do
  if [ ! -f "$BUNDLE_DIR/$file" ]; then
    echo "Missing required HTTPS bundle file: $file" >&2
    exit 1
  fi
done
for file in "$PLATFORM_DIR/platform.env" "$PLATFORM_DIR/compose.yml"; do
  if [ ! -f "$file" ]; then
    echo "The existing Kyrion platform installation is incomplete: $file" >&2
    exit 1
  fi
done
if ss -ltn | grep -q ':443 '; then
  echo "Port 443 is already in use; refusing to replace the existing listener." >&2
  exit 1
fi

install -d -o root -g root -m 0750 "$CADDY_STATE/data" "$CADDY_STATE/config"
install -d -o root -g root -m 0700 "$TLS_DIR"
openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 397 \
  -subj "/CN=kyrion-node.local/O=Kyrion Local" \
  -addext "subjectAltName=DNS:kyrion-node.local,IP:192.168.1.116" \
  -addext "basicConstraints=critical,CA:FALSE" \
  -addext "keyUsage=critical,digitalSignature,keyEncipherment" \
  -addext "extendedKeyUsage=serverAuth" \
  -keyout "$PRIVATE_KEY" -out "$CERTIFICATE"
chmod 0600 "$PRIVATE_KEY"
chmod 0644 "$CERTIFICATE"
install -o root -g root -m 0644 "$BUNDLE_DIR/Caddyfile" "$PLATFORM_DIR/Caddyfile"
install -o root -g root -m 0644 "$BUNDLE_DIR/compose.platform.yml" "$PLATFORM_DIR/compose.yml"
docker load --input "$BUNDLE_DIR/caddy-arm64.tar"

compose() {
  docker-compose --env-file "$PLATFORM_DIR/platform.env" -f "$PLATFORM_DIR/compose.yml" "$@"
}

compose up -d --no-build web caddy
attempt=0
until curl --fail --silent --cacert "$CERTIFICATE" https://kyrion-node.local/ >/dev/null; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 24 ]; then
    compose logs --tail=100 web caddy
    echo "Kyrion HTTPS did not become healthy." >&2
    exit 1
  fi
  sleep 5
done

export_user=${SUDO_USER:-root}
export_home=$(getent passwd "$export_user" | cut -d: -f6)
install -o "$export_user" -g "$export_user" -m 0644 "$CERTIFICATE" "$export_home/kyrion-server.crt"

compose ps
echo "Kyrion HTTPS is ready at https://kyrion-node.local/"
echo "Pinned public server certificate: $export_home/kyrion-server.crt"
