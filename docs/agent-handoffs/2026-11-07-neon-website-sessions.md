# Neon website session database integration

## Scope and authorization

Owner created and connected a Neon Free database to Vercel's `kyrion-website`
project, supplied connection details, and explicitly requested database setup and
private env configuration. Existing public identity transport/SMTP acceptance
remains in [the tunnel handover](2026-11-07-central-identity-tunnel.md).
Work is on master; source commit is discoverable with
`git log -- apps/website/account-runtime-grants.sql`.

This is the dedicated central **website session** database in Frankfurt. The
provider database and all local installation databases remain separate. No
Core migration, local user/password/membership change, public registration,
provider import reset, installer change or personal service restart occurred.
The owner's possible future wider migration is not an instruction to migrate
local data or eliminate offline independence.

## Actual changes

1. Read-only preflight connected over verified TLS, confirmed an empty public
   schema and provisioning-role CREATE ROLE permission.
2. Applied existing `apps/website/account-schema.sql` without modifying it:
   `website_account`, `website_oidc_flow`, `website_session`,
   `website_account_event`, plus the existing expiry index/constraints.
3. Created independent SQL login `kyrion_website_app` with random private password,
   no superuser/CREATEDB/CREATEROLE/replication/BYPASSRLS privileges and no provider
   administrator membership. The application does not use `neondb_owner`.
4. Added password-free `account-runtime-grants.sql`. It checks administrative
   role/membership hazards, grants exact runtime operations, disallows public
   schema creation, and gives audit INSERT only. Applied the source file twice
   successfully on the dedicated Neon DB. Do not run this on shared/Core DBs.
5. Website `pg` pool now enables SCRAM channel binding when offered by the server.
   No dependency added. URLs retain explicit `sslmode=verify-full`; no disabled
   certificate checks or plaintext connection variants used.
6. Created ignored `apps/website/.env.production.local`, with ACL limited to the
   Windows user, SYSTEM and Administrators. It contains complete server-only
   KYRION_WEBSITE configuration and a restricted pooled runtime DATABASE_URL.
   Only the needed existing website OIDC client secret was transferred from Pi
   via verified SSH into the private file, with no secret output. No SMTP,
   tunnel, provider-admin or provider-DB secret exported by that operation.
7. Provisioning input is private and ignored under
   `.run/stabilization/identity-pilot/neon-owner.json`. Do not include these files
   in commits, public archives, screenshots or handover excerpts. No real secret
   was added to tracked `.env.example` or production example files.

## Real database and software verification

- Direct owner connection and pooled restricted application connection succeed
  with certificate-authorized TLS. Runtime cannot create public schema objects
  or delete audit events.
- Actual AccountStore implementation exercised against Neon: one-use flow and
  replay rejection, session issuance with persisted SHA256 token digest, foreign
  token rejection, logout revocation and two expected audit events. A random
  synthetic issuer/subject was used. Only its own fixture rows were removed via
  the provisioning connection afterward; no real user was registered.
- Initial Node strip-only runner rejected TypeScript parameter properties before
  any SQL test operations. Reran the actual source with Node transform-types;
  the real integration check passed. No test failure hidden as acceptance.
- Source grant script reapplication passes twice. Role guards are production
  checks, not a claim that a privileged role was deliberately granted in Neon.
- Isolated Next production build `.next-neon-account-readiness`, TypeScript and
  changed-file ESLint pass. Full Website Playwright42 pass, actual cloud accounts
  and real SMTP disabled in that regression. Synthetic RSA provider tests are
  distinct from the real Neon storage integration.
- All15 generated browser JS assets scanned against the private owner/runtime/
  OIDC secrets; no matches. This does not claim a scan of every historical artifact.
- Automatic isolated-build tsconfig additions removed after comparing with saved
  original; original bytes restored. Existing active build untouched.
- Both private files confirmed ignored by Git. Parallel `.env.example` changes
  were preserved and excluded from this task's commit.

## Remaining activation and credential actions

`KYRION_WEBSITE_ACCOUNT_ENABLED=false` remains in the private production file.
Public registration and the website client are still disabled. Neon setup alone
does not enable OIDC callback, user registration or local access.

The local env file does **not** upload itself to Vercel. No authenticated Vercel
tool/CLI session is available. Import the private KYRION_WEBSITE variables into
the `kyrion-website` project's Production environment only, with secrets marked
sensitive, preserve unrelated contact-mail settings, and do not copy production
secrets into Preview. The generic DATABASE_URL alias is optional for the account
feature; its authoritative connection is KYRION_WEBSITE_ACCOUNT_DATABASE_URL.
Retain the exact `https://www.kyrion.ch/api/account/callback`.

The owner credential supplied in chat must be rotated in Neon. Do not repeat it
in responses. Website runtime has an independent new password, so rotating the
owner role does not change that runtime credential. Provider-managed Vercel
aliases may update separately; verify integration settings after rotation.

Before live account activation: secure individual admin/MFA and recovery,
resolve the separately pending off-Pi backup authorization, then enable exact
website client/verified-mail registration, deploy and prove actual browser
registration, verification/reset, callback/session/logout/expiry. Local device
link remains a separate explicit opt-in without membership or OWNER grants.

No automatic global migration, paid plan, Neon Auth identity system, invitation
broker, general remote access or production Vercel deployment was introduced.

Official references:

- https://neon.com/docs/manage/roles
- https://vercel.com/docs/environment-variables
- https://vercel.com/docs/environment-variables/sensitive-environment-variables
