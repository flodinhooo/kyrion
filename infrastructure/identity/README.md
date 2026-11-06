# Isolated Keycloak development environment

For the complete real Website→Web→Core→Keycloak browser flow, including
registration/mail verification and provider outage, use
[full local acceptance](FULL_ACCEPTANCE.md). It has its own project, ports and
disposable databases; the persistent environment below is separate.

This optional Docker Compose project starts Keycloak 26.7.5, its own PostgreSQL,
and a separate website-session PostgreSQL. It does not use installation data,
change DNS, modify the installer, or deploy anything. Only loopback ports 8089
and 5549 are published. The provider database is not published. Image version is
pinned for reproducibility; review current provider security releases before any
production deployment. This `start-dev` environment and its `sslRequired: none`
realm are strictly for loopback development.

1. Copy `.env.example` to ignored `.env` in this directory and supply independent
   random private passwords/client secret. Do not commit the resulting file.
2. From the repository root run
   `docker compose --env-file infrastructure/identity/.env -f infrastructure/identity/compose.yaml up -d`.
3. Open `http://localhost:8089/admin` and use the configured private administrator
   credentials. In realm `kyrion` create a development user, set a password and
   clear required actions. For mailbox-related testing provide a real test mail
   transport; do not treat manually attested addresses as delivery evidence.
4. Configure `apps/website/account.env.example` values in a private development
   environment. The website database URL uses port 5549 and its independently
   supplied password; the website secret must match `WEBSITE_CLIENT_SECRET`.
   Enable accounts and explicit loopback development HTTP. Start with
   `pnpm --filter website dev` and open `http://localhost:3001/account`.
5. Configure local Core's optional issuer to
   `http://localhost:8089/realms/kyrion` and client ID `kyrion-local`, with its
   documented explicit development HTTP option. No shared secret is used by
   this public device client. Open the provider's verification URI from the same
   development computer; `localhost` is unsuitable for cross-device acceptance.

The imported realm has no users or credentials in Git. Realm import substitutes
`${WEBSITE_CLIENT_SECRET}` from the container environment. Import applies to a
new realm only; changing JSON does not overwrite an existing realm. Use the
admin console to review subsequent changes or start a separate fresh test
project; do not delete existing data to force an import.

The website client registers only exact development callbacks on localhost 3001
and the isolated live-test port 3109, requires S256, has a server-only secret and
disables implicit/direct grants. `kyrion-local` is public and enables RFC 8628
device authorization with no redirect URI, shared secret or direct password
grant. The five-minute device code requires explicit user authorization at
Keycloak. Both clients use RS256. Account identity is issuer+subject per client;
there is no assumption that subjects match across clients.

## Live acceptance

Run from `apps/website` after starting this Compose project:

```sh
pnpm exec playwright test --config identity-live.config.ts
```

The opt-in configuration reads only the ignored development `.env` file, starts
the worktree website on localhost 3109 with accounts enabled, and disables
trace capture. The suite creates a disposable test user through the local admin
API, verifies the website code flow and local public-client device flow using
the browser, then deletes that user. No production DNS/TLS/SMTP acceptance is
implied. Keep this suite separate from ordinary tests, which disable accounts.

To exercise the actual JVM Core adapter, use two terminals in this worktree.
In `services/core`, with the existing Java 21 toolchain configured:

```powershell
$env:KYRION_IDENTITY_LIVE = 'true'
$env:KYRION_IDENTITY_LIVE_REQUEST_FILE = (Join-Path (Resolve-Path ../..) '.run/stabilization/identity-live-request.json')
./gradlew.bat test --tests '*CentralIdentityProviderTest' --tests '*CentralIdentityLiveTest' bootJar --console=plain
```

Immediately run in `apps/website` (using that same absolute request path):

```powershell
node scripts/authorize-core-device.mjs --request E:/path/to/worktree/.run/stabilization/identity-live-request.json
```

The request file contains only the public user code/verification URI. The helper
creates a disposable development user, confirms the request in Chromium, waits
for the JVM to consume it, then removes that user. It uses the loopback admin
only to provision this fixture; product clients never use the password grant.
The smoke obeys provider `slow_down` responses. Remove the two
`KYRION_IDENTITY_LIVE*` variables afterward. Normal Core tests intentionally skip
this opt-in test. This proves real Core-provider transport; domain/session/link
tests separately exercise real PostgreSQL with mocked provider responses.

To stop this isolated environment, run the same Compose command with `stop`.
Persistent volumes are deliberately retained.

## Production and installer boundaries

An operator must provision a hardened Keycloak deployment with HTTPS, dedicated
database/backups, admin protection, mail verification and reviewed account
lifecycle policy. `auth.kyrion.ch` is a proposed issuer configuration, not
existing infrastructure. Create a separate confidential website client with
the exact public callback and protect its secret. Local installations use only
the public client ID/issuer and device grant, requiring outbound HTTPS and no
inbound public or arbitrary LAN callback. Provider outage must not affect local
password authentication. Future installer inputs are optional issuer, public
client ID and enabled flag; never ship the website secret or central database
credentials. No installer files are changed here.

Official references reviewed:

- [Keycloak OIDC flows](https://www.keycloak.org/securing-apps/oidc-layers)
- [Keycloak container guide](https://www.keycloak.org/server/containers)
- [Keycloak import/export and variable substitution](https://www.keycloak.org/server/importExport)
- [openid-client signature checks](https://github.com/panva/openid-client/blob/main/docs/functions/enableNonRepudiationChecks.md)
