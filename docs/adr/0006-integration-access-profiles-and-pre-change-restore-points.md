# ADR 0006: Integration Access Profiles and Pre-Change Restore Points

- Status: Accepted
- Date: 2026-08-05

## Context

Kyrion must support existing households that keep Home Assistant while adopting
Kyrion incrementally and new households that onboard devices directly through
Kyrion-managed adapters. Forcing every Home Assistant connection to remain
read-only prevents useful controlled operation. Broad write access without
explicit scope would undermine Core authority and make migration unsafe.

Adding an integration, pairing a device, raising permissions or migrating
ownership can alter several systems. A database backup alone may not protect a
Home Assistant installation, Zigbee coordinator, Thread fabric or gateway
configuration. Recovery protection must therefore be part of the change
workflow rather than a later operations feature.

## Decision

### Integration access profiles

During integration onboarding the owner selects one of three user-facing
profiles:

1. **Observe** reads approved devices, rooms, capabilities, state, events and
   health information.
2. **Control** includes Observe and permits explicitly modelled Kyrion
   capability commands for approved targets.
3. **Manage** includes Control and permits explicitly supported configuration,
   assignment, pairing and lifecycle operations.

The profiles are presets over granular permissions rather than a single trusted
`readWrite` flag. Initial permission identifiers include:

```text
integration.read
integration.configure
integration.remove
device.readState
device.executeCommand
device.manage
automation.read
automation.manage
```

Adapters declare which permissions and operations they support. Core stores the
approved scopes, checks them for every request and records changes. Increasing
access requires explicit owner confirmation; reducing it takes effect
immediately. Device, room and household scopes may further restrict a profile.

Manage does not allow arbitrary Home Assistant service calls, provider APIs or
shell commands. Every operation remains a typed Kyrion command subject to Core
identity, capability, policy, confirmation and audit checks. Velora receives
only the resulting owner-authorised tool catalogue.

### Pre-change restore points

Kyrion creates a pre-change restore point before:

- completing integration onboarding, regardless of the selected profile;
- increasing integration permissions;
- pairing, importing, migrating, removing or materially reassigning a device;
- bulk-importing or activating automations;
- changing critical gateway, adapter or network configuration;
- applying Core, gateway or adapter updates.

A restore point is a Core-owned manifest that references all applicable
component backups and records their scope, creation result, integrity metadata,
retention class and restore-verification status. Components may include:

```text
Kyrion Core database and mappings
encrypted credential metadata and separately protected key material
Home Assistant backup
Zigbee coordinator or network backup
Thread fabric and OTBR configuration where safely exportable
gateway and adapter configuration
room, role, policy and automation dependencies
```

Kyrion distinguishes `complete`, `partial`, `unsupported` and `failed` backup
coverage. It also distinguishes a created backup from a restore-verified backup.
The UI must not claim complete recoverability when an external system cannot be
backed up or restored through a supported interface.

A failed required backup blocks the protected change. If a provider cannot
offer complete backup coverage, Kyrion presents the exact gap before the owner
can approve a limited operation. Destructive migration or removal must not use
an unsupported backup as if it were a rollback guarantee.

Normal state changes such as switching a light do not create restore points.
Retention, deduplication and storage quotas prevent onboarding checkpoints from
growing without bound. Restore procedures require periodic automated checks and
real scheduled restore exercises.

### Home Assistant coexistence and migration

The Home Assistant adapter supports all three access profiles. Onboarding first
creates the applicable restore point, then inspects and presents devices,
areas, capabilities and possible duplicates before importing mappings.

Imported records retain external identity and provenance. Kyrion does not
silently delete Home Assistant entities or automations. A device may remain
controlled through Home Assistant or be explicitly migrated to a native Kyrion
adapter. Migration creates another restore point, displays affected mappings
and automations, requires confirmation and verifies the new path before the old
path is disabled.

Arbitrary Home Assistant automations are classified as fully translatable,
partially translatable or unsupported. Unsupported semantics remain in Home
Assistant until the owner deliberately replaces them.

## Consequences

- Existing Home Assistant users can adopt Kyrion without an all-at-once
  migration or loss of their current installation.
- New households can use native Kyrion onboarding without Home Assistant.
- Observe, Control and Manage are understandable choices while enforcement
  remains granular and capability-based.
- Backup providers, manifests, retention, integrity verification and restore
  orchestration become first-class Core concepts.
- Some onboarding flows take longer because a safe checkpoint precedes change.
- External backup limitations are visible and may prevent destructive changes.
- Provider-specific backup creation and restoration stay behind adapters;
  policy and recovery truth remain Core-owned.
