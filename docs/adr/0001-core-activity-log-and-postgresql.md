# ADR 0001: Core-Owned Activity Log and PostgreSQL

- Status: Accepted
- Date: 2026-08-02

## Context

Kyrion needs a trustworthy activity view before it can execute device,
automation or integration capabilities. Browser-local entries would not prove
what Core validated or executed, and arbitrary payload logging could expose
private content. A durable Core boundary is now justified by this concrete use
case.

## Decision

Kyrion Core owns an append-only activity event log and exposes its recent
projection through `GET /v1/activity`. PostgreSQL is the initial durable store.
The development database uses a bind mount whose documented default is
`E:/Kyrion/Data/postgres`, keeping database files off the system drive.

Events contain a stable type and summary code, status, category, actor, source,
timestamp and correlation identifier. They do not contain prompts, message
bodies, credentials, tokens or unrestricted metadata. Core is the only writer;
the Web application reads events through its server-side proxy.

The current single-user development slice does not pretend to provide user
isolation. Actor identifiers are nullable so authentication can be introduced
without changing the event identity model. The activity log is not yet a
complete compliance audit trail.

## Consequences

- Core startup can produce the first real, confirmed event.
- Future proposed, approved and executed actions can share a correlation ID.
- Event summaries remain localisable in the UI through stable summary codes.
- PostgreSQL and Core become additional local development services.
- Retention, authenticated user ownership and tamper-evidence remain explicit
  follow-up work.
