# Kyrion Gateway Agent

This directory is reserved for the device-independent Kyrion gateway agent.

The gateway agent will authenticate a managed node with Kyrion Core, report
bounded health and capability information, and execute only typed operations
that Core has authorised. It must not expose unrestricted shell, radio, Home
Assistant, or operating-system access to Web or the AI service.

Implementation will start after the registration, identity, heartbeat, health,
and recovery contracts have been defined and the first Raspberry Pi has been
inventoried.
