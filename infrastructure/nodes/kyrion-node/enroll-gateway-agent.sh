#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this script with sudo." >&2
  exit 1
fi

if [ "$#" -ne 2 ]; then
  echo "Usage: enroll-gateway-agent.sh CORE_URL ENROLLMENT_TOKEN" >&2
  exit 1
fi

CORE_URL=$1
ENROLLMENT_TOKEN=$2

runuser -u kyrion-gateway -- env PYTHONPATH=/opt/kyrion-gateway/src \
  python3 -m kyrion_gateway_agent.cli \
  --config /etc/kyrion-gateway/agent.json \
  enroll --core-url "$CORE_URL" --token "$ENROLLMENT_TOKEN"

systemctl enable --now kyrion-gateway-agent.service
echo "Kyrion gateway agent enrolled and started."
