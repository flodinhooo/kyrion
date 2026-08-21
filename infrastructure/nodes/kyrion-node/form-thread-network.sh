#!/bin/sh
set -eu

BACKUP_DIR=/var/backups/kyrion/thread/active

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this script with sudo." >&2
  exit 1
fi
if [ "$(docker exec otbr ot-ctl state | tr -d '\r')" != "disabled
Done" ]; then
  echo "OTBR is not in the expected disabled state; refusing to replace a network." >&2
  exit 1
fi

docker exec otbr ot-ctl dataset init new
docker exec otbr ot-ctl dataset networkname Kyrion-Thread
docker exec otbr ot-ctl dataset channel 25
docker exec otbr ot-ctl dataset commit active
docker exec otbr ot-ctl thread start

attempt=0
state=disabled
while [ "$attempt" -lt 30 ]; do
  state=$(docker exec otbr ot-ctl state | sed -n '1p' | tr -d '\r')
  case "$state" in
    leader|router|child) break ;;
  esac
  attempt=$((attempt + 1))
  sleep 1
done
case "$state" in
  leader|router|child) ;;
  *) echo "Thread did not attach; current state: $state" >&2; exit 1 ;;
esac

install -d -o root -g root -m 0700 "$BACKUP_DIR"
docker exec otbr ot-ctl dataset active -x \
  | sed -n '1p' \
  | tr -d '\r' \
  > "$BACKUP_DIR/dataset.hex"
chmod 0600 "$BACKUP_DIR/dataset.hex"
tar -C /var/lib -czf "$BACKUP_DIR/otbr-data.tar.gz" otbr
chmod 0600 "$BACKUP_DIR/otbr-data.tar.gz"

printf 'state=%s\n' "$state"
docker exec otbr ot-ctl networkname
docker exec otbr ot-ctl channel
