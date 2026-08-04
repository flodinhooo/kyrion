
---

# 5. `docs/roadmap.md`
# Kyrion Roadmap

This roadmap describes direction rather than fixed deadlines.

## Milestone 0 — Foundation

Goal: establish the identity and basic structure of Kyrion.

- [x] Create the monorepo structure
- [ ] Define the internationalisation strategy
- [ ] Define product vision
- [ ] Define project principles
- [ ] Document the initial architecture
- [ ] Create the root README
- [ ] Initialise Git
- [ ] Create the remote GitHub repository
- [ ] Make the initial commit

## Milestone 1 — Nanoleaf Prototype

Goal: control an existing Nanoleaf installation from Kyrion.

- [ ] Identify the exact Nanoleaf model
- [ ] Confirm that the panels are connected to the local network
- [ ] Discover or configure the controller IP address
- [x] Generate and securely persist a local API authentication token
- [x] Read the current device state
- [x] Switch the panels on and off
- [ ] Change brightness
- [x] Display meaningful connection and API errors
- [x] Build a minimal Kyrion dashboard
- [x] Add German and English translations
- [x] Add a language selector
- [x] Persist the selected language locally

Success criterion:

> A user can open Kyrion Web and reliably control the existing Nanoleaf panels
> without using the official Nanoleaf application.

## Milestone 2 — Integration Boundary

Goal: separate device-specific communication from the user interface.

- [ ] Define a generic device model
- [ ] Define integration capabilities
- [x] Move Nanoleaf logic behind an integration interface
- [ ] Add command execution results
- [x] Add basic activity logging
- [x] Decide whether the dedicated Kyrion Core service is now justified

## Milestone 3 — Text Assistant

Goal: control an existing integration using natural language.

- [ ] Create the AI service
- [ ] Connect a local or optional remote model
- [ ] Define a tool schema
- [ ] Convert text requests into structured tool calls
- [ ] Validate all tool calls in Kyrion Core
- [ ] Display action results in the web interface

Example:

> “Set the Nanoleaf brightness to 30 percent.”

## Milestone 4 — Always-On Host

Goal: run Kyrion independently of the gaming computer.

- [ ] Evaluate mini-PC hardware
- [ ] Install a Linux server operating system
- [ ] Define service deployment
- [ ] Introduce Docker or another suitable deployment mechanism
- [ ] Configure backups
- [ ] Configure secure local and remote access
- [ ] Add monitoring and health checks

## Milestone 5 — Device and Media Expansion

Possible integrations:

- [ ] Wake-on-LAN
- [ ] Jellyfin
- [ ] Home Assistant
- [ ] smart lights
- [ ] network status
- [ ] photovoltaic data

The exact order depends on personal usefulness.

## Milestone 6 — Mobile Application

- [ ] Create the Expo application
- [ ] Add authentication
- [ ] Show device status
- [ ] Execute quick actions
- [ ] Add assistant chat
- [ ] Add notifications
- [ ] Evaluate speech input

## Strategic Phase 5 — Marketplace and Enterprise Edition

This phase begins only after Core, AI, automations and the main user interfaces
are stable. Its sequence is deliberately incremental:

- [ ] Stabilise internal integration and capability contracts
- [ ] Define versioned plugin manifests and SDK contracts
- [ ] Convert selected official integrations into first-party plugins
- [ ] Add plugin permissions, lifecycle management and audit events
- [ ] Define isolation, signing, review, update and rollback policies
- [ ] Introduce personal knowledge bases with explicit access scopes
- [ ] Define versioned knowledge-package contracts and evaluations
- [ ] Validate official domain packages before allowing third parties
- [ ] Design marketplace discovery, installation and licensing
- [ ] Define Community, Pro and Enterprise edition boundaries
- [ ] Add enterprise deployment, identity, support and compliance capabilities
- [ ] Open the marketplace to reviewed third-party publishers only after the
  security and compatibility model has proven reliable

See [Marketplace and Enterprise Vision](marketplace-enterprise.md) for the
architectural boundaries, possible domains and commercial direction.

## Future Ideas

- automation editor;
- email summaries;
- calendar summaries;
- local document search;
- voice personalities such as Velora;
- household users and permissions;
- plugin developer SDK;
- backup and restore;
- energy-aware automation;
- commercial or managed deployment options.
