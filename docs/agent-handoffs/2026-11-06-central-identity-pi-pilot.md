# Central identity Pi pilot staging

## Authorization and result

The owner declined paid hosting and authorized preparation on the existing Pi.
Pi-hole only resolves LAN names; it does not publish the public issuer. The
decision is recorded in [ADR 0043](../adr/0043-home-hosted-central-identity.md).
Source changes are on master; find the exact commit with
`git log -- infrastructure/identity/pilot.compose.yaml`.

A new `kyrion-identity-pilot` Compose project is running, with its own PostgreSQL
and networks. All eight previously running containers retained their original
IDs, including Pi-hole, personal Core/Web/PostgreSQL/Caddy, Home Assistant, Matter
and OTBR. No host reboot, DNS change, public deployment, customer SMTP secret,
installation migration or local central-login activation occurred.

Private deployment directory on Pi:
`~/.local/state/kyrion/identity-central/` (0700); `.env` and evidence are0600.
Independent random provider DB/admin/website secrets were generated directly on
the Pi, never printed, transmitted to customers or committed. Keep this directory
and provider Docker volume: future subjects and signing keys must survive moves.

## Deployed configuration

- Keycloak26.8.2, production mode, fixed hostname `https://auth.kyrion.ch`.
  Image digest `sha256:3879c623248408de29a5303178b5816c77e8dfef3890c361f8c0bbeaa979ba3b`.
- PostgreSQL17, no published port, independent provider volume.
  Image digest `sha256:ff87138949ad9a46f32ff23bd6852b52ce024a13dffe9b4087be98292cdd3b4f`.
- Caddy2.10.2, restrictive public-path proxy; all logs discarded to prevent
  accidental authorization/email action URL logging on failed upstream requests.
  Image digest `sha256:c3d7ee5d2b11f9dc54f947f68a734c84e9c9666c92c88a7f30b9cba5da182adb`.
- Host loopback18889 is full provider access; loopback18890 is the restricted
  future tunnel origin. No LAN/public listener or management port is published.
- Registration and confidential website client are disabled; verified-email
  policy stays enabled. SMTP is not configured. Local public device client is
  enabled, without shared secrets/password grants/redirect URIs.

Initially about4 GiB memory was available, about3.34 GiB after startup; about20 GiB
disk free before deployment. Docker reports `MemoryLimit=false`, so configured
container RAM limits are not enforced. Java heap is independently capped512 MiB,
CPU quota supported. Monitor native memory, database/log growth and load. No
kernel boot changes or reboot were performed to enable memory accounting.

## Actual verification

- Actual ARM64 registry manifests verified and images pulled/pinned by digest.
- Actual Compose configuration validation and all three container starts pass;
  all three running with restart count0 at observation, provider DB healthy.
- First readiness attempts correctly failed during initial Keycloak build/schema
  import; checks were repeated after completed bootstrap, not treated as success.
- `verify-pilot.py` passes against actual Pi Keycloak through loopback proxy:
  fixed HTTPS issuer despite spoofed Host/forwarded-host input, S256 advertised,
  JWKS available, six admin/master/management paths404, real RFC8628 public device
  request with maximum300-second expiry. Device credentials were not printed.
- Actual Caddy configuration validation passes. Public proxy restarted once to
  apply URL-log suppression; no personal service restarted.
- Provider `initial-provider.dump` created0600. Restore into an independent
  temporary DB succeeded; realm/client/user counts matched, only that probe DB
  removed afterward. This same-Pi snapshot is not an off-device disaster backup.
- Python compilation, Prettier check and Git whitespace check pass. Application
  source/migrations were unchanged; Core/Web/Website builds were not rerun for
  this isolated deployment configuration change.

Evidence (`readiness.json`, initial snapshot, original container IDs, pull/start
logs) remains private in the deployment directory. No public browser login, real
SMTP delivery, DNS/TLS or Vercel account-session integration was tested here.

## Remaining gates and next owner step

1. Owner signs up/signs into Cloudflare Free. No credentials in chat. No account
   or nameserver change was performed. Inventory existing authoritative DNS and
   DNSSEC before proposing a complete record-preserving delegation transition.
2. Create a named tunnel, token protected on Pi, public hostname `auth.kyrion.ch`
   pointing ONLY to restricted proxy18890. Validate public TLS/discovery and
   admin denial; never tunnel personal Core/Web/PostgreSQL or loopback18889.
3. Secure individual administration/MFA, remove bootstrap credential environment,
   configure central Infomaniak SMTP587/STARTTLS through a private secret channel,
   prove mailbox verification/recovery and registration. Customer Cores receive
   only issuer/public client configuration, never these SMTP credentials.
4. Secure off-device backup and run browser local-link/login/unlink/outage checks
   before enabling central login on either personal installation.
5. Website accounts additionally require a separate securely reachable central
   session DB for Vercel. Do not expose Pi databases. Evaluate a free DB offering's
   current limits/data location and TLS before registration. Contact form settings
   alone do not provide this database or central account service.
6. See [PILOT.md](../../infrastructure/identity/PILOT.md) for activation gates and
   [invitation plan](../space-invitation-cloud-plan.md) for the subsequent Jennifer
   slice. No new invitations/remote control/data synchronization implemented.
