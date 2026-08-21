#!/bin/sh
set -eu

MATTER_DATA=/var/lib/matter-server
MATTER_CONFIG=/etc/kyrion-matter-server
MATTER_IMAGE=ghcr.io/matter-js/matterjs-server:stable

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this script with sudo." >&2
  exit 1
fi
if docker container inspect matter-server >/dev/null 2>&1; then
  echo "A Matter Server container already exists; refusing to replace it." >&2
  exit 1
fi
if [ "$(docker exec otbr ot-ctl state | sed -n '1p' | tr -d '\r')" != "leader" ]; then
  echo "The accepted OTBR is not the Thread leader." >&2
  exit 1
fi

install -d -o 1000 -g 1000 -m 0700 "$MATTER_DATA"
install -d -o root -g root -m 0700 "$MATTER_CONFIG"
cat > "$MATTER_CONFIG/matter.env" <<'EOF'
STORAGE_PATH=/data
PRIMARY_INTERFACE=eth0
LISTEN_ADDRESS=127.0.0.1
PORT=5580
LOG_LEVEL=info
PRODUCTION_MODE=true
EOF
chmod 0600 "$MATTER_CONFIG/matter.env"

docker pull "$MATTER_IMAGE"
MATTER_DIGEST=$(docker image inspect --format '{{index .RepoDigests 0}}' "$MATTER_IMAGE")
printf '%s\n' "$MATTER_DIGEST" > "$MATTER_CONFIG/image-digest.txt"
chmod 0600 "$MATTER_CONFIG/image-digest.txt"

docker run --name matter-server --detach \
  --restart unless-stopped \
  --network host \
  --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=128m \
  --cap-drop ALL \
  --security-opt no-new-privileges=true \
  --volume="$MATTER_DATA:/data" \
  --env-file="$MATTER_CONFIG/matter.env" \
  "$MATTER_DIGEST"

docker ps --filter name=matter-server
