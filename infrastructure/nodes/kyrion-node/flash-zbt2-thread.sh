#!/bin/sh
set -eu

DEVICE=/dev/ttyACM0
BACKUP_DIR=/var/backups/kyrion/thread/zbt2-pre-thread-20260821
FIRMWARE=zbt2_openthread_rcp_2.7.2.0_GitHub-fb0446f53_gsdk_2025.6.2.gbl
IMAGE=ghcr.io/home-assistant/home-assistant@sha256:56690a89c79a0de98035e1719f8324a92d5859c1192ff45adb0230ea81cb42a5

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this script with sudo." >&2
  exit 1
fi
if [ ! -e /dev/serial/by-id/usb-Nabu_Casa_ZBT-2_94A990D05658-if00 ]; then
  echo "The accepted ZBT-2 is not attached." >&2
  exit 1
fi
if fuser "$DEVICE" >/dev/null 2>&1; then
  echo "$DEVICE is in use; refusing to flash." >&2
  exit 1
fi
[ "$(sha256sum "$BACKUP_DIR/$FIRMWARE" | awk '{print $1}')" = "431500fd4399a45c8a7910262762562fa13ae02fe18b546531a3c2d14fc39d96" ] || {
  echo "Thread firmware checksum mismatch." >&2
  exit 1
}

docker run --rm \
  --device="$DEVICE:$DEVICE" \
  -v "$BACKUP_DIR:/firmware:ro" \
  --entrypoint universal-silabs-flasher \
  "$IMAGE" \
  --device "$DEVICE" \
  flash --profile zbt2 --firmware "/firmware/$FIRMWARE"

docker run --rm \
  --device="$DEVICE:$DEVICE" \
  --entrypoint universal-silabs-flasher \
  "$IMAGE" \
  --device "$DEVICE" \
  --probe-methods spinel:460800 \
  probe
