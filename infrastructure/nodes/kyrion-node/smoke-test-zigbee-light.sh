#!/bin/sh
set -eu

DEVICE=${1:?Pass the paired Zigbee device identifier.}
mosquitto_pub -h 127.0.0.1 -t zigbee2mqtt/bridge/request/permit_join -m '{"value":false,"time":0}'
mosquitto_pub -h 127.0.0.1 -t "zigbee2mqtt/$DEVICE/set" -m '{"state":"OFF"}'
sleep 2
mosquitto_pub -h 127.0.0.1 -t "zigbee2mqtt/$DEVICE/set" -m '{"state":"ON"}'
echo "Pairing closed and reversible power smoke test requested."
