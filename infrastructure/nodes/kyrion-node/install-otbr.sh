#!/bin/sh
set -eu

DEVICE=/dev/ttyACM0
DEVICE_ID=/dev/serial/by-id/usb-Nabu_Casa_ZBT-2_94A990D05658-if00
OTBR_CONFIG=/etc/kyrion-otbr
OTBR_DATA=/var/lib/otbr
OTBR_IMAGE=openthread/border-router:latest

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this script with sudo." >&2
  exit 1
fi
if [ ! -e "$DEVICE_ID" ] || [ ! -e /dev/net/tun ]; then
  echo "The accepted ZBT-2 or /dev/net/tun is unavailable." >&2
  exit 1
fi
if docker container inspect otbr >/dev/null 2>&1; then
  echo "An OTBR container already exists; refusing to replace it." >&2
  exit 1
fi

install -d -o root -g root -m 0700 "$OTBR_CONFIG" "$OTBR_DATA"
cat > "$OTBR_CONFIG/pre-install-sysctl.txt" <<EOF
net.ipv4.ip_forward=$(/usr/sbin/sysctl -n net.ipv4.ip_forward)
net.ipv6.conf.all.forwarding=$(/usr/sbin/sysctl -n net.ipv6.conf.all.forwarding)
net.ipv6.conf.eth0.accept_ra=$(/usr/sbin/sysctl -n net.ipv6.conf.eth0.accept_ra)
net.ipv6.conf.eth0.accept_ra_rt_info_max_plen=$(/usr/sbin/sysctl -n net.ipv6.conf.eth0.accept_ra_rt_info_max_plen)
EOF
chmod 0600 "$OTBR_CONFIG/pre-install-sysctl.txt"

cat > /etc/sysctl.d/60-kyrion-otbr.conf <<'EOF'
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
net.ipv6.conf.eth0.accept_ra = 2
net.ipv6.conf.eth0.accept_ra_rt_info_max_plen = 64
EOF
/usr/sbin/sysctl --system

cat > "$OTBR_CONFIG/otbr.env" <<'EOF'
OT_RCP_DEVICE=spinel+hdlc+uart:///dev/ttyACM0?uart-baudrate=460800
OT_INFRA_IF=eth0
OT_THREAD_IF=wpan0
OT_LOG_LEVEL=5
EOF
chmod 0600 "$OTBR_CONFIG/otbr.env"

docker pull "$OTBR_IMAGE"
OTBR_DIGEST=$(docker image inspect --format '{{index .RepoDigests 0}}' "$OTBR_IMAGE")
printf '%s\n' "$OTBR_DIGEST" > "$OTBR_CONFIG/image-digest.txt"
chmod 0600 "$OTBR_CONFIG/image-digest.txt"

docker run --name otbr --detach \
  --restart unless-stopped \
  --network host \
  --cap-drop ALL \
  --cap-add NET_ADMIN \
  --cap-add NET_RAW \
  --security-opt no-new-privileges=true \
  --device="$DEVICE:$DEVICE" \
  --device=/dev/net/tun:/dev/net/tun \
  --volume="$OTBR_DATA:/data" \
  --env-file="$OTBR_CONFIG/otbr.env" \
  "$OTBR_DIGEST"

docker ps --filter name=otbr
