# Full local identity acceptance

This opt-in environment uses actual Website, local Web, packaged Core, Keycloak,
three independent PostgreSQL databases and Mailpit. There are no mocked HTTP
routes or provider responses in `apps/website/full-identity/flows.spec.ts`.
It neither contacts nor restarts the personal installation. No installer changes
are involved. Do not run these commands against production configuration.

## Prerequisites and start

Use Docker Desktop, Node/pnpm and Java 21. Set `JAVA_HOME` to your Java 21 path.
Install the root workspace and the independent `apps/web` dependencies with their
frozen lockfiles. Install Chromium using `pnpm --filter website exec playwright
install chromium` if unavailable. Then, from this checkout's repository root:

```powershell
node apps/website/scripts/identity-acceptance-core.mjs --init
docker compose --env-file .run/stabilization/identity-acceptance.env -f infrastructure/identity/acceptance.compose.yaml up -d
```

The first command generates private random credentials in ignored
`.run/stabilization/identity-acceptance.env` if absent; it prints no credentials
and preserves an existing configuration. Keep that file private. Do not use the
ordinary `infrastructure/.env` or an installation database for this environment.

Wait until Core/Website PostgreSQL accept connections and
`http://localhost:18089/realms/kyrion/.well-known/openid-configuration` returns 200. Keycloak's initial augmentation/schema import can take several minutes on
a slow Desktop filesystem. Compose's `up -d` alone is not readiness evidence.
The imported realm explicitly enables registration and email verification,
provides a local SMTP catcher, requires a password and issues 60-second tokens
to exercise actual expiry. Password setup can occur after email verification;
the browser suite handles that actual provider flow and remembered-user reauth.

Build and verify the current combined Core before acceptance. The runner pins
the boot JAR required by the schema-only rehearsal and holds the shared Core
verification lock; an unconfigured plain `gradlew test` cannot supply that proof:

```powershell
& infrastructure/dev/Test-CoreSchemaMigration.ps1 -JavaHome $env:JAVA_HOME -FullCoreSuite
Push-Location apps/website
pnpm exec playwright test --config full-identity.config.ts
Pop-Location
```

The Playwright configuration starts this checkout's Core JAR on loopback 18092,
Website on localhost 3119 and Web on localhost 3219; each refuses to reuse an
unrelated existing process. Both Next applications use separate acceptance build
directories, leaving personal dev/build output in place. The wrapper provisions a separate test bootstrap
proof and credential/audit keys under ignored `.run/stabilization/` and selects
only the acceptance Core database at 15559. The website session DB is at 15549;
the provider DB has no published port. Mailpit's UI/API is localhost 18025, and
SMTP 1025 is container-network-only. All published infrastructure ports bind
127.0.0.1. No public incoming port, LAN callback registration or token relay is
used: local login uses the real public client's outbound device grant.

## What the suite proves

- A new central user registers in the actual provider UI, receives a real local
  verification email, follows its action and establishes a website session.
- Website logout and subsequent login with that existing central account work.
- The existing host-secret UI creates the local OWNER when necessary; the
  existing local invitation/signup UI creates a non-OWNER local member.
- Central login before linking is denied without creating a local user/role.
- The member explicitly connects after local password and provider device-code
  confirmation, then logs in centrally with exactly the original local rights.
- The real short-lived central session expires, requiring login again.
- The test stops **only** `kyrion-identity-full-keycloak-1`; the UI explains the
  outage, local password login still works, and password/checkbox-confirmed unlink
  works without the provider. The local user and OWNER grants survive. `finally`
  starts that test provider again.

Tracing, video, screenshots and automatic failure DOM snapshots are disabled;
navigation logs omit query strings,
and central response logs include machine status/code only. Test usernames/mail
are synthetic. The acceptance script uses SQL only against its fixed isolated
database to inspect user/role/link preservation, not to manufacture credentials,
membership or session expiry. The Core domain suite separately covers hostile
tokens, replay/concurrency, current membership and Gateway/Calendar authority.

## Stop and limits

```powershell
docker compose --env-file .run/stabilization/identity-acceptance.env -f infrastructure/identity/acceptance.compose.yaml stop
```

All **acceptance databases use tmpfs**. Stopping those database containers discards
their synthetic data; the environment is intentionally disposable and does not
prove crash durability. The ordinary optional development Compose remains
persistent and unchanged. No database volume or protected private configuration
is deleted by this procedure. Repeated Core starts within the same running test
database perform normal Flyway validation and preserve initialized accounts.

HTTP, plaintext isolated SMTP and self-registration here are test configuration,
not production readiness. Public provider hosting, maintained release/backup
policy, verified DNS, HTTPS/TLS, production mail and reviewed registration policy
remain external steps. This does not expose the installation to the internet,
enable multi-Space operation or implement cloud-delivered invitations. See
[the invitation contract](../../docs/space-invitation-cloud-plan.md) for that next
slice and [the current handover](../../docs/agent-handoffs/unified-identity-handover.md)
for actual acceptance results.
