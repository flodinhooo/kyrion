# Home-hosted central identity pilot

See [ADR 0043](../../docs/adr/0043-home-hosted-central-identity.md). This is
separate from the loopback development environment. Never publish its dev realm
or run `start-dev` for public use.

## Private staging

Place `pilot.compose.yaml`, `pilot-realm.json` and `pilot.Caddyfile` in an owner-only
directory on the Pi, e.g. `~/.local/state/kyrion/identity-central/` (0700). Create
`.env` there (0600) using `pilot.env.example`, independent random secrets and
reviewed image digests. Keep it out of Git, chat, command arguments and logs.
Copy `themes/` alongside the Compose file for its read-only Kyrion theme mount.
Existing imported realms need explicit theme selection; see [theme operations](themes/README.md).

```sh
cd ~/.local/state/kyrion/identity-central
docker compose --env-file .env -f pilot.compose.yaml up -d
```

Provider PostgreSQL has no published port. Keycloak administration is only on
Pi loopback18889; the restrictive public proxy is only on loopback18890. The
management port9000 is unpublished. No service joins the personal installation's
networks. Requested memory limits are 1 GiB provider, 384 MiB database, 128 MiB
proxy. The inspected Pi reports `MemoryLimit=false`; Docker cannot enforce these
limits on that host. Java is independently capped at a 512 MiB heap (native
overhead is additional), CPU quota is supported, and free-memory monitoring is
required. No kernel/boot configuration change or reboot is part of this pilot.
No access logs are enabled: authorization and email action URLs contain secrets.

Realm import only creates an absent realm, never updates an existing one.
Registration and the confidential website client initially stay disabled.
SMTP is absent in the initial import; see the central SMTP checkpoint below for
the subsequently configured live pilot. verifyEmail remains mandatory. Do not manually mark real users
verified as a substitute for mailbox proof. The local public device client has
no secret, password grant, redirect URI or automatic local enrollment.

## Public activation gates

### Central SMTP checkpoint, 2026-11-07

Owner supplied the existing mailbox SMTP password through a private ignored
editor file. It was transferred through verified SSH and stored0600 only in the
central Pi identity directory; never in either local installation's configuration.
Actual Infomaniak STARTTLS587 authentication with certificate checks passed.
The central `kyrion` realm now uses:

| Setting                        | Value                                                     |
| ------------------------------ | --------------------------------------------------------- |
| Host                           | `mail.infomaniak.com`                                     |
| Port                           | `587`                                                     |
| Authentication                 | enabled, basic mailbox authentication                     |
| STARTTLS                       | enabled; Keycloak26.8.2 requires STARTTLS when configured |
| Implicit SSL                   | disabled (STARTTLS transport)                             |
| User/from                      | `hello@kyrion.ch`                                         |
| Display name                   | `Kyrion`                                                  |
| SMTP debug                     | disabled                                                  |
| Connection/read/write timeouts | 10 seconds                                                |

SMTP settings were applied through the loopback Keycloak Admin REST API, after
preserving the prior realm state privately. No environment/JVM password argument
or client-side credential was introduced. The bootstrap admin's previously
absent email was set to the owner's mailbox, explicitly unverified, so Keycloak's
native SMTP test could address its logged-in administrator. That native test
returned204 and submitted a real test mail. The owner confirmed receipt in the
normal inbox, not spam. No inbox access was used; this delivery does not mark
any central or local user address verified.

Registration remains disabled, website client disabled, verified-email policy
enabled, both local Core flags unchanged. Do not enable public registration until
mailbox verification/recovery and secured individual admin/MFA acceptance. A
local-email settings panel is still separate from a central account link.
This SMTP setup does not provide a Vercel session database or cloud invitations.

### Named connector installed, 2026-11-07

The owner created `kyrion-central-auth` and supplied its token through a private
ignored file. A digest-pinned ARM64 cloudflared2026.10.7 connector is connected
and its internal `/ready` returns200. Use both Compose files for subsequent
operations; otherwise the proxy's tunnel network can be removed accidentally:

```sh
docker compose --env-file .env -f pilot.compose.yaml -f pilot.tunnel.compose.yaml up -d --no-deps public-proxy cloudflared
```

The overlay places only connector and restrictive proxy on a separate `tunnel`
network. Connector runs with the private token owner's non-root UID/GID, all
capabilities dropped, no new privileges, read-only root and token file, no host
ports and bounded container logs. Neither provider nor personal installation
shares that connector network. No OS package installation or host reboot needed.
The private `.env` adds image digest and UID/GID only, not the token itself.

**Dashboard origin for this container deployment:** public hostname
`auth.kyrion.ch`, empty path, service type HTTP, URL `public-proxy:8080`.
Do not use `localhost:18890` from inside the connector container, and never
route directly to Keycloak/admin18889, Core, Web or any PostgreSQL port.
Public route creation, active delegation and normal HTTPS/browser acceptance
remain pending. Connection readiness is not proof of public authentication.

At this checkpoint public DNS still returned old Infomaniak NS answers, DS was
absent and A resolution succeeded. This supersedes the earlier DNSSEC failure
observations below; do not reapply their former incident diagnosis without a
fresh check. SMTP, registration, website client/database and Core opt-in remain
unchanged and disabled pending their separate acceptance gates.

### Read-only recheck, 2026-11-07

The Pi pilot still returns discovery on loopback18889/18890 with issuer
`https://auth.kyrion.ch`; restricted admin/master/management paths return404.
Registration and the website client remain disabled, realm SMTP has zero
configuration rows, and central login is disabled on both personal Cores.

Public validation currently fails **before** issuer TLS: DNS returns SERVFAIL,
with `DNSKEY Missing / no SEP matching the DS`. The signed parent publishes DS
key tag167, algorithm13, digest type2; validating NS queries fail. A diagnostic
checking-disabled query exposes the existing Infomaniak delegation and returns
NXDOMAIN for the auth A record. This diagnostic flag is not an application
workaround or permission to disable DNSSEC. Public website account acceptance
could not be checked through the broken hostname.

Before the numbered activation gates, the domain operator must inventory the
current zone/DS/DNSKEY state, preserve all mail/Vercel/validation records and
reconcile the parent DS with the intended authoritative signing keys. Decide
whether to retain Infomaniak DNS or perform the separately reviewed Cloudflare
delegation. Obtain a record-preserving, DNSSEC-consistent transition/rollback
procedure from the selected operator; never blindly remove DS or change NS.
Verify validating queries from independent resolvers before enabling anything.

The remaining change sequence is: DNSSEC and complete zone review → exact
auth hostname/tunnel/TLS → private administration/MFA and SMTP acceptance →
off-device recovery → central browser pilot → separately chosen website session
database/callback → per-installation Core opt-in. Each is a separate controlled
change, not a consequence of successful local software tests. Missing decisions
are domain/delegation authority, secure SMTP/admin access, website database
provider/location/backup policy and the intended first Core opt-in target.

Retain original zone/DS records and tunnel/client/Core settings before each step.
Rollback only the changed scope: withdraw the new tunnel route; disable new
registration/website-client entry; restore the previous website account flag and
Core central flag via their scoped deployment procedure. Preserve provider data,
subjects/signing keys, local passwords and memberships; never reset a realm or
restore a stale database over subsequent users. DNS rollback must restore a
consistent delegation/signature chain, not just an old NS list. Do not enable
public registration until real mailbox verification/recovery has passed.

No productive setting was changed by this recheck. Current software acceptance
and its limits are in the [gate evidence](../../docs/status/2026-11-07-acceptance-gates.md).

1. Owner creates/signs into Cloudflare Free. Inventory/export existing Infomaniak
   DNS, especially MX/SPF/DKIM/DMARC, Vercel and ownership validation records;
   review DNSSEC/DS before changing nameservers. Preserve domain registration,
   Infomaniak mail and Vercel website. DNS migration is not implied by staging.
2. Create a named tunnel for `auth.kyrion.ch`, origin
   `http://127.0.0.1:18890` when cloudflared runs on the host. A container must
   instead use a deliberately configured isolated connection to public-proxy,
   not its own loopback and never the administration listener. Store the tunnel
   credential in an owner-only file, not chat, Git or shell history. No Quick
   Tunnel/random issuer hostname for persistent accounts.
3. Preserve the proxy allowlist. Public `/admin`, `/realms/master`, root and
   management endpoints must return404. Do not add a Cloudflare Access login in
   front of public OIDC routes: Core/website server requests cannot satisfy it.
   Disable caching for authentication traffic. Retain verified public TLS.
4. Access administration through a private SSH forward, never the public proxy.
   Use a temporary protected management hostname/SSH SOCKS arrangement with valid
   HTTPS, preserving the public realm hostname. Plain HTTP loopback is suitable
   for discovery checks, not public credentials or browser cookie acceptance.
   Replace bootstrap administration with an individually secured admin/MFA and
   remove bootstrap credentials from the deployment environment afterward.
5. Configure realm SMTP using Infomaniak STARTTLS587, sender/login
   `hello@kyrion.ch`, and its private mailbox password. Store centrally only.
   Test delivery to an owner-controlled mailbox. Enable registration only after
   email verification, password recovery and rate/brute-force policy acceptance.
6. Take an encrypted/off-device backup of the provider DB, deployment secrets
   and signing-key material. Prove restore in isolation. Keep issuer, realm
   subjects and keys stable during migration. No `down -v` or fresh realm reset.
7. Verify public discovery issuer, signature/JWKS, RFC8628 authorization with an
   actual browser, explicit local link, central login, unlink, timeout and local
   password login during provider outage. Only then enable central configuration
   on each installation. Do not copy SMTP or website secrets into either Core.
8. Website accounts require a separate central PostgreSQL reachable securely by
   Vercel. Do not expose this Pi's provider/local DB. Select a suitable free
   central database only after checking current limits, TLS and data location;
   then initialize `apps/website/account-schema.sql`, configure private Vercel
   variables and enable the exact confidential client callback. No paid plan or
   provider registration is assumed. This is separate from contact form SMTP.

For local readiness use discovery through loopback18890, assert the HTTPS issuer
and S256/device endpoints, check forbidden paths, container health/restart counts,
memory/disk and unchanged personal service IDs. This does not establish public
DNS, HTTPS, real mail delivery or browser login acceptance.

## Availability and recovery

There is no additional hosting subscription; power, internet and storage still
cost resources. Home failure prevents new central authentication. Existing local
password accounts and authorization do not require this stack. Do not restart
Pi-hole, local Core/Web or the host to deploy it. Stop only this Compose project
if capacity becomes constrained; retain its volume and private credentials.

Official deployment documentation:

- https://www.keycloak.org/server/hostname
- https://www.keycloak.org/server/reverseproxy
- https://developers.cloudflare.com/tunnel/get-started/
- https://developers.cloudflare.com/dns/zone-setups/full-setup/setup/
