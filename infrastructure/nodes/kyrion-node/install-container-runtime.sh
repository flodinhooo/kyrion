#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this script with sudo." >&2
  exit 1
fi

apt-get update
apt-get install -y docker.io

systemctl enable --now docker.service

docker version
systemctl --no-pager --full status docker.service
