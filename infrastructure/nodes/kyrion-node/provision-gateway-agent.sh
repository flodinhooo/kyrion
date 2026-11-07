#!/bin/sh
set -eu

STAGED_SOURCE=/tmp/kyrion-gateway-agent
INSTALL_ROOT=/opt/kyrion-gateway
CONFIG_ROOT=/etc/kyrion-gateway
STATE_ROOT=/var/lib/kyrion-gateway
SERVICE_USER=kyrion-gateway

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this script with sudo." >&2
  exit 1
fi

if [ ! -f "$STAGED_SOURCE/src/kyrion_gateway_agent/cli.py" ]; then
  echo "Staged gateway-agent source is missing." >&2
  exit 1
fi

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --home-dir "$STATE_ROOT" --shell /usr/sbin/nologin "$SERVICE_USER"
fi

install -d -o root -g root -m 0755 "$INSTALL_ROOT"
install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0750 "$CONFIG_ROOT" "$STATE_ROOT"
cp -R "$STAGED_SOURCE/src" "$INSTALL_ROOT/"
chown -R root:root "$INSTALL_ROOT/src"
find "$INSTALL_ROOT/src" -type d -exec chmod 0755 {} \;
find "$INSTALL_ROOT/src" -type f -exec chmod 0644 {} \;

install -o root -g root -m 0644 \
  "$STAGED_SOURCE/kyrion-gateway-agent.service" \
  /etc/systemd/system/kyrion-gateway-agent.service

systemctl daemon-reload
echo "Kyrion gateway agent files were provisioned. Enrollment is still required."
