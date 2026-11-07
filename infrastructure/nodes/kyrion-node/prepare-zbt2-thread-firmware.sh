#!/bin/sh
set -eu

RELEASE=v2026.02.23
RELEASE_URL="https://github.com/NabuCasa/silabs-firmware-builder/releases/download/$RELEASE"
BACKUP_DIR=/var/backups/kyrion/thread/zbt2-pre-thread-20260821
ZIGBEE=zbt2_zigbee_ncp_7.5.1.0_None.gbl
THREAD=zbt2_openthread_rcp_2.7.2.0_GitHub-fb0446f53_gsdk_2025.6.2.gbl
MANIFEST=manifest.json

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this script with sudo." >&2
  exit 1
fi

install -d -o root -g root -m 0700 "$BACKUP_DIR"
for artifact in "$MANIFEST" "$ZIGBEE" "$THREAD"; do
  curl -fsSL "$RELEASE_URL/$artifact" -o "$BACKUP_DIR/$artifact"
  chmod 0600 "$BACKUP_DIR/$artifact"
done

check_sha3() {
  expected=$1
  file=$2
  actual=$(openssl dgst -sha3-256 "$file" | awk '{print $2}')
  [ "$actual" = "$expected" ] || {
    echo "SHA3-256 mismatch for $file" >&2
    exit 1
  }
}

[ "$(sha256sum "$BACKUP_DIR/$MANIFEST" | awk '{print $1}')" = "a050323158d3cd7cce745a15948539b2d05a567a98beac71554ea59dbea81eb7" ] || {
  echo "SHA-256 mismatch for $MANIFEST" >&2
  exit 1
}
check_sha3 6a2c18980ee795dac2fd4aa101a8093845f314055df997f2f7ee49eed74ea0b7 "$BACKUP_DIR/$ZIGBEE"
check_sha3 8a7bb812d8043025e271da7e9983b45d023af10153443b9616494a15ee2035c3 "$BACKUP_DIR/$THREAD"

thread_sha256=$(sha256sum "$BACKUP_DIR/$THREAD" | awk '{print $1}')
[ "$thread_sha256" = "431500fd4399a45c8a7910262762562fa13ae02fe18b546531a3c2d14fc39d96" ] || {
  echo "SHA-256 mismatch for $THREAD" >&2
  exit 1
}

cat > "$BACKUP_DIR/restore-manifest.txt" <<EOF
prepared_at=2026-08-21
release=$RELEASE
device=/dev/serial/by-id/usb-Nabu_Casa_ZBT-2_94A990D05658-if00
usb_vendor_product=303a:831a
detected_firmware=EmberZNet 7.5.1.0 build 0 (20260224005837)
detected_baudrate=460800
restore_firmware=$ZIGBEE
target_firmware=$THREAD
target_sha256=$thread_sha256
EOF
chmod 0600 "$BACKUP_DIR/restore-manifest.txt"

sha256sum "$BACKUP_DIR"/*
