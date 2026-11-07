#!/bin/sh
set -eu

BUNDLE_DIR=${1:-}
PLATFORM_DIR=/etc/kyrion/platform
POSTGRES_DIR=/var/lib/kyrion/postgres
SECRETS_DIR=/var/lib/kyrion/secrets
CORE_URL=http://127.0.0.1:18080

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this script with sudo and the prepared bundle directory." >&2
  exit 1
fi
if [ -z "$BUNDLE_DIR" ] || [ ! -d "$BUNDLE_DIR" ]; then
  echo "Usage: install-platform.sh BUNDLE_DIR" >&2
  exit 1
fi
for file in compose.platform.yml platform.env kyrion-core-arm64.tar kyrion-web-arm64.tar database.dump credential.key audit-integrity.key; do
  if [ ! -f "$BUNDLE_DIR/$file" ]; then
    echo "Missing required bundle file: $file" >&2
    exit 1
  fi
done
if ! systemctl is-active --quiet docker.service; then
  echo "Docker must be active before installing the platform." >&2
  exit 1
fi
if ! command -v docker-compose >/dev/null 2>&1; then
  echo "docker-compose is required; run install-container-runtime.sh first." >&2
  exit 1
fi
if ss -ltn | grep -q ':3000 '; then
  echo "Port 3000 is already in use; refusing to replace the existing listener." >&2
  exit 1
fi
if ss -ltn | grep -q ':18080 '; then
  echo "Port 18080 is already in use; refusing to replace the existing listener." >&2
  exit 1
fi
if [ -d "$POSTGRES_DIR" ] && [ "$(find "$POSTGRES_DIR" -mindepth 1 -maxdepth 1 | head -n 1)" ]; then
  echo "PostgreSQL target is not empty; refusing an implicit overwrite." >&2
  exit 1
fi

install -d -o root -g root -m 0700 "$PLATFORM_DIR"
install -d -o root -g root -m 0750 /var/lib/kyrion
install -d -o 10001 -g 10001 -m 0700 "$SECRETS_DIR"
install -d -o root -g root -m 0700 "$POSTGRES_DIR"
install -o root -g root -m 0644 "$BUNDLE_DIR/compose.platform.yml" "$PLATFORM_DIR/compose.yml"
install -o root -g root -m 0600 "$BUNDLE_DIR/platform.env" "$PLATFORM_DIR/platform.env"
install -o 10001 -g 10001 -m 0600 "$BUNDLE_DIR/credential.key" "$SECRETS_DIR/credential.key"
install -o 10001 -g 10001 -m 0600 "$BUNDLE_DIR/audit-integrity.key" "$SECRETS_DIR/audit-integrity.key"

docker load --input "$BUNDLE_DIR/kyrion-core-arm64.tar"
docker load --input "$BUNDLE_DIR/kyrion-web-arm64.tar"

compose() {
  docker-compose --env-file "$PLATFORM_DIR/platform.env" -f "$PLATFORM_DIR/compose.yml" "$@"
}

compose up -d postgres
attempt=0
until compose exec -T postgres pg_isready -U kyrion -d kyrion >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 24 ]; then
    echo "PostgreSQL did not become ready." >&2
    exit 1
  fi
  sleep 5
done
compose exec -T postgres pg_restore --exit-on-error --no-owner --no-acl --username=kyrion --dbname=kyrion < "$BUNDLE_DIR/database.dump"
compose up -d --no-build core web

attempt=0
until curl --fail --silent "$CORE_URL/actuator/health" >/dev/null; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 24 ]; then
    compose logs --tail=100 core
    echo "Kyrion Core did not become healthy; gateway configuration was not changed." >&2
    exit 1
  fi
  sleep 5
done
curl --fail --silent http://127.0.0.1:3000/ >/dev/null

if [ -f /etc/kyrion-gateway/agent.json ]; then
  backup_dir=/var/backups/kyrion/"$(date -u +%Y%m%dT%H%M%SZ)"
  install -d -o root -g root -m 0700 "$backup_dir"
  install -o root -g root -m 0600 /etc/kyrion-gateway/agent.json "$backup_dir/agent.json"
  python3 - /etc/kyrion-gateway/agent.json "$CORE_URL" <<'PY'
import json
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
current = path.stat()
value = json.loads(path.read_text(encoding="utf-8"))
value["core_url"] = sys.argv[2]
temporary = path.with_suffix(".tmp")
temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
os.chown(temporary, current.st_uid, current.st_gid)
os.chmod(temporary, current.st_mode & 0o777)
os.replace(temporary, path)
PY
  systemctl restart kyrion-gateway-agent.service
fi

compose ps
curl --fail --silent "$CORE_URL/actuator/health"
echo
echo "Kyrion Web is available on port 3000. OTBR on port 8080 was not changed."
