# Kyrion development status

Last reviewed: 2026-11-07. Start with the [active backlog](TODO.md).
Development continues on `master`; there is no pending worktree integration.

Maintenance baseline `4f6ea01` passed [hosted CI](https://github.com/flodinhooo/kyrion/actions/runs/42359230467).
That completed round was not repeated. [Current KY-001 checks](2026-11-07-home-calendar-acceptance.md)
exercise real Core/PostgreSQL and separate authenticated browsers in DE/EN desktop/mobile.
A correction makes conflict feedback visible; `871c46a` passed
[hosted CI](https://github.com/flodinhooo/kyrion/actions/runs/42364439472) and is
[installed on Pi Web](2026-11-07-pi-web-conflictfix-rollout.md). Windows was not updated.
**KY-001 remains open** pending actual HOME/user acceptance.

## Current capabilities and evidence

| Area | Implemented | Verification and limits |
| --- | --- | --- |
| Local platform | Core-owned local login, protected first owner, roles/invitations, audit, one HOME/BUSINESS Space per installation | [Security baseline](2026-10-11-security-hardening.md), [Spaces audit](../spaces-tenant-audit.md). Multi-Space runtime and Business Voice stay blocked. |
| Optional identity | Explicit central-account linking/login/unlink, independent local password login, optional website account | [Real isolated Keycloak/Mailpit/Core/Web/Website acceptance](../agent-handoffs/2026-11-06-identity-master-integration.md). [Pi pilot](../agent-handoffs/2026-11-06-central-identity-pi-pilot.md) is loopback only; productive central login is not activated. |
| HOME calendar | Joint native events, selected participants, revision conflicts, voluntary personal disclosure, explicit manual Google delivery/retry and retained copies | [Source results](../agent-handoffs/2026-11-06-home-calendar-results.md), [disclosure](../agent-handoffs/2026-11-06-personal-calendar-disclosure-results.md), [delivery](../agent-handoffs/2026-11-06-household-calendar-delivery-results.md), [browser fixtures](../agent-handoffs/2026-11-06-calendar-usability-results.md). Authenticated real-family/provider acceptance remains open. |
| Devices/media | Nanoleaf, selected Zigbee/Hue and OA20 commands; HA read-only import; Spotify and YouTube Lounge | [Hardware roadmap](../hardware-roadmap.md), [HA](../home-assistant-import.md), [Lounge](../lounge.md). Device-specific evidence is bounded; legacy button grants require explicit review. |
| AI/Velora/Knowledge | Provider-neutral chat/proposals, local and opt-in cloud profiles, personal context/Knowledge; local wake/STT/batch TTS and voice sessions | [AI](../ai-model-providers.md), [K-Data](../agent-handoffs/kdata-handover.md), [Voice](2026-10-31-voice-no-speech-rollout.md). Cloud adapters simulated; real RAG, audio/latency and lifecycle acceptance remain open. |
| Installer | Guarded fresh-install tooling, bundle digest/signature verification and templates | [Implementation status](../installer-v1-implementation-status.md). No installable public signed release or clean-host acceptance. |

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
environment. The baseline hosted result above does not certify the new local
KY-001 UI correction, which has only the linked local verification.

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
