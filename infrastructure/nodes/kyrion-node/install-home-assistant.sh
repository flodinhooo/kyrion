#!/bin/sh
set -eu

HA_IMAGE=ghcr.io/home-assistant/home-assistant:stable
HA_CONFIG=/var/lib/homeassistant

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this script with sudo." >&2
  exit 1
fi
if ! systemctl is-active --quiet docker.service; then
  echo "Docker must be active before installing Home Assistant." >&2
  exit 1
fi
if docker container inspect homeassistant >/dev/null 2>&1; then
  if [ "$(docker inspect --format '{{.State.Running}}' homeassistant)" = "true" ]; then
    echo "A running Home Assistant container already exists; refusing to replace it." >&2
    exit 1
  fi
  docker rm -f homeassistant
fi

install -d -o root -g root -m 0700 "$HA_CONFIG"
docker pull "$HA_IMAGE"
docker run -d \
  --name homeassistant \
  --restart unless-stopped \
  --network host \
  --read-only \
  --tmpfs /run:rw,exec,nosuid,nodev,size=64m \
  --tmpfs /tmp:rw,nosuid,nodev,size=256m \
  --security-opt no-new-privileges=true \
  --cap-drop ALL \
  -e TZ=Europe/Zurich \
  -v "$HA_CONFIG:/config" \
  -v /etc/localtime:/etc/localtime:ro \
  "$HA_IMAGE"

docker image inspect --format '{{index .RepoDigests 0}}' "$HA_IMAGE"
docker ps --filter name=homeassistant
