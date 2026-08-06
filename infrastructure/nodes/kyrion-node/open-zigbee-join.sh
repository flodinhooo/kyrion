#!/bin/sh
set -eu

DURATION=${1:-180}
case "$DURATION" in
  *[!0-9]*|'') echo "Duration must be numeric." >&2; exit 1 ;;
esac
if [ "$DURATION" -lt 1 ] || [ "$DURATION" -gt 254 ]; then
  echo "Duration must be between 1 and 254 seconds." >&2
  exit 1
fi

mosquitto_pub -h 127.0.0.1 \
  -t zigbee2mqtt/bridge/request/permit_join \
  -m "{\"value\":true,\"time\":$DURATION}"
echo "Zigbee joining requested for $DURATION seconds."
