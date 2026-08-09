# Product Strategy

## Strategic thesis

Kyrion should not compete by recreating Home Assistant, every radio protocol or
an unrestricted general-purpose assistant. Its opportunity is to become the
understandable, secure and reliably operated orchestration layer above existing
devices, integrations and local infrastructure.

The intended position is between powerful technical platforms and simple but
opaque consumer ecosystems:

> Combine the openness and local capability of advanced home automation with
> the usability, diagnosis and operational reliability expected from a
> consumer product.

Kyrion's durable advantage should come from explaining, authorising,
monitoring, coordinating and recovering what integrations technically enable.
Integration count alone is not the product moat.

## Product promise

A concise direction for the product is:

> One home. One secure control surface. Your data under your control.

This promise must be supported by verifiable behaviour rather than broad
claims:

- essential functions continue without internet access;
- external data transfers are visible and optional where practical;
- customer data is not used for AI training without explicit consent;
- support access is time-limited, permissioned and audited;
- updates are signed and can be rolled back;
- backups are tested through real restoration;
- every AI-proposed action is authorised and traceable.

Privacy is necessary but not sufficient. Kyrion should combine privacy with
simple operation, reliability and understandable failure handling.

## What Kyrion owns

Kyrion should build and own the product-specific trust and orchestration layer:

- a provider-neutral device, state, capability, event and command model;
- households, identities, roles and permissions;
- a policy and confirmation engine for users, automations and AI proposals;
- understandable integration health and diagnostic explanations;
- correlated action and automation audit trails;
- Simple Mode and Expert Mode over the same authoritative state;
- a safe automation editor with an execution timeline and explanations;
- transparent external data-flow records;
- signed update, rollback, backup and verified-restore foundations;
- authenticated gateway and voice-satellite management.

The defining distinction is that an integration may know how to operate a
device, while Kyrion knows whether, why and for whom that operation should run,
how it is explained and how failure is recovered.

## What Kyrion integrates

Kyrion should reuse mature protocol and ecosystem work through bounded
adapters. It should not initially build:

- a Zigbee, Thread or Matter protocol stack;
- a NAS operating system or hypervisor;
- a media server;
- a general-purpose foundation model;
- custom VPN or cryptographic primitives;
- autonomous medical diagnosis or legal advice;
- a complete commercial appliance before the software is product-ready.

Home Assistant should be introduced early as an integration engine for breadth.
During onboarding the owner selects an Observe, Control or Manage access
profile. These profiles map to granular Core-enforced permissions; even Manage
does not expose arbitrary Home Assistant services. Home Assistant entities and
services are untrusted provider data and must be translated into Kyrion-owned
identities, capabilities, states and health information. Home Assistant is
optional and replaceable; it never owns Kyrion permissions, policies, audit or
product state.

Integration and device onboarding follows a backup-first rule. Kyrion creates
an applicable pre-change restore point before connecting an integration,
raising its permissions, pairing or migrating devices and performing other
material configuration changes. Recovery coverage and restore verification are
reported honestly when an external system cannot provide a complete backup.

Native integrations remain important when they prove Kyrion contracts, improve
local reliability or diagnosis, close an important functional gap, support the
gateway, or serve a strategic domain. Nanoleaf remains the native reference
integration. The ordered Zigbee, Thread, Bluetooth, Wi-Fi and voice hardware
will validate the gateway and abstraction boundaries without committing Kyrion
to rebuilding mature radio stacks.

## Velora's role

Velora is a controlled interaction and explanation layer, not the authority.
It should help users:

- find and understand devices and current state;
- draft automations;
- summarise integration and automation failures;
- explain energy events;
- propose actions using owner-visible capabilities.

Velora must never execute arbitrary provider APIs or operating-system commands.
Every proposal passes through Core target resolution, permissions, policy,
confirmation and audit. Routine authorised lighting may execute immediately;
server restarts require an applicable policy or confirmation; door, firewall,
destructive and other high-risk operations require stronger restrictions.
Medical decisions are never autonomous.

## Initial customer and differentiation

The strongest early users are technically interested Swiss homeowners with
multiple smart-home ecosystems and a household that also needs simple daily
operation. Solar generation, batteries, wallboxes or heat pumps create both a
real coordination problem and measurable value.

Solar Manager is therefore a promising future integration. Kyrion should not
copy its control algorithms; it should combine energy information with home
state, weather, devices, infrastructure and authorised user preferences.

The first meaningful validation should occur in the developer's real home,
followed by a small pilot of approximately five to ten representative
households before broad consumer positioning or dedicated commercial hardware.

## AI deployment choice as a product principle

Kyrion should eventually offer three understandable AI operating modes over one
provider-neutral architecture:

1. **Kyrion Local** runs suitable STT, LLM and TTS models on user-controlled
   hardware. Setup may detect and benchmark CPU, RAM and available VRAM, then
   recommend honest hardware profiles such as CPU-only, Local Lite, Local
   Standard or Local Performance. Complete offline operation is a product
   capability, not a prerequisite imposed on every customer.
2. **Kyrion Managed AI** runs selected AI workloads on Kyrion-operated
   infrastructure for users who do not own suitable accelerator hardware or do
   not want to manage models. Local Core remains authoritative, and only the
   minimum context required for the selected workload should leave the home.
3. **Bring Your Own AI** connects an owner-selected external provider through a
   bounded provider plugin or adapter. Possible providers include OpenAI,
   Gemini, Anthropic, Perplexity and remote or local model endpoints. Provider
   credentials remain protected and the provider never gains Core authority.

The user-facing promise is choice rather than model terminology: private and
local, simple and Kyrion-managed, or use an existing AI provider. Expert users
may choose independently where speech recognition, reasoning and speech
synthesis run; Simple Mode should offer an automatic managed choice without
requiring knowledge of model names or VRAM.

This direction strengthens the intended positioning:

> Local-first, cloud-capable and provider-agnostic. The owner decides where AI
> processing runs.

It does not authorise immediate cloud implementation. Local streaming should be
stabilised first, while its contracts remain suitable for later managed and
external-provider adapters. Commercial terms, data processing, residency,
retention, consent, cost controls and operational support require explicit
product and legal decisions before Kyrion Managed AI is offered.

## Sequencing rule

Development priority is:

1. trustworthy orchestration foundation;
2. understandable daily household operation;
3. energy, privacy and operational differentiation;
4. voice, dedicated hardware and adjacent domains on the proven foundation.

Every slice should improve a real user outcome. New integration breadth must
not outrun identity, policy, diagnosis, audit, update and recovery maturity.
