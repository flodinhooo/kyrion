# Named central identity connector

## Subsequent central SMTP checkpoint, 2026-11-07

Owner supplied the Vercel contact mailbox's SMTP password through private ignored
`smtp-password.txt`. It was transferred through verified SSH; Pi input normalized
without trimming intentional password spaces, stored0600 centrally, and incoming
transfer copy removed. No secrets printed, committed, copied into local Cores,
passed in process arguments or shared with customers.

Actual Pi-to-Infomaniak authentication passed on `mail.infomaniak.com:587` with
mandatory STARTTLS and normal certificate verification. Central Keycloak realm
SMTP configured through loopback Admin REST: basic auth, STARTTLStrue, implicit
SSLfalse, debugfalse, from/user `hello@kyrion.ch`, display `Kyrion`, 10-second
timeouts. Prior realm snapshot retained privately in `realm-before-smtp.json`.
Admin access token existed only in operation memory. Bootstrap admin email was
previously absent and set to the owner's sender mailbox with emailVerifiedfalse,
allowing Keycloak's native logged-in-admin test-mail endpoint to address it.

Native `POST /admin/realms/kyrion/testSMTPConnection` returned204 and submitted
one real test mail to the owner-controlled sender mailbox. This is an actual
Keycloak JVM mail test, not mocked delivery or only Python SMTP authentication.
Receipt remains pending owner confirmation; no inbox read access was used.
Evidence is private `smtp-readiness.json`; no real user email is asserted verified.

Fresh provider snapshot `provider-smtp-20261107T162631Z.dump` was restored in an
independent temporary database; realm/client/user/SMTP configuration row counts
matched. Only the temporary probe database was removed. SHA256:
`bf1c00d2285fd13dfef67a63b324348bdd52f8a355519223a8ebc5b24d2ef980`.
Snapshot and restore evidence remain0600 on Pi. This is not yet an encrypted
off-device recovery copy. No personal installation data/migration was touched.

Registration remainsfalse, verifyEmailtrue, website client disabled, Core flags
unchanged. Public registration/link/account login is not declared accepted. Next:
confirm receipt, secure individual admin/MFA and recovery, encrypted off-device
provider backup, real browser email verification/reset/device link acceptance,
then separately scope Core opt-in and the missing Vercel session database.

## Subsequent public HTTPS checkpoint, 2026-11-07

Owner added the exact `auth.kyrion.ch` route and reported both zone and Universal
SSL Active. Cloudflare recursive DNS now returns public edge addresses. Some
Google/Pi/Windows DNS caches still alternate stale NS/NXDOMAIN answers during
delegation convergence; DS is absent in the public checks. This supersedes the
earlier route-not-created/TLS-pending state below, not the remaining mail/login
activation gates.

Public HTTPS was verified using actual public DNS edge addresses temporarily
mapped **only inside each test process**, retaining original hostname/SNI and
complete certificate verification. No hosts, Pi-hole, resolver settings or TLS
checks were changed. Discovery issuer matches
`https://auth.kyrion.ch/realms/kyrion`; discovery and JWKS return200. Requests
with browser and Java-client user-agent headers receive expected results;
`/admin/`, `/realms/master`, `/health`, `/metrics` and `/` return404.
Default Python urllib user-agent receives403 from the public path: do not
misreport all automated clients as accepted or silently spoof clients in product
code. Actual JVM/Node authenticated flows still need their own acceptance.

Real isolated Chromium public account-console navigation reaches the Keycloak
login form, HTTP200, username/password visible, registration link absent, no
page script errors. This is a real TLS/browser check without credentials, not
successful user authentication. Private screenshot/script remain in ignored
`.run/stabilization/identity-pilot/`. Connector still connected with zero restarts;
loopback discovery200. No real users created, mail sent, registration enabled,
website client enabled or personal Core central flags changed.

Next dependency is a privately supplied Infomaniak SMTP password and secure
administration/MFA provisioning. Customer installations must never receive the
central mailbox secret. Preserve parallel uncommitted development changes; no
application build/restart is needed for this evidence-only update.

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
