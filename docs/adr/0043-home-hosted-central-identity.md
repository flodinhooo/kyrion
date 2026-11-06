# Home-hosted central identity without a hosting subscription

Status: accepted for a gated personal pilot; public activation pending.

## Context

The owner requests no additional hosting subscription. A separate ARM64 Pi
already runs the personal installation and Pi-hole. On inspection it has about
4 GiB available RAM and 20 GiB free disk. Pi-hole is a LAN resolver, not public
authoritative DNS or a public authentication endpoint.

## Decision

Keep Keycloak and the existing RFC 8628 public-client integration. Run a separate
Compose project with a dedicated provider PostgreSQL volume on the Pi. Do not
reuse the installation database, credentials, network or application containers.
Initially expose only loopback listeners; disable registration until verified
SMTP, HTTPS and backup acceptance. Use production mode and the intended stable
issuer `https://auth.kyrion.ch/realms/kyrion` from the beginning.

A separately authorized named Cloudflare Tunnel can later publish only the
realm authentication and static resource paths through a restrictive local
proxy. The admin API/console and management port must never be routed through
that proxy. No local Core, device controls or PostgreSQL port is published.
Cloudflare terminates public TLS and is consequently a trusted transport
processor. The local HTTP hop stays on the isolated Docker network.

Cloudflare Free requires an owner-controlled account and authoritative DNS
on Cloudflare for this custom hostname. Domain registration and mail hosting
can stay at Infomaniak. Preserve all existing DNS records, including mail,
DKIM, SPF, DMARC, Vercel and verification records, and plan DNSSEC transition
before changing delegation. No nameserver change is performed by this decision.

## Consequences

No additional hosting subscription, but existing power/storage/network costs,
maintenance, backups and availability remain the owner's responsibility. Pi or
home internet failure stops new central authentication, while local password
login remains independent. This is a personal pilot, not a high-availability
customer service. Review load, disk growth and security updates before expansion.

SMTP secrets remain only with the central provider. Do not copy them to customer
installations. Website accounts additionally need a separately secured central
session database reachable by the Vercel server runtime: the Pi PostgreSQL must
not be published to solve this. Website activation is a separate prerequisite;
hosting Keycloak alone does not enable the website account feature.

Migration to another host must preserve the issuer hostname, realm database,
subjects, signing keys and client configuration. Never recreate existing users
from matching email addresses. No implementation of an OAuth/OIDC server is added.

## References

- https://www.keycloak.org/server/containers
- https://www.keycloak.org/server/hostname
- https://www.keycloak.org/server/reverseproxy
- https://developers.cloudflare.com/tunnel/get-started/
- https://developers.cloudflare.com/dns/zone-setups/full-setup/setup/
