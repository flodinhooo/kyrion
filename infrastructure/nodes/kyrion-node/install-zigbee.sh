#!/bin/sh
set -eu

Z2M_VERSION=2.10.1
Z2M_ROOT=/opt/zigbee2mqtt
Z2M_DATA=/var/lib/zigbee2mqtt
Z2M_USER=zigbee2mqtt
ADAPTER=/dev/serial/by-id/usb-Itead_Sonoff_Zigbee_3.0_USB_Dongle_Plus_V2_3a2eabb8d8ffef11ba3e91256d9880ab-if00-port0

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this script with sudo." >&2
  exit 1
fi
if [ ! -e "$ADAPTER" ]; then
  echo "The expected Sonoff Zigbee adapter is not attached." >&2
  exit 1
fi

apt-get update
apt-get install -y ca-certificates curl gnupg git make g++ gcc libsystemd-dev mosquitto mosquitto-clients
install -d -m 0755 /etc/apt/keyrings
curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
  | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" \
  > /etc/apt/sources.list.d/nodesource.list
apt-get update
apt-get install -y nodejs

if ! id "$Z2M_USER" >/dev/null 2>&1; then
  useradd --system --home-dir "$Z2M_DATA" --shell /usr/sbin/nologin "$Z2M_USER"
fi
usermod -a -G dialout "$Z2M_USER"

install -d -o root -g root -m 0755 "$Z2M_ROOT"
install -d -o "$Z2M_USER" -g "$Z2M_USER" -m 0750 "$Z2M_DATA"

if [ ! -d "$Z2M_ROOT/.git" ]; then
  git clone --branch "$Z2M_VERSION" --depth 1 https://github.com/Koenkk/zigbee2mqtt.git "$Z2M_ROOT"
fi
git -C "$Z2M_ROOT" fetch --depth 1 origin "refs/tags/$Z2M_VERSION:refs/tags/$Z2M_VERSION"
git -C "$Z2M_ROOT" checkout --detach "$Z2M_VERSION"

npm install --global corepack@0.34.0
corepack enable
cd "$Z2M_ROOT"
pnpm install --frozen-lockfile
pnpm run prepack

cat > /etc/mosquitto/conf.d/kyrion-local.conf <<'EOF'
listener 1883 127.0.0.1
allow_anonymous true
persistence true
EOF

cat > "$Z2M_DATA/configuration.yaml" <<EOF
version: 5
mqtt:
  base_topic: zigbee2mqtt
  server: mqtt://127.0.0.1:1883
serial:
  port: $ADAPTER
  adapter: ember
  rtscts: false
advanced:
  channel: 15
  network_key: GENERATE
  pan_id: GENERATE
  ext_pan_id: GENERATE
  log_output:
    - console
frontend:
  enabled: false
homeassistant:
  enabled: false
permit_join: false
EOF
chown "$Z2M_USER:$Z2M_USER" "$Z2M_DATA/configuration.yaml"
chmod 0600 "$Z2M_DATA/configuration.yaml"

cat > /etc/systemd/system/zigbee2mqtt.service <<'EOF'
[Unit]
Description=Kyrion Zigbee2MQTT adapter
After=mosquitto.service network.target
Requires=mosquitto.service

[Service]
Type=notify
User=zigbee2mqtt
Group=zigbee2mqtt
SupplementaryGroups=dialout
WorkingDirectory=/opt/zigbee2mqtt
Environment=NODE_ENV=production
Environment=ZIGBEE2MQTT_DATA=/var/lib/zigbee2mqtt
ExecStart=/usr/bin/node index.js
Restart=on-failure
RestartSec=10s
WatchdogSec=30s
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
ReadWritePaths=/var/lib/zigbee2mqtt
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
LockPersonality=true

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now mosquitto.service
systemctl enable --now zigbee2mqtt.service
