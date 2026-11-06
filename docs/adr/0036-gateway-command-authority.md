# ADR 0036: Explicit queued Gateway authority

Date: 2026-11-06
Status: Accepted for the bounded Gateway authority slice

## Context

Queue owner IDs identify resources, not the person who requested execution.
Authentication of a polling node cannot establish authority for queued actions.
The current queue loses the human principal across asynchronous dispatch.

## Decision

Core persists typed authority separately from command payload: resource Space,
principal kind and ID, required permission, capability, and (where applicable)
automation grant or HOME Voice session. Correlation remains a separate queue field.
Every production enqueue requires explicit authority; there is no owner fallback.
Core validates authority at enqueue and after atomic claim, before returning any
payload to an authenticated node. Denials become terminal failed results and are
audited with the original principal, Space and correlation. Legacy pending rows
without provenance are failed closed; historical completed/running rows are not
rewritten or attributed to an invented human.

Human authority uses current TenantBoundary and RBAC. These are durable commands:
logout does not revoke a human's accepted intent; disabling membership, changing
roles or suspending the Space does. HTTP authentication remains mandatory at entry.

Replacing button bindings explicitly issues fresh grants attributed to the
authenticated configurator. Grants are bound to source button, gesture, node,
target and action through the current binding. Replacing/deleting a binding
revokes its old grant, even if recreated with identical values. Grant validation
also checks the configurator's current permissions. Historical bindings have no
grant and require explicit resaving. Node credentials do not issue grants.

HOME Voice retains a distinct integration principal, with a live satellite and
active unexpired dialogue session. It has only routine device capabilities;
Business Voice stays blocked. The existing server-created ActionContext supplies
this provenance without changing shared Voice code.

No automatic replay of running commands is introduced: uncertain physical effects
must not be retried as though execution had not occurred. A future retry mechanism
must retain and revalidate the same authority. Revocation after release cannot
recall an already dispatched device operation.

## Consequences

V42 is additive and does not rewrite existing migrations or sealed audit history.
Old pending commands fail on claim. Existing button bindings need reviewed resave.
Core remains the sole authority; no gateway wire contract exposes grants or secrets.
Physical acceptance and deployment are separate from source verification.
