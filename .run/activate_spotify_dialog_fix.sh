#!/bin/sh
set -eu

STAGE_DIR=${1:?Pass the staged update directory}
PLATFORM_DIR=/etc/kyrion/platform
ENV_FILE=$PLATFORM_DIR/platform.env
COMPOSE_FILE=$PLATFORM_DIR/compose.yml
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
ROLLBACK_IMAGE=kyrion/web:spotify-dialog-rollback-$TIMESTAMP

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo." >&2
  exit 1
fi

docker image tag kyrion/web:pi-local "$ROLLBACK_IMAGE"

rollback() {
  docker image tag "$ROLLBACK_IMAGE" kyrion/web:pi-local
  docker-compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --no-build --force-recreate web caddy
  echo "Web update failed and the previous image was restored." >&2
  exit 1
}

docker-compose --env-file "$ENV_FILE" -f "$STAGE_DIR/infrastructure/nodes/kyrion-node/compose.platform.yml" build web || rollback
install -o root -g root -m 0644 "$STAGE_DIR/infrastructure/nodes/kyrion-node/compose.platform.yml" "$COMPOSE_FILE"
docker-compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --no-build --force-recreate web caddy || rollback

attempt=0
until curl --fail --silent http://127.0.0.1:3000/ >/dev/null; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    rollback
  fi
  sleep 2
done

echo "Spotify dialog fix is live. Rollback image: $ROLLBACK_IMAGE"
