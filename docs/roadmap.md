
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
- [ ] Generate a local API authentication token
- [ ] Read the current device state
- [ ] Switch the panels on and off
- [ ] Change brightness
- [ ] Display meaningful connection and API errors
- [ ] Build a minimal Kyrion dashboard
- [ ] Add German and English translations
- [ ] Add a language selector
- [ ] Persist the selected language locally

Success criterion:

> A user can open Kyrion Web and reliably control the existing Nanoleaf panels
> without using the official Nanoleaf application.

## Milestone 2 — Integration Boundary

Goal: separate device-specific communication from the user interface.

- [ ] Define a generic device model
- [ ] Define integration capabilities
- [ ] Move Nanoleaf logic behind an integration interface
- [ ] Add command execution results
- [ ] Add basic activity logging
- [ ] Decide whether the dedicated Kyrion Core service is now justified

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
