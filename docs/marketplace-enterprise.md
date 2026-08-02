# Kyrion Marketplace and Enterprise Vision

## Status

This document describes a long-term product and architecture direction. It is
not part of the initial prototype. The marketplace should only be implemented
after Kyrion Core, the AI service, automations and the user interfaces are
stable and their extension contracts have proven useful internally.

## Strategic Phase 5 — Marketplace and Enterprise Edition

Kyrion should evolve from one fixed application into a modular platform. Each
installation can select only the capabilities it needs, while Kyrion Core keeps
control of identity, permissions, execution, persistence and auditability.

The long-term goal is a platform comparable to an operating system for local AI
and automation solutions: Kyrion provides the trusted runtime, while plugins
and knowledge packages add integrations and domain-specific competence.

## Extension model

Kyrion distinguishes three kinds of extensions:

1. **Integration plugins** connect devices and external services and expose
   provider-independent capabilities.
2. **Feature plugins** add workflows, user-interface modules, automations or
   domain applications.
3. **Knowledge packages** add curated domain knowledge, retrieval sources,
   prompts and declarations for tools supplied by trusted plugins.

Knowledge packages do not reprogram Velora and must not execute actions by
themselves. They enrich the AI service's context. Any proposed action still
passes through typed contracts, permission checks, confirmation policies and
audit logging in Kyrion Core.

```text
Web / Mobile / Voice
          |
          v
     Kyrion Core  <---- Plugin registry and policy engine
       |     |
       |     +---- Integration and feature plugins
       |
       +---------- AI service (Velora)
                        |
                        +---- Knowledge packages
                        +---- Personal knowledge base
```

## Plugin framework

Every plugin should provide a versioned manifest that declares:

- its identity, version and compatible Kyrion API version;
- capabilities and tool schemas;
- required permissions and external network access;
- configuration and secret requirements;
- database migrations or owned storage;
- optional web and mobile extension points;
- events it publishes or consumes;
- health checks and lifecycle hooks;
- publisher identity, licence and integrity signature.

Plugins must use stable SDK contracts and must not access another plugin's data
or internal Core implementation directly. Installation, updates, disabling and
removal must be observable and reversible. Third-party code should eventually
run with isolation appropriate to its risk, such as a separate process or
container with restricted network, filesystem and secret access.

The plugin system should first be used for official internal integrations. A
public marketplace is justified only after versioning, permissions, isolation,
signing, review, migration and rollback have been validated in practice.

## Possible plugin domains

### Smart home

- Philips Hue, Home Assistant, Shelly and Nanoleaf;
- televisions, Sonos and other media systems;
- photovoltaic systems and heating;
- cameras and security devices.

### Hospitality

- kitchen displays and order management;
- table and reservation management;
- inventory and HACCP workflows;
- delivery-service integrations;
- voice interaction in kitchens.

### Medical and care environments

Possible future capabilities include documentation assistance, reminders,
patient administration, voice notes, daily planning, family contact and
emergency detection. These domains require separate regulatory, clinical,
privacy, safety and certification work. They must never be presented as
available merely because the generic plugin framework exists.

### Business

- CRM and ticket workflows;
- knowledge bases and document search;
- meeting notes;
- employee assistants and automations.

## Knowledge packages

Examples include hospitality, medical, legal, finance, home automation and
software-development knowledge. A package may contain curated documents,
retrieval indexes, terminology, workflows, evaluation cases and references to
tools exposed by installed plugins.

Packages require provenance, versioning, licensing, update policies and quality
evaluation. Domain knowledge must be separated from user data and executable
code. High-risk packages need stronger review and must communicate their limits.

## Personal knowledge bases

Each installation may maintain a private knowledge base containing preferences,
devices, rooms, family or household relationships, habits, calendars,
documents and reminders. Access is scoped per user or household. Sensitive data
remains local by default, is encrypted where appropriate and is only retrieved
for an authorised purpose.

Shared domain packages and personal knowledge must remain separate so that
packages can be updated without overwriting private information and private
information cannot accidentally be distributed with a package.

## Product editions

### Community Edition

- free and local-first;
- open-source Core;
- essential official integrations;
- self-managed installation and community support.

### Pro Edition

- premium plugins and knowledge packages;
- optional enhanced AI capabilities;
- guided installation, updates and professional support.

### Enterprise Edition

- on-premise installation;
- maintenance and support contracts;
- individual integrations;
- organisational identity, permissions and audit controls;
- privacy, compliance, training and operational services.

The exact feature and licensing boundaries remain a future business decision.
Local control, transparent permissions and safe execution should remain common
architectural foundations across all editions.

## Decisions required before implementation

- plugin packaging, discovery and distribution format;
- extension API and compatibility policy;
- process or container isolation model;
- signing, publisher trust and marketplace review;
- data ownership, migration, backup and uninstall behaviour;
- billing, licensing and offline licence validation;
- knowledge provenance and evaluation requirements;
- rules for regulated or safety-critical domains;
- support responsibilities for third-party plugins.

Each consequential decision should be recorded as an Architecture Decision
Record before marketplace implementation begins.
