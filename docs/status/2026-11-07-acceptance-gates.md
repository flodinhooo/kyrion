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
