#!/bin/sh
set -eu

STAGE_DIR=${1:?Pass the staged update directory}
PLATFORM_DIR=/etc/kyrion/platform
ENV_FILE=$PLATFORM_DIR/platform.env
COMPOSE_FILE=$PLATFORM_DIR/compose.yml
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP_DIR=/var/backups/kyrion/platform-$TIMESTAMP

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo." >&2
  exit 1
fi
for required in "$STAGE_DIR/infrastructure/nodes/kyrion-node/compose.platform.yml" "$STAGE_DIR/spotify.env"; do
  [ -f "$required" ] || { echo "Missing $required" >&2; exit 1; }
done
grep -q '^KYRION_SPOTIFY_CLIENT_ID=.' "$STAGE_DIR/spotify.env" || { echo "Spotify client ID is missing." >&2; exit 1; }
grep -q '^KYRION_SPOTIFY_CLIENT_SECRET=.' "$STAGE_DIR/spotify.env" || { echo "Spotify client secret is missing." >&2; exit 1; }
grep -q '^KYRION_SPOTIFY_REDIRECT_URI=https://' "$STAGE_DIR/spotify.env" || { echo "Spotify HTTPS redirect URI is missing." >&2; exit 1; }

install -d -o root -g root -m 0700 "$BACKUP_DIR"
install -o root -g root -m 0600 "$ENV_FILE" "$BACKUP_DIR/platform.env"
install -o root -g root -m 0644 "$COMPOSE_FILE" "$BACKUP_DIR/compose.platform.yml"

# Preserve the current images as an explicit local rollback point.
docker image tag kyrion/core:pi-local kyrion/core:spotify-rollback-$TIMESTAMP
docker image tag kyrion/web:pi-local kyrion/web:spotify-rollback-$TIMESTAMP

docker-compose --env-file "$ENV_FILE" -f "$STAGE_DIR/infrastructure/nodes/kyrion-node/compose.platform.yml" build core web

install -o root -g root -m 0644 "$STAGE_DIR/infrastructure/nodes/kyrion-node/compose.platform.yml" "$COMPOSE_FILE"
grep -v '^KYRION_SPOTIFY_' "$ENV_FILE" > "$ENV_FILE.tmp"
cat "$STAGE_DIR/spotify.env" >> "$ENV_FILE.tmp"
chown root:root "$ENV_FILE.tmp"
chmod 0600 "$ENV_FILE.tmp"
mv "$ENV_FILE.tmp" "$ENV_FILE"

if ! docker-compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --no-build core web caddy; then
  docker image tag kyrion/core:spotify-rollback-$TIMESTAMP kyrion/core:pi-local
  docker image tag kyrion/web:spotify-rollback-$TIMESTAMP kyrion/web:pi-local
  docker-compose --env-file "$BACKUP_DIR/platform.env" -f "$BACKUP_DIR/compose.platform.yml" up -d --no-build core web caddy
  echo "Update failed and the previous images were restored." >&2
  exit 1
fi

attempt=0
until curl --fail --silent http://127.0.0.1:18080/actuator/health >/dev/null && curl --fail --silent http://127.0.0.1:3000/ >/dev/null; do
  attempt=$((attempt + 1))
  [ "$attempt" -lt 30 ] || { echo "Updated services did not become healthy; inspect logs and use $BACKUP_DIR for rollback." >&2; exit 1; }
  sleep 5
done

echo "Spotify platform update is healthy. Backup: $BACKUP_DIR"
