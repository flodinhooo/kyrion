#!/bin/sh
set -eu

install -o root -g root -m 0644 /tmp/cli.py /opt/kyrion-gateway/src/kyrion_gateway_agent/cli.py
if [ -f /tmp/health.py ]; then
    install -o root -g root -m 0644 /tmp/health.py /opt/kyrion-gateway/src/kyrion_gateway_agent/health.py
fi
if [ -f /tmp/bluetooth.py ]; then
    install -o root -g root -m 0644 /tmp/bluetooth.py /opt/kyrion-gateway/src/kyrion_gateway_agent/bluetooth.py
fi
install -o root -g root -m 0644 /tmp/kyrion-gateway-agent.service /etc/systemd/system/kyrion-gateway-agent.service
systemctl daemon-reload
systemctl restart kyrion-gateway-agent
systemctl is-active kyrion-gateway-agent
systemctl show kyrion-gateway-agent -p ExecStart --no-pager
