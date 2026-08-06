# Kyrion Gateway Agent

This directory contains the device-independent Kyrion gateway agent.

The gateway agent will authenticate a managed node with Kyrion Core, report
bounded health and capability information, and execute only typed operations
that Core has authorised. It must not expose unrestricted shell, radio, Home
Assistant, or operating-system access to Web or the AI service.

Version `0.1.0` implements one-time enrollment, protected local credentials,
bounded Linux health collection and authenticated 15-second heartbeats. It is
deployed as a hardened systemd service on the first Raspberry Pi node. Radio,
device-control and voice authority are not implemented yet.
