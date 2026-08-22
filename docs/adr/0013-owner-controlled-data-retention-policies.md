# ADR 0013: Owner-Controlled Data Retention Policies

- Status: Accepted
- Date: 2026-08-22

## Context

Conversation history, activity events and personal memory have different trust
and product purposes. A single hidden cleanup period would be surprising and
could destroy information the owner expects Kyrion to retain. Retention must
also remain separate from future household roles and legal or backup policy.

## Decision

Core stores one owner-scoped policy for each domain: conversations, activity
and personal memory. Supported choices are `keep_forever`, `30_days`,
`90_days`, `365_days` and `3_years`. New owners and missing rows resolve to
`keep_forever`.

This first slice persists and exposes policy intent but does not enforce
automatic deletion. The API returns `enforcementActive: false`, and Web states
clearly that changing the setting deletes nothing yet. Enforcement requires a
separate reviewed slice with previews, explicit activation, backup interaction,
transaction boundaries and auditable cleanup results.

## Consequences

- Retention intent is explicit, typed and owner-scoped.
- No data is deleted merely by deploying or configuring this slice.
- Future enforcement can use a stable policy without inventing defaults.
- Household administration, legal holds, export and archival remain future
  policies rather than implicit side effects.
