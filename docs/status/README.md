# Kyrion development status

Website/documentation reviewed: 2026-11-12. Start with the [active backlog](TODO.md)
and [current website acceptance](2026-11-12-website-acceptance.md).
Development continues on `master`; no additional worktree integration was found
in the website audit. Unrelated installer work is in progress and is not included
in the website acceptance. Other platform evidence retains its stated date.

Maintenance baseline `4f6ea01` passed [hosted CI](https://github.com/flodinhooo/kyrion/actions/runs/42359230467).
That completed round was not repeated. [Current KY-001 checks](2026-11-07-home-calendar-acceptance.md)
exercise real Core/PostgreSQL and separate authenticated browsers in DE/EN desktop/mobile.
A correction makes conflict feedback visible; `871c46a` passed
[hosted CI](https://github.com/flodinhooo/kyrion/actions/runs/42364439472) and is
[installed on Pi Web](2026-11-07-pi-web-conflictfix-rollout.md). Windows was not updated.
**KY-001 remains open** pending actual HOME/user acceptance.

The [KY-002–KY-005 recheck](2026-11-07-acceptance-gates.md) records source-only
binding/Voice fixes, real isolated identity acceptance, an earlier DNSSEC failure
and same-host original-key restore evidence. Personal/physical/full-host/off-host
acceptance stays open; no later source fix is silently deployed.

The website audit removed seven unused generated builds, corrected canonical
host/contact-origin templates and inaccurate DE/EN cookie disclosures, and passed
50 isolated tests plus the production build, types, lint and formatting checks.
The public account API currently reports enabled and public provider discovery
works. The public pages still returned the older apex metadata and privacy copy
on 2026-11-12; publishing the corrections and real mail/account acceptance remain
open. These are KY-020–KY-024, not missing integration of generated directories.

## Current capabilities and evidence

| Area                | Implemented                                                                                                                                              | Verification and limits                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Local platform      | Core-owned local login, protected first owner, roles/invitations, audit, one HOME/BUSINESS Space per installation                                        | [Security baseline](2026-10-11-security-hardening.md), [Spaces audit](../spaces-tenant-audit.md). Multi-Space runtime and Business Voice stay blocked.                                                                                                                                                                                                                                                                                                                                                                                                 |
| Optional identity   | Explicit central-account linking/login/unlink, independent local password login, optional website account                                                | [Real isolated acceptance](../agent-handoffs/2026-11-06-identity-master-integration.md); [later public ingress/central SMTP evidence](../agent-handoffs/2026-11-07-central-identity-tunnel.md). Public website account API enabled and HTTPS discovery rechecked on 2026-11-12. Real public user journeys and installation Core opt-ins are not certified by that check.                                                                                                                                                                               |
| Public website      | DE/EN informational, Contact, Account, Privacy, Download and Hardware routes; separate server-side account/contact boundaries                            | [Current acceptance](2026-11-12-website-acceptance.md), [detailed website audit](../../apps/website/STATUS.md). 50 isolated tests and build/types/lint/format pass; seven old generated builds removed. Corrections published and publicly verified in `48d064a`; contact Origin still requires a Vercel Production correction. Customer browser registration, a responsive account menu and remembered website sessions are implemented (ADR 0051); actual new-user/renewal and deployed abuse/privacy acceptance remain open; release catalog empty. |
| HOME calendar       | Joint native events, selected participants, revision conflicts, voluntary personal disclosure, explicit manual Google delivery/retry and retained copies | [Source results](../agent-handoffs/2026-11-06-home-calendar-results.md), [disclosure](../agent-handoffs/2026-11-06-personal-calendar-disclosure-results.md), [delivery](../agent-handoffs/2026-11-06-household-calendar-delivery-results.md), [browser fixtures](../agent-handoffs/2026-11-06-calendar-usability-results.md). Authenticated real-family/provider acceptance remains open.                                                                                                                                                              |
| Devices/media       | Nanoleaf, selected Zigbee/Hue and OA20 commands; selected HA inventory and separately consented power control; Spotify and YouTube Lounge                | [Hardware roadmap](../hardware-roadmap.md), [HA](../home-assistant-import.md), [Lounge](../lounge.md). Device-specific evidence is bounded; legacy button grants require explicit review.                                                                                                                                                                                                                                                                                                                                                              |
| AI/Velora/Knowledge | Provider-neutral chat/proposals, local and opt-in cloud profiles, personal context/Knowledge; local wake/STT/batch TTS and voice sessions                | [AI](../ai-model-providers.md), [K-Data](../agent-handoffs/kdata-handover.md), [Voice](2026-10-31-voice-no-speech-rollout.md). Cloud adapters simulated; real RAG, audio/latency and lifecycle acceptance remain open.                                                                                                                                                                                                                                                                                                                                 |
| Installer           | Guarded fresh-install tooling, bundle digest/signature verification and templates                                                                        | [Implementation status](../installer-v1-implementation-status.md), [committed Nov11 continuation](2026-11-11-installer-continuation.md): synthetic fresh-stack/recovery and developer-native artifacts have evidence; ongoing native Windows work is separate. No installable public signed release or clean-host acceptance.                                                                                                                                                                                                                          |

## Deployment is separate

The [2026-11-06 V46 rollout](../agent-handoffs/2026-11-06-v46-live-rollout.md)
records actual Windows/Pi Core/Web activation, original-key restore drills and
anonymous DE/EN browser checks. It does not prove authenticated owner/family
journeys, hardware, provider writes, full-host restart or off-host disaster recovery.
These are historical observations, not a current health guarantee. The KY-001
isolated work read only personal health/artifact metadata. The later authorized
Pi Web-only rollout is recorded separately above; no personal login or provider
write was performed.

[Maintenance verification](2026-11-07-maintenance.md) records the checks for the
initial maintenance changes. Results apply only to their reported source and
environment. Hosted results apply to their recorded commits, including the
separately linked871c46a run; later local binding/Voice/recovery changes have
only the verification recorded in the current gate report.

## Reading order

1. [README](../../README.md) and [agent rules](../../AGENTS.md).
2. [Active backlog](TODO.md), then the linked evidence for the selected item.
3. [Architecture](../architecture.md), [ADRs](../adr/) and [startup](../development-startup.md).

Implemented, automatically tested, deployed, physically/provider accepted,
experimental and planned are distinct states. Healthy services do not establish
an authenticated user journey. Local-first does not make external services offline.

The previous cumulative [status index](README-archive-before-2026-11-07.md),
[TODO](TODO-archive-before-2026-11-07.md) and
[chat context](CHAT-CONTEXT-archive-before-2026-11-07.md) are immutable historical
snapshots. Their older priorities, source counts and deployment boundaries are
not the active backlog.
