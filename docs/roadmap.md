# Kyrion Roadmap

This roadmap describes outcome-oriented direction rather than fixed deadlines.
It implements the priorities in [Product Strategy](product-strategy.md): build
the trustworthy orchestration layer first, then daily usability, followed by
energy and operational differentiation. Integration breadth must not outrun
permissions, diagnosis, audit and recovery.

## Milestone 0 — Foundation

Goal: establish Kyrion's identity, structure and architectural boundaries.

- [x] Create the monorepo structure
- [x] Define internationalisation, vision and principles
- [x] Document the initial architecture
- [x] Create the repository and initial project documentation

## Milestone 1 — Native Nanoleaf Reference Slice

Goal: prove a local, owner-scoped integration end to end.

- [x] Discover and authorise local Nanoleaf controllers
- [x] Encrypt and persist owner-scoped credentials
- [x] Read state and control power, brightness, colour, temperature and scenes
- [x] Persist rooms and device assignments
- [x] Build German and English integration and Home surfaces
- [x] Route Web and bounded Velora power commands through Core
- [x] Add persistent bounded availability observations
- [ ] Complete physical German and English text/Voice verification
- [ ] Complete focused HTTP boundary and failure tests

Nanoleaf remains the native reference adapter used to prove generic contracts;
it is not a reason to reproduce every manufacturer integration.

## Milestone 2 — Trustworthy Orchestration Foundation

Goal: make Core the provider-neutral trust and operations layer.

- [ ] Stabilise device identity, state, availability, capability, event,
  command and result contracts
- [ ] Implement a Core-owned Device Manager and target resolution
- [ ] Model households, members and initial owner/member/guest roles
- [ ] Define routine, confirmation-required, high-risk and forbidden action
  policy classes
- [ ] Define Observe, Control and Manage integration profiles backed by granular
  Core permissions and scoped to approved households, rooms and devices
- [ ] Record proposed, rejected, confirmation-required and executed actions
  with actor, source and correlation ID
- [ ] Define integration health and diagnostic reason contracts
- [ ] Separate discovered candidates from explicitly approved devices
- [ ] Define a versioned internal adapter contract before a public plugin API
- [ ] Add cross-owner, ambiguity, malformed-output and adapter-failure tests

Success criterion:

> Web, Velora and integrations use the same Core-owned identity, capability,
> policy and audit path without exposing provider credentials or trusting an
> adapter to establish authority.

## Milestone 3 — Safe Integration Breadth Without Lock-In

Goal: connect mature ecosystems without making any one of them Kyrion Core.

- [ ] Add an optional Home Assistant adapter with selectable Observe, Control
  and Manage profiles
- [ ] Translate bounded HA devices, areas, capabilities, state and health into
  Kyrion models without exposing HA entity semantics to consumers
- [ ] Create a pre-change restore point before adapter onboarding and permission
  elevation, then show backup coverage and restore-verification status
- [ ] Diagnose adapter availability, stale state and mapping failures
- [ ] Allow Control and Manage operations only through typed Core commands,
  granular permissions and policy validation
- [ ] Import external identity and provenance without silently deleting HA
  entities or automations
- [ ] Classify automation migration as fully translatable, partial or
  unsupported before any owner-approved cutover
- [ ] Add Wake-on-LAN as a small native infrastructure integration
- [ ] Define criteria for native integration versus ecosystem adapter work
- [ ] Add bounded background observations or device events
- [ ] Reconcile provider addresses safely after network changes

Home Assistant provides early integration breadth. It remains optional,
replaceable and subordinate to Kyrion identity, policy, audit and UX.

## Milestone 4 — Managed Gateway and Operational Safety

Goal: operate the ordered Raspberry Pi as a secure edge node while Core remains
on the development PC or a later server.

- [x] Select and order the Raspberry Pi 5 and dedicated Zigbee/Thread hardware
- [ ] Define authenticated gateway registration, identity, heartbeat and health
- [ ] Define stable adapter identity without fixed USB device-path assumptions
- [ ] Buffer bounded state and events during temporary network interruption
- [ ] Validate Raspberry Pi, Zigbee, Thread, Bluetooth and USB voice hardware
- [ ] Deploy and monitor the gateway agent and OTBR safely
- [ ] Implement Core-owned restore-point manifests across applicable database,
  provider, coordinator and gateway backups
- [ ] Establish retention, integrity checks and verified-restore procedures
- [ ] Define signed update channels and rollback foundations
- [ ] Configure secure local and later remote access without exposing device
  control endpoints publicly

Continuing local automation during Core outages is a later policy replication
slice, not an initial gateway promise.

## Milestone 5 — Understandable Daily Product

Goal: make a heterogeneous home simple for every authorised household member.

- [ ] Build provider-neutral room, device, favourite and scene views
- [ ] Add Simple Mode and Expert Mode over the same authoritative data
- [ ] Build an Integration Manager, discovery inbox and health explanations
- [ ] Add clear pairing and approval flows
- [ ] Show Observe, Control and Manage access plus granular scopes and backup
  coverage during integration onboarding
- [ ] Build an automation editor using capabilities rather than protocols
- [ ] Add a human-readable execution timeline and “Why did this not run?”
  explanations
- [ ] Add explicit ambiguity clarification in text and voice conversations
- [ ] Complete responsive German and English UX in both themes
- [ ] Add safe remote access after throttling, session controls and audit exist

## Milestone 6 — Hardware and Protocol Validation

Goal: prove the abstractions against the ordered devices as separate vertical
slices rather than claiming success from pairing alone.

- [ ] Zigbee lamps, button and motion events through the dedicated coordinator
- [ ] Matter-over-Thread contact events through OTBR and the dedicated adapter
- [ ] Bluetooth discovery and bounded device access through the gateway
- [ ] Shelly and myStrom Wi-Fi state and capabilities
- [ ] Voice satellite capture, playback, health and Core-confirmed actions
- [ ] Restart, temporary-network-loss and unavailable-device recovery tests

Kyrion uses mature radio stacks and does not implement its own Zigbee, Thread
or Matter protocol stack.

## Milestone 7 — Energy and Operational Differentiation

Goal: deliver measurable household value and verifiable trust features.

- [ ] Integrate Solar Manager without reproducing its control algorithms
- [ ] Combine energy state with authorised household and device automations
- [ ] Add energy dashboards and explanations
- [ ] Add a Privacy Receipt showing relevant external data flows
- [ ] Complete child, guest, technician and time-limited support roles
- [ ] Verify signed update rollback and automated restore tests
- [ ] Add Docker, Proxmox and NAS monitoring as integrations, not replacement
  platforms
- [ ] Pilot Kyrion in approximately five to ten representative households

The initial target is technically interested Swiss homeowners with multiple
systems, household members who need simple operation and potential energy
assets such as PV, batteries, wallboxes or heat pumps.

## Milestone 8 — Mobile and Local Voice Refinement

- [ ] Create the Expo mobile application
- [ ] Add authentication, device state, quick actions and notifications
- [ ] Add assistant access under the same Core policies
- [ ] Replace prototype browser STT/TTS with explicitly selected local providers
- [ ] Add wake-word, interruption and voice-device management
- [ ] Keep Ollama and other model runtimes optional and replaceable

## Later Platform and Commercial Phases

Only after the contracts and operating model are proven:

- [ ] Productise three AI modes over the same provider contracts: Kyrion Local,
  Kyrion Managed AI and Bring Your Own AI
- [ ] Add hardware detection and reproducible CPU, RAM and VRAM benchmarks that
  recommend honest local model profiles and expected latency
- [ ] Allow STT, LLM and TTS routing to be selected independently in Expert Mode
  while Simple Mode offers understandable Local, Managed and External choices
- [ ] Define the privacy, residency, retention, consent, metering, cost-control
  and support model before implementing Kyrion Managed AI
- [ ] Prove at least one bounded external AI provider plugin without exposing
  credentials to Web or allowing the provider to bypass Core policy and audit
- [ ] Stabilise versioned plugin manifests and SDK contracts
- [ ] Prove plugin permissions, isolation, signing, updates and rollback with
  official first-party plugins
- [ ] Add Jellyfin and media scenes
- [ ] Evaluate pre-installed Kyrion hardware
- [ ] Evaluate installer and managed-support offerings
- [ ] Explore hospitality pilots, followed only later by suitable business use
  cases
- [ ] Keep medical, care and legal functionality behind dedicated expert,
  regulatory and safety review
- [ ] Open a reviewed marketplace only after lifecycle and compatibility are
  operationally proven

Kyrion will not initially build its own NAS operating system, hypervisor, media
server, VPN or cryptographic primitives, general-purpose AI model, medical
diagnostics, autonomous legal advice or complete commercial appliance.
