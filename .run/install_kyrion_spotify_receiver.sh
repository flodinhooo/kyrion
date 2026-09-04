#!/bin/sh
set -eu

PACKAGE=/home/flodinho/raspotify-latest_arm64.deb
CONFIG=/etc/raspotify/conf

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo." >&2
  exit 1
fi
[ -f "$PACKAGE" ] || { echo "Missing $PACKAGE" >&2; exit 1; }

apt-get install -y "$PACKAGE"
cp -a "$CONFIG" "$CONFIG.kyrion-backup"
sed -i 's/^#LIBRESPOT_BITRATE=.*/LIBRESPOT_BITRATE=320/' "$CONFIG"
sed -i 's/^#LIBRESPOT_DEVICE_TYPE=.*/LIBRESPOT_DEVICE_TYPE=speaker/' "$CONFIG"
sed -i 's/^#LIBRESPOT_NAME=.*/LIBRESPOT_NAME="Kyrion Pi"/' "$CONFIG"
sed -i 's/^#LIBRESPOT_INITIAL_VOLUME=.*/LIBRESPOT_INITIAL_VOLUME=35/' "$CONFIG"

systemctl enable --now raspotify
sleep 3
systemctl is-active --quiet raspotify
echo "Kyrion Pi Spotify Connect receiver is active."
