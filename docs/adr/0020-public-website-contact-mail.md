# ADR 0020: Public website contact mail

Status: Accepted for the public contact-form implementation.

## Context

The public website is deployed on Vercel at kyrion.ch. Public inquiries and
interest in future testing need a contact channel using the existing Infomaniak
mailbox. This is separate from local installations and their Core authority.
The website previously had no backend integration. The requested contact channel
introduces one bounded exception to that informational-only deployment.

## Decision

The website owns a Node.js `POST /api/contact` Route Handler. It validates a
bounded JSON request, checks the configured browser origin and a honeypot,
then awaits authenticated SMTP delivery using Nodemailer. SMTP configuration,
sender and the single recipient come only from server environment variables.
The visitor can supply a validated Reply-To address, never routing headers.
The trusted `CONTACT_FORM_ORIGIN` comes from deployment configuration, not
request or forwarded host headers, because Next.js can use an internal hostname.

The endpoint does not authenticate users, persist inquiries, call Kyrion Core,
or access local installation data. Mailbox storage is the delivery destination.
Shared validation and typed response codes keep browser and server behaviour
consistent. An injectable abuse-policy boundary allows distributed rate limits
or a challenge verifier without changing the form or mail transport boundaries.

Use TLS on port 465 or mandatory STARTTLS on port 587, with certificate
verification and bounded connection timeouts. Do not retry mail automatically:
an interrupted SMTP exchange can have an ambiguous delivery outcome.

## Consequences

- Nodemailer is a small, established SMTP dependency; no separate provider,
  database, queue or service is introduced.
- Client locking prevents accidental repeated submissions while sending and
  after success. Exactly-once delivery across retries, tabs or server instances
  is not guaranteed without a durable idempotency store.
- A filled honeypot is rejected. Origin checks are browser protection, not bot
  authentication. No existing rate limiter is suitable for reuse on Vercel;
  distributed rate limiting/challenge protection remains an explicit follow-up.
- Logs contain only a generated correlation ID and bounded failure categories,
  never inquiry content, addresses, credentials or raw provider errors.
- Acknowledgement is required, but is not a complete privacy policy. Publish a
  reviewed policy and decide mailbox retention before a broader launch.
- SMTP acceptance is not proof of final inbox placement. Live delivery and
  Reply-To checks follow configuration by the mailbox owner.
