# ADR 0018: Bounded Home Assistant snapshot import

Accepted 2026-09-06 for the consolidation phase.

Core imports registered devices with supported state entities using a fixed,
read-only REST template. No user-supplied templates, services, event subscriptions
or control path are accepted. The operator configures one HA installation and
its owner through server environment variables; the token stays server-side.

Existing integration connections, room assignments and device observations remain
authoritative. HA registry IDs are internal reconciliation keys. A separate
provider metadata table stores only bounded translated state and hardware labels,
not arbitrary provider payloads. Imported devices advertise read capabilities only.

Each sync updates HA-managed names and room mappings. This is an explicit exception
to preserving owner-managed imported metadata: exact trim/case-insensitive room
name matches use existing owner rooms, while absent or ambiguous matches clear
the assignment. No rooms are created and no synonyms or fuzzy matches are used.

Imports are transactional and serialized per owner. Missing devices become unknown;
provider unavailability is not evidence that every downstream device is offline.
Existing observations expire under the catalog's freshness policy.

ADR 0006 describes future profiles and restore orchestration. Those are deferred;
this import does not mutate HA. Shelly native experimental code remains evidence,
but HA is the selected sensor import path for this phase.

Protocol references: [REST template endpoint](https://developers.home-assistant.io/docs/api/rest/)
and [template functions](https://www.home-assistant.io/template-functions/).
