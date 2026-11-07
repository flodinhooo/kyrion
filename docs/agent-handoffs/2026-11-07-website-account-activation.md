# Website account production preparation

Owner requested completion of website registration after confirming real central
SMTP delivery. Work remains on master; no worktree, installer change, personal
Core restart, local membership change or public-registration activation.

## Implemented and verified

- Website account configuration validates PostgreSQL URL structure and requires
  explicit `sslmode=verify-full` for production and every remote database. Only
  explicit loopback development can omit it. Errors never include credential
  values. Disabled accounts still require no cloud/database configuration.
- Actual public apex `/`, `/account` and `/api/account/session` each return308
  to `www.kyrion.ch`. The canonical www account/session endpoint returns200 with
  enabledfalse. Prior apex callback would break browser-origin/cookie boundaries.
- Production example and provider import template now use the single exact
  `https://www.kyrion.ch/api/account/callback`. A contract regression checks the
  two templates against generated application configuration and required PKCE.
- Actual **disabled** Keycloak website client updated through private loopback
  Admin REST to that single www callback after preserving its representation
  privately. S256 and disabled direct-password/implicit grants retained. Import
  template on Pi updated without restarting Keycloak or resetting the realm.
- Real `openid-client` discovery against the public provider succeeds with the
  library's normal transport and TLS checks. Initial ENOTFOUND resolved after
  clearing only the stale Windows DNS cache. No Pi-hole config/cache change,
  hosts override, custom User-Agent or certificate bypass was used for this
  actual library check. Issuer and S256 match expected metadata.

## Checks actually run

- Targeted security subset12 pass (synthetic RSA-signed OIDC responses, not a real
  user login): valid response, wrong signature/issuer/audience/nonce/state/expiry/
  algorithm, cookies/configuration/TLS boundaries.
- Full Website Playwright suite41 pass against an isolated production build,
  accounts and real SMTP disabled. After adding the canonical-template contract,
  current account suite14 pass; after replacing its untyped JSON fixture with a
  typed static import, affected contract test1 passes again.
- Next production build `.next-account-production-readiness`, TypeScript,
  changed-file ESLint, Prettier and whitespace checks pass. Automatic tsconfig
  additions from the isolated build removed only after checking against the
  saved original; original bytes restored. Active website build untouched.
- These do not prove production registration/email verification/reset/callback/
  website session issuance. Those require the external settings below.

## Precise remaining dependencies

1. No authenticated Vercel tool/CLI session is available here. Owner's interactive
   dashboard access remains necessary for project Storage/configuration/deploy.
2. Separate website-session PostgreSQL has not been provisioned. Neon Free via
   Vercel Marketplace is a possible no-subscription option; confirm whether one
   already exists, Free selection, region and TLS endpoint before creating it.
   Do not use Neon Auth as a second identity system: Keycloak remains authority.
   Only website UUID/issuer/subject/session/flow/audit data belongs there; no
   local Core data or central mailbox password. Do not expose Pi PostgreSQL.
3. Initialize `account-schema.sql` on that **new separate** website database,
   restrict application credentials, set verified-TLS URL and confidential-client
   secret in protected Vercel server configuration. Never share the secret with
   local installations. Bind canonical origin and callback to www. Keep preview
   deployments disabled or use separate explicit clients/databases, no wildcard.
4. Secure individual central administration/MFA and recovery. Existing bootstrap
   admin is private/strongly credentialed, but human MFA acceptance remains open.
   Do not remove bootstrap access before proving replacement access.
5. Encrypted off-Pi recovery export was **not executed**: automatic approval
   review rejected bundling provider DB, SMTP password, tunnel token and private
   config for Windows because that precise sensitive transfer lacked explicit
   owner authorization. A pending owner question describes exact payload and
   ignored Windows destination. No alternate export/encryption bypass attempted.
   Existing on-Pi snapshots and isolated restore evidence remain intact.
6. With those gates met, enable exact website client and registration with email
   verification/recovery policy, deploy only the website changes, test real
   registration/verification/existing-account login/callback/logout/expiry and
   provider outage. User chooses own password; do not preassign a personal user
   based on sender address or infer memberships/OWNER from any central account.
7. Local Core public-device opt-in/link acceptance remains separate; preserve
   passwords, current membership and offline local login throughout.

No claim of a new live registered user or completed website account activation.
Current public transport and confirmed real mail evidence are recorded in
[the tunnel handover](2026-11-07-central-identity-tunnel.md).

Official sources consulted for this preparation:

- https://vercel.com/docs/marketplace-storage
- https://vercel.com/marketplace/neon
- https://neon.com/docs/introduction/plans
- https://vercel.com/docs/cli/login
