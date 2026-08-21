# Kyrion Gateway Agent

This directory contains the device-independent Kyrion gateway agent.

The gateway agent will authenticate a managed node with Kyrion Core, report
bounded health and capability information, and execute only typed operations
that Core has authorised. It must not expose unrestricted shell, radio, Home
Assistant, or operating-system access to Web or the AI service.

Version `0.1.0` implements one-time enrollment, protected local credentials,
bounded Linux health collection, authenticated heartbeats and bounded Zigbee
command execution through loopback-only MQTT. Command polling runs separately
from health collection so local commands can normally be claimed within 250 ms
without increasing the five-second full-health cadence. It is deployed as a
hardened systemd service on the first Raspberry Pi node.

The deployed node uses the router-provided local DNS URL
`http://kyrion-core.home:8080` for Core. A stable name keeps DHCP addresses out
of runtime configuration, but it is not an authority boundary: the gateway
continues to authenticate with its protected node identity and token, and Core
remains restricted to the node by the host firewall.
