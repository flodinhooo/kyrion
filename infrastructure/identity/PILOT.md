# Home-hosted central identity pilot

See [ADR 0043](../../docs/adr/0043-home-hosted-central-identity.md). This is
separate from the loopback development environment. Never publish its dev realm
or run `start-dev` for public use.

## Private staging

Place `pilot.compose.yaml`, `pilot-realm.json` and `pilot.Caddyfile` in an owner-only
directory on the Pi, e.g. `~/.local/state/kyrion/identity-central/` (0700). Create
`.env` there (0600) using `pilot.env.example`, independent random secrets and
reviewed image digests. Keep it out of Git, chat, command arguments and logs.

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
SMTP is absent; verifyEmail remains mandatory. Do not manually mark real users
verified as a substitute for mailbox proof. The local public device client has
no secret, password grant, redirect URI or automatic local enrollment.

## Public activation gates

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
