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

Core persists and exposes policy intent but does not run automatic deletion.
The API returns `enforcementActive: false`, and changing the policy never
deletes data. An owner may request a preview containing per-domain cutoffs and
record counts, then manually execute cleanup by entering the exact confirmation
`DELETE`. Core recalculates eligibility inside one transaction, deletes only the
authenticated owner's expired records and appends a data-minimised audit event.
Web recommends creating a backup before confirmation.

## Consequences

- Retention intent is explicit, typed and owner-scoped.
- No data is deleted merely by deploying or configuring this slice, and no
  unattended cleanup job is active.
- Manual enforcement is previewed, explicitly confirmed, transactional and
  owner-scoped.
- Household administration, legal holds, export and archival remain future
  policies rather than implicit side effects.
