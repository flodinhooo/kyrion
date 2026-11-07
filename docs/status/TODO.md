# Active Kyrion backlog

Last reviewed: 2026-11-07. Development branch: `master`.

This is the single active backlog. P1 means the next acceptance or safety gate;
P2 means bounded follow-up; P3 means future product scope. **Open** includes
unverified work: source, software tests, deployment and human/provider acceptance
are separate. See [current evidence](README.md) for what already works.

## Next acceptance gates (in priority order)

| ID | Priority / state | Outcome and concrete next step | Completion evidence |
| --- | --- | --- | --- |
| KY-001 | P1 / open | Accept authenticated HOME use: run owner password login and a controlled two-person calendar journey with disposable provider events, disclosure/revocation, conflict, retry and retained-copy checks. | Authenticated DE/EN desktop/mobile results and real-account outcomes; anonymous health checks are insufficient. [Readiness](../home-first-use-readiness.md), [manual checklist](../home-family-calendar-manual-acceptance.md) |
| KY-002 | P1 / open | Review/resave each of the three legacy button bindings on each installation with the eligible human; test single/double/long actions and revoked/offline cases. | Explicit grants and measured physical results, with no inferred or bulk approval. [Rollout](../agent-handoffs/2026-11-06-v46-live-rollout.md) |
| KY-003 | P1 / open | Finish optional productive central identity: review public ingress, TLS, SMTP/lifecycle/admin protection, off-device restore and the separate website session database before enabling it. | Public authenticated registration/verification/recovery/link/unlink/outage journeys, preserved local login and unchanged Space authority. Loopback pilot is insufficient. [Pilot](../agent-handoffs/2026-11-06-central-identity-pi-pilot.md) |
| KY-004 | P1 / open | Accept Velora on physical hardware: two audible dialogues then twenty action attempts including exact targets, partial/offline outcomes, session-end feedback and next wake; measure acoustic latency/continuity. | Human hearing and same-clock timing evidence, DE/EN reviewed audio; record batch-TTS latency and no spoken barge-in. [Voice evidence](2026-10-31-voice-no-speech-rollout.md), [audio review](2026-10-31-tts-listening-review.md) |
| KY-005 | P1 / open | Prove recovery: controlled full-host reboot/network-loss on intended Windows/Pi targets, helper ACL diagnosis and child lifecycle, then independent off-host database + original keys/config/files restore. | Correct destinations, startup order, fresh heartbeat, audit/credential verification and preserved revocations; include nonempty Knowledge data. [Rollout limits](../agent-handoffs/2026-11-06-v46-live-rollout.md), [helper diagnosis](../agent-handoffs/2026-11-06-chats-a-b-closeout.md) |

These steps require separate owner-controlled operational acceptance. This backlog
does not authorize live changes, provider spending or hardware actions.

## Bounded follow-up

| ID | Priority / state | Next step | Completion evidence |
| --- | --- | --- | --- |
| KY-006 | P1 / open | Prove fresh Installer v1 on an independent clean Debian ARM64 host: signed immutable four-image bundle, trusted certificates/bootstrap, private permissions, interruption/concurrency/corruption and existing-state refusal. | Protected GitHub signing run plus clean-room install and scoped backup/restore evidence before pilot distribution. [Installer status](../installer-v1-implementation-status.md) |
| KY-007 | P1 / to verify | Recheck optional-context opt-out/content and multi-process worker/cache/stream lifecycle boundaries; review any legacy orphan roles deliberately. | Combined adversarial isolation/revocation tests and documented process/restore limits. Keep single-Space and Business Voice guards. [Tenant audit](../spaces-tenant-audit.md), [integration](2026-11-06-master-worktree-closeout.md) |
| KY-008 | P2 / open | Complete HA/Shelly, Nanoleaf, Hue/button/motion and OA20 acceptance: exact-room import, connection UI, repeated sync, offline/reconnect/power-cycle, brightness and last-command-state limitations. | Device-specific physical matrix including failures and restart latency. [HA](../home-assistant-import.md), [hardware](../hardware-roadmap.md) |
| KY-009 | P2 / open | Verify Spotify Web receiver/invited-account rights and bounded playback; retain explicit YouTube player behavior. | Real receiver control/permission results; no inferred acceptance from phone playback. [Lounge](../lounge.md) |
| KY-010 | P2 / open | Accept personal Knowledge with a configured local embedding/model runtime, representative synthetic documents, restart, deletion and DB-plus-file restore; review parser/scale limits and stopped-answer provenance. | Actual sourced answers, no cross-user/deleted sources, bounded resource measurements and nonempty restore evidence. Historical KDATA-003/004/005/006/008/010 remain relevant. [K-Data handover](../agent-handoffs/kdata-handover.md) |
| KY-011 | P2 / open | Reconcile AI provider billing/unknown outcomes and run separately approved real-cloud acceptance; measure cold/runtime behavior without changing the selected voice engine speculatively. | Provider-account reconciliation and explicit usage/cost/consent evidence; simulations do not close this. [Accounting](../kai-accounting-and-acceptance.md) |
| KY-012 | P2 / open | Complete calendar usability: simultaneous private overlays and explicit ambiguous wall-time authoring; define reconciliation when remote success precedes audit failure and settle consumer OAuth ownership. | DST/privacy/retry browser and provider cases; no bundled common OAuth secrets. Recurrence/all-day authoring remains planned. [HOME readiness](../home-first-use-readiness.md), [calendar](../calendar-synchronization.md) |
| KY-013 | P2 / planned | Implement the reviewed outbound cloud-invitation slice only after central identity acceptance; retain local password enrollment and explicit owner trust. | Idempotent invitation redemption, offline/revocation tests, no remote-control or data-sync authority. [Contract](../space-invitation-cloud-plan.md) |
| KY-014 | P2 / open | Complete responsive DE/EN, both-theme review of authenticated Home, Plugins, Activity, Calendar, Users and Roles. | Browser results on desktop/mobile with real local authentication; public website tests cover only the website. |
| KY-015 | P1 / hosted CI failed | Publish locally checked CI/fixture fixes only after resolving the automatic Vercel Production-deployment conflict, then rerun all jobs. | Successful hosted software checks; protected release/ARM64 acceptance stays separate. [GitHub findings](2026-11-07-github-ci.md) |

## Future scope (not current release claims)

| ID | Priority / state | Next step | Completion criterion |
| --- | --- | --- | --- |
| KY-016 | P3 / planned | Design existing-installation updater and pre-change restore orchestration with Observe/Control/Manage integration profiles. | Reviewed compatibility, backup, isolated restore and rollback preserving later effects. |
| KY-017 | P3 / planned | Scope multi-HOME membership, room/device permissions and shared Business knowledge separately. | Additive contracts and complete worker/stream/device/document isolation evidence before lifting guards. [HOME direction](../adr/0035-home-membership-and-family-calendar-direction.md) |
| KY-018 | P3 / planned | Bound general automations, mobile/remote access, Matter/Thread, energy/notifications, signed official plugins and later marketplace into separate slices. | Each slice has permissions, recovery and target acceptance; provisioning/scaffolding is insufficient. [Roadmap](../roadmap.md) |
| KY-019 | P1 before public distribution / open | Select repository licence and contribution guidance; review bundled runtime/model licences and signing custody. | Committed licence and distribution review; no open-source reuse permission implied today. |

## Consolidation and history

The [previous TODO](TODO-archive-before-2026-11-07.md),
[previous status index](README-archive-before-2026-11-07.md) and
[previous chat context](CHAT-CONTEXT-archive-before-2026-11-07.md) preserve their
original bytes, assertions and evidence limits. They are historical, not competing
work orders. The [older snapshot](TODO-history-before-2026-10-11.md) remains intact.

Superseded items: separate-worktree integration and old V39/V41 rollout blockers
are closed by [master consolidation](2026-11-06-master-worktree-closeout.md) and
[actual V46 activation](../agent-handoffs/2026-11-06-v46-live-rollout.md).
Google reauthorization was demonstrated in [Sprint 03](2026-10-30-stabilization-sprint-03.md);
this does not certify today's token or the new family flow (KY-001).
Household native events, disclosure and manual delivery are implemented, replacing
the old broad household-definition task; wider membership/scopes remain KY-017.
The MOSS pair decision retained Chatterbox; unreviewed outlier hearing observations
remain KY-004, not a new TTS selection mandate. KDATA migration/source integration
and the inherited combined-lint baseline have later evidence; actual RAG/recovery
and scale/retention work remains KY-010. Unresolved historical operational and
security items are retained above as open or to verify, never closed by date alone.
