# KY-002–KY-005 software verification and operational gates

This evidence supplements the existing [backlog](TODO.md); it is not another
task list. Work starts on `master` at `fb3f87c`, preserving the installed Pi Web
`871c46a` / `aaUX9C2_I6tMOcrV1sImr`. KY-001 is unchanged and awaits the actual
two-user acceptance. No personal binding/account/provider approval is inferred.

## KY-002 — legacy button review

Read-only transactions on both actual databases confirm three legacy rows each,
all without grants. They refer to the same SONOFF button and room-toggle actions.
The Pi has a fresh intended-node heartbeat; Windows has only an August source
observation. Owner eligibility includes devices:read/update/execute, but that is
not consent to any binding. Device/room names, addresses and row identifiers stay
in the private six-row review sheet:
`.run/private-evidence/ky002-005/legacy-binding-review.md`.

The current UI omitted grant state and could present inactive legacy settings as
ordinary assignments. Source now displays localized unreviewed/authorized status
and explains that saving replaces **all** selected grants. Grant metadata is
validated; absent legacy metadata remains unreviewed. Duplicate gestures and
malformed grant metadata are rejected. This UI change is **not deployed**.

Existing actual-Core/PostgreSQL integration covers authenticated saving, fresh
grants, identical-resave revocation, author permission revocation, room/source/
target isolation, terminal denial and no stale replay. A new regression also
removes bindings through the authenticated API and denies their pending command.
The synthetic gateway records dispatch/results; no physical adapter is contacted.
Targeted results: GatewayAuthorityIntegrationTest29 and ZigbeeButtonBindingTest3,
zero failures/errors/skips; Web contract tests6, ESLint, typecheck and isolated production build pass.

For actual review, use the intended installation's eligible human session at
Devices → button → Button bindings. Confirm each exact gesture, current room
power targets and toggle action. Remove any unapproved row before saving: one
save replaces the whole button configuration. Never infer approval from the
private inventory or resave Windows against its stale source. Inspect actor/grant
audit, then observe physical single/double/long, offline and revoked cases in an
agreed slot. No actual binding was changed; **KY-002 remains open**.

## KY-003 — optional central identity

Actual Pi Keycloak26.8.2 remains loopback18889/18890 with the fixed HTTPS issuer;
discovery succeeds and restricted admin/master/management paths return404.
Read-only provider SQL confirms registration disabled, email verification on,
website client disabled and zero SMTP configuration rows. Both personal Cores
return central-enabled=false. No personal account/link/role was changed.

Fresh public DNS queries fail SERVFAIL with `DNSKEY Missing / no SEP matching the
DS`. Parent DS tag167/algorithm13/digest2 validates; child signing keys do not
match that trust chain. Checking-disabled diagnostic queries expose Infomaniak
NS and auth A NXDOMAIN; they are not a proposed DNSSEC bypass. Public website
account/TLS acceptance is blocked at DNS, not established by loopback health.
The [existing pilot plan](../../infrastructure/identity/PILOT.md#read-only-recheck-2026-11-07)
now records gates, target, scope, missing decisions and rollback boundaries.
No DNS, ingress, provider settings or public registration changes were made.

Actual isolated Keycloak26.7.5/Core/Web/Website/three PostgreSQL/Mailpit acceptance
passes: synthetic registration/mail verification, website login/logout, local
owner/member enrollment, unknown central subject denied without new membership,
explicit password/confirmation-based link, central login with unchanged member
rights, real token expiry, test-provider outage, preserved local password login
and offline unlink. Mail is caught locally; no productive email/provider is used.
UnifiedIdentityIntegrationTest13, CentralIdentityProviderTest9 and
IdentityTransportTest2 pass with no failures/errors/skips. Domain tests use a
mocked provider; the full browser scenario uses actual local Keycloak transport.

First browser attempt failed before registration because the disposable provider
was still bootstrapping. The runner now waits for the exact isolated discovery
issuer (bounded120s) before starting Core; its startup budget includes that wait.
It also explicitly suppresses the personal infrastructure/.env import. The final
complete scenario passes (1.8m); Node syntax, focused ESLint/Prettier pass. The
reviewed unchanged Core JAR was reused; no unrelated full suite/build repeated.
Acceptance services were stopped afterwards; only their synthetic tmpfs data was
discarded. **KY-003 remains open** for productive domain/mail/admin/website and
real-account acceptance. Logs are private under `.run/private-evidence/ky002-005/`.
