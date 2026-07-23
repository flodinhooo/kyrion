# Kyrion Principles

These principles guide product and architecture decisions.

## 1. Local First

User data should be processed and stored locally whenever practical.

Cloud services may be supported, but they must be optional and transparent.

## 2. Privacy by Default

Kyrion must not send personal data to external services without an explicit
reason and clear user consent.

Integrations should request only the permissions they require.

## 3. AI Is Optional

Every essential function must remain usable without an AI model.

Artificial intelligence is an interaction and automation layer, not a required
foundation of the platform.

## 4. Controlled Actions

AI models must never receive unrestricted access to the operating system,
network, email accounts or connected devices.

Every action must pass through explicitly defined tools, validation and
permission checks.

## 5. Human First

The user must understand what Kyrion is doing.

Important or destructive actions should be visible, reviewable and, where
appropriate, require confirmation.

## 6. Modular by Design

External systems should be connected through integrations with clearly defined
interfaces.

The platform core must not depend directly on a particular device manufacturer
or service provider.

## 7. Useful Before Impressive

A small feature that is used every day is more valuable than a complex feature
that only demonstrates technical capability.

## 8. Progressive Complexity

Kyrion should begin with the simplest architecture that supports the current
requirements.

New infrastructure should only be introduced when it solves a concrete
problem.

## 9. Offline Friendly

Local device control and essential platform functions should continue to work
when the internet connection is unavailable.

## 10. Beautiful Software

Kyrion should be technically reliable and visually pleasant.

The interface should feel coherent, calm and intuitive rather than exposing
unnecessary technical complexity.

## 11. Observable and Auditable

Actions, errors and automation executions should be traceable.

Users should be able to understand what happened, when it happened and which
component initiated it.

## 12. Secure by Default

Authentication, authorisation, secret management and network boundaries must be
considered from the beginning, even when the first deployment has only one
user.
## 13. International from the Beginning

Kyrion should support German and English from its first user-facing version.

User-interface text must be separated from application logic and stored in
dedicated translation resources.

English is the primary technical language and acts as the fallback user-interface
language.

The architecture should allow additional languages to be introduced later
without rewriting existing features.
