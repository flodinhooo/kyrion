#!/bin/sh
set -eu

UNIT_SOURCE=/home/flodinho/kyrion-spotify-receiver.service
UNIT_DIR=/home/flodinho/.config/systemd/user

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo." >&2
  exit 1
fi

systemctl disable --now raspotify
loginctl enable-linger flodinho
install -d -o flodinho -g flodinho -m 0755 "$UNIT_DIR"
install -o flodinho -g flodinho -m 0644 "$UNIT_SOURCE" "$UNIT_DIR/kyrion-spotify-receiver.service"

runuser -u flodinho -- env XDG_RUNTIME_DIR=/run/user/1000 systemctl --user daemon-reload
runuser -u flodinho -- env XDG_RUNTIME_DIR=/run/user/1000 systemctl --user enable --now kyrion-spotify-receiver.service
sleep 3
runuser -u flodinho -- env XDG_RUNTIME_DIR=/run/user/1000 systemctl --user is-active --quiet kyrion-spotify-receiver.service
echo "Kyrion Pi now uses the PipeWire Bluetooth audio output."
