#!/bin/sh
set -eu

SOURCE=/var/lib/zigbee2mqtt
TARGET=/var/backups/kyrion/zigbee
STAMP=${1:-initial-network}

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this script with sudo." >&2
  exit 1
fi
if [ ! -f "$SOURCE/coordinator_backup.json" ]; then
  echo "Coordinator backup is not available yet." >&2
  exit 1
fi

install -d -o root -g root -m 0700 "$TARGET/$STAMP"
install -o root -g root -m 0600 "$SOURCE/coordinator_backup.json" \
  "$TARGET/$STAMP/coordinator_backup.json"
install -o root -g root -m 0600 "$SOURCE/configuration.yaml" \
  "$TARGET/$STAMP/configuration.yaml"
if [ -f "$SOURCE/database.db" ]; then
  install -o root -g root -m 0600 "$SOURCE/database.db" "$TARGET/$STAMP/database.db"
fi
echo "Zigbee snapshot stored at $TARGET/$STAMP"
