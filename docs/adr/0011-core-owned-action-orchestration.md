# ADR 0011: Core-owned action orchestration

## Status

Accepted for the first shared device-action slice on 2026-08-19.

## Context

Kyrion currently executes bounded device commands in Core, but proposal
orchestration and user-facing result selection are still split between clients.
The Next.js chat route can request an AI proposal and then call the command
endpoint, while the physical Voice path cannot yet execute the same action and
receive the authoritative result. This makes it difficult to apply one policy,
one correlation identity and one audit trail across Web, Voice and future
clients.

Core already owns authentication, owner-scoped device state, capability
validation, adapter execution and activity logging. AI output, browser input
and integration output are untrusted and must not become execution authority.

## Decision

Core owns a thin, domain-extensible Action Orchestrator above existing domain
services. An action has:

- an `ActionContext` containing owner, actor, interaction channel, locale,
  correlation identity, optional session/conversation scope and idempotency
  identity;
- a typed `ActionProposal`; the first implementation is
  `DeviceActionProposal` with a stable device identifier, capability and typed
  arguments;
- an `ActionDecision` produced by Core policy;
- an `ActionOutcome` containing a stable result code and only safe result
  facts.

Interaction channels are `web`, `voice`, `mobile`, `automation` and
`integration`. Policy classes are `read`, `routine`,
`confirmation_required`, `restricted` and `forbidden`.

The orchestrator selects a handler by proposal type, evaluates policy before
execution and returns rejected or confirmation-required outcomes without
calling a domain service. A domain handler reloads authoritative owner state,
revalidates target and capability, converts the proposal into the existing
domain command and returns the confirmed domain result. The action correlation
identifier is passed through the domain service and adapters.

The first slice accepts one stable device target per proposal. Room/category
resolution, AI proposal acquisition, persistent idempotency claims and the
public Web/Voice endpoint are follow-up slices built on these contracts. They
must not be simulated inside this foundation.

Stable initial result codes use lowercase dotted values:

- `action.succeeded`;
- `action.partially_succeeded`;
- `action.failed`;
- `action.denied`;
- `action.confirmation_required`;
- `action.unsupported`;
- `target.not_found`;
- `device.offline`;
- `proposal.invalid`.

Audit events contain codes and correlation identity, not prompts, credentials
or provider payloads. Idempotency identity is mandatory for executable action
contexts. The first Web endpoint persists an owner-scoped claim before domain
execution and stores the complete typed outcome for safe replay. Reusing a key
with a different request is rejected, and an in-progress claim cannot start a
second execution.

## Consequences

- Web and Voice can converge on one Core authority without moving adapter rules
  into either client.
- Device services remain reusable and provider-specific translation stays
  behind the capability boundary.
- A positive action outcome can only be derived from the real domain result.
- Later Calendar, Email, Playback and Automation handlers can add typed
  proposals without weakening device validation.
- The Web endpoint cannot select another interaction channel; Core constructs
  its context as `web`. Voice will invoke the orchestrator internally with its
  authenticated session context.
- The initial contracts do not yet make physical Voice commands available;
  proposal acquisition, room semantics, endpoint wiring and response-plan
  selection remain required.

## Rejected alternatives

- Letting each client execute a proposal and interpret adapter results.
- Passing arbitrary tool names or untyped provider payloads through Core.
- Letting an AI model choose policy, confirmation or success state.
- Building a generic workflow engine before one physical action proves the
  contracts.
- Claiming idempotency before a durable claim/result store exists.
