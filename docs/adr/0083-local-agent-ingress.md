# ADR 0083: Restricted local TLS ingress for existing agent protocols

Status: Accepted for implementation

## Decision

Use the installation's existing Caddy TLS listener for explicitly enumerated
gateway and voice-satellite protocol paths. Do not expose the complete Core API.
The immediate connection peer must be loopback, RFC1918 IPv4 or ULA IPv6; forwarded
headers cannot grant local status. Core continues to authenticate enrollment and
device credentials, enforce the Space boundary, and validate command authority.

Native Windows upstream traffic retains certificate and hostname validation
against the owned Core certificate. Container installations use their existing
private Compose network. The agent must explicitly trust the installation
certificate and still validate hostname and its pinned certificate bytes.
No router changes, public listener, remote shell or Ollama LAN listener are added.

Existing installed configurations require an explicitly reviewed extension;
source changes alone do not rewrite or restart installations. A proxy route is
transport, not evidence that agent deployment, task migration or microphone setup
is complete.

## References

Verified against the official [Caddy request matchers](https://caddyserver.com/docs/caddyfile/matchers),
[handle directive](https://caddyserver.com/docs/caddyfile/directives/handle) and
[reverse proxy TLS transport](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy).
