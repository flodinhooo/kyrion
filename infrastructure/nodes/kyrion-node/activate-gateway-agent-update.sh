#!/bin/sh
set -eu

install -o root -g root -m 0644 /tmp/cli.py /opt/kyrion-gateway/src/kyrion_gateway_agent/cli.py
install -o root -g root -m 0644 /tmp/kyrion-gateway-agent.service /etc/systemd/system/kyrion-gateway-agent.service
systemctl daemon-reload
systemctl restart kyrion-gateway-agent
systemctl is-active kyrion-gateway-agent
systemctl show kyrion-gateway-agent -p ExecStart --no-pager
