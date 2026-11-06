# ADR 0039: Conservative presentation of owned calendar copies

Status: accepted HOME-05 first-slice direction, 2026-11-06.

## Context

Native household events and their Google copies can appear twice in the combined
calendar. Filtering by title/time or an unverified provider marker would hide
independent events or external edits. Personal availability-only disclosure must
not gain correlation metadata merely to improve presentation.

## Decision

Add a read-only, authenticated Core projection of the acting account's own
confirmed household-copy links for an actual selected Google calendar. Revalidate
active HOME, account and calendar read permission. Candidate links additionally
require the current concrete personal connection, active recipient grant, current
participant membership, recipient create/update permissions, SYNCED state, ETag
and the same delivered/native revision. The projection is bounded and uncached.
No other member's provider identity is exposed and no provider call is made.

The Web server may omit an owned Google copy only if its canonical household
event was successfully loaded in this response and provider ID/private marker,
ETag, revision, title/description and exact timed boundaries all match. No content-
only duplicate heuristic. Unknown/malformed links, changed remote data, revoked
grants, stale/uncertain delivery, all-day/recurring conversion or a missing native
view retain the Google event. Core/link failure falls back to showing copies,
never an empty calendar. Link metadata stays in the Web server, not its combined
browser response. The unresolved `primary` alias is not guessed from email.

Other members' shared-source overlays remain independently redacted, including
availability-only intervals. Do not add native correlation IDs or suppression
oracles to those private projections. Managing these overlays remains explicit
display selection, not a reason to expand disclosure.

## Calendar time correctness

While checking HOME-05, preserve original absolute instants when an existing
datetime-local field is unchanged. The original instant and initial form value
are editor state only and never authority in Core. This prevents an unrelated
title edit from truncating seconds or changing the second occurrence of a repeated
autumn hour to its first occurrence. Reject a newly entered nonexistent spring
clock time rather than silently normalizing it. Explicit selection between both
occurrences of a newly authored ambiguous time remains separate UI work.

## Consequences

No migration, new provider, role grant or remote write is needed. Native events
remain editable at one canonical identity. Retained or externally changed copies
remain visible. Live provider/browser acceptance and the V45 original-data
upgrade/restore remain distinct from fixture and source verification.
