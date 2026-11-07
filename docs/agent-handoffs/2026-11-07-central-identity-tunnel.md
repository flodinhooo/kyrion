# Named central identity connector

Owner authorized home-hosted central identity and created Cloudflare tunnel
`kyrion-central-auth`. Token supplied through ignored local private file; no
credential copied into source, shell arguments, environment values or chat.

## Installed on Pi

Private directory: `~/.local/state/kyrion/identity-central/`.
Token is `cloudflare-token.txt`, mode0600, mounted read-only into cloudflared.
Incoming transfer file was removed after normalization and validation. Windows
private input remains preserved and Git-ignored; do not stage/archive it publicly.
`.env.before-tunnel` preserves prior private deployment configuration.

Source adds `pilot.tunnel.compose.yaml`, an explicit overlay over the existing
pilot Compose. Actual command used scoped `up -d --no-deps public-proxy cloudflared`:
only Identity public proxy recreated to add connector network; existing Keycloak,
its DB and all personal services retained. No apt repositories, host service,
host networking, router ports, Pi-hole settings or installer changes.

Cloudflared2026.10.7, ARM64 image pinned to
`sha256:4955524aeaa379e154023d5a027c250f7b35041a2e7e950cf13f144bc9b9c5ba`.
Runs as private token owner UID/GID, capability-free, no-new-privileges,
read-only root, no published ports. Dedicated tunnel bridge connects only proxy
and connector. Internal metrics/readiness20241 is not published. Requested
128 MiB Docker limit is advisory on this Pi (`MemoryLimit=false`); CPU quota
0.5 is supported. Error-level bounded logs, never debug; raw diagnostics stay
private. Cloudflare account administrators can change remote routing, so remain
trusted operators; token permits running this named connector, not DNS admin.

## Actual checks

- Native image pulled, pinned and architecture checked.
- Both Compose files merged and `config --quiet` passed against private config.
- Connector running, restart count0; real `/ready`200 through proxy container.
- Inspected connector root read-only, no host ports, only dedicated tunnel bridge.
- Ten other previously running containers have unchanged IDs. Identity proxy is
  the only recreated existing container; local application DBs are untouched.
- Existing loopback proxy discovery200, canonical HTTPS issuer preserved.
- Prettier, Git whitespace checks pass. No application source/migration changes;
  application builds were not rerun for this connector-only deployment.

Private evidence: `before-tunnel-containers.json`, `tunnel-readiness.json`,
`tunnel-image-pull.log`, `tunnel-startup.log`, `tunnel-diagnostics.log`.
No successful public TLS/browser login/mail delivery claimed.

## Next owner dashboard action

Add published application/public hostname route in the connected tunnel:

| Field        | Value               |
| ------------ | ------------------- |
| Subdomain    | `auth`              |
| Domain       | `kyrion.ch`         |
| Path         | empty               |
| Service type | HTTP                |
| URL          | `public-proxy:8080` |

This origin is reachable from the dedicated container bridge. Host loopback18890
is not connector loopback. Do not route Keycloak8080 directly or admin18889;
never route personal Core/Web/devices/DB. Check existing remote routing before
any public use; authenticated dashboard access is not available to this agent.
Do not request a broad account API token just to automate this one route.

At latest check DS absent, A DNS succeeds; recursive NS still reports Infomaniak.
Owner has entered assigned Cloudflare NS at registrar; public delegation and
Cloudflare zone activation must still be verified. Previous DS167 incident is
historical, not the current result. DNSSEC remains temporarily disabled until
delegation is stable and a new consistent signing chain is separately configured.

Then verify normal public TLS/discovery plus admin/master/management denial.
Secure administration/MFA, central SMTP587/STARTTLS, real verified-email recovery,
off-device backup and browser device/link/unlink/outage acceptance still required
before personal Core opt-in. Registration and website client remain disabled.
Website Vercel session database remains an independent missing prerequisite; no
SMTP password or website secret belongs in customer installations.

## Scoped rollback

Withdraw the new public hostname route, stop only `cloudflared` using both Compose
files; retain token/provider database/subjects/keys. No `down -v`, realm reset,
database restoration over subsequent changes or unrelated service restart.
Removing the tunnel does not require reverting domain DNS delegation. Any future
DNS rollback must preserve a consistent complete zone/signature chain.
