# Platform diagnostics and action inspection

The existing Web System services surface remains the single service overview.
Its status contract is `healthy`, `degraded`, `offline` or `unknown`, with bounded
diagnostic reason codes translated in German and English.

Web's successful response proves that request was served. Core, AI, STT and
Ollama probes validate the expected response body; an HTTP 200 alone is not
healthy. PostgreSQL is checked with a Core-owned `SELECT 1`. HA reports the last
explicit import attempt, successful attempt and correlation ID. Gateway services
reuse the authenticated gateway heartbeat. Old child readiness cannot outlive
an offline/unknown parent. Missing Voice, Zigbee and Spotify receiver observations
are shown as unknown, not inferred from installation or configuration.

No independent Voice microphone/playback health, Spotify playback success,
restart requirement or update requirement is invented. Gateway process readiness
is not physical end-to-end acceptance. Probe success timestamps describe the
current request; they are not a durable uptime history. HA sync timestamps and
gateway heartbeats use existing persistent evidence. If Core authentication is
unavailable, the protected page reports its existing error state; this is not an
out-of-band monitoring system.

The device catalog adds a diagnostic reason for absent, stale, offline and
degraded observations. Existing capability names are retained for compatibility:
`power.set`, `light.setBrightness`, `light.setColour`. Web and Voice share this
catalog. HA devices advertise read capabilities only. Core validates capabilities
again for synchronous and queued commands, including direct Web calls.

## Action inspector

Expand **Inspect execution** on an Activity item. Core queries the complete
owner-scoped correlation from the existing activity table, ordered by audit
sequence, capped at 1000 rows with explicit truncation. It does not reconstruct
missing steps from a recent-page subset. Existing integrity seals remain intact.

New device actions record proposal, capability, policy acceptance, resolved
Kyrion target IDs, adapter invocation, adapter confirmation and final outcome.
Actor, channel/provider source, timestamps and correlation are retained. Duration
is calculated only when actual start and terminal events exist. No prompt, token,
provider address or unfiltered provider error is shown. The timeline projection
allowlists stages, diagnostic codes, providers and UUIDs without changing the
underlying signed audit events.

When an orchestrator outcome exists, the inspector reuses its persisted target
names and requested/succeeded/failed counts. Queued Web commands also record their
validated target and capability, and the gateway completion retains that
correlation. Adapter completion is distinct from a multi-target action's final
completion. No missing outcome or timing is reconstructed from current device state.

Failure stages cover rejection, target/capability failure, gateway offline,
timeout, malformed results and provider failure. Partial success remains an
explicit orchestrator outcome. Ambiguous/invalid Web and Voice proposals and
stale session validation are audited even before execution. Historical actions
may have fewer stages; their unavailable detail is stated rather than fabricated.

Gateway command IDs now retain the parent action correlation. Some adapters
confirm transport/command execution rather than measuring the resulting physical
state. The inspector therefore says **Adapter confirmed execution**, not
**Physically verified**. Generic gateway `EXECUTION_FAILED` remains a generic
provider error unless more precise evidence exists. No new execution authority,
parallel log store or AI diagnosis engine is introduced.
