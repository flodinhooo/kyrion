# Public contact form operations

## Architecture

`/contact` (German) and `/en/contact` (English) use the public site's normal metadata, layout,
themes and locale resources. `POST /api/contact` is a Node.js Route Handler on
Vercel. It awaits SMTP acceptance before reporting success. No inquiry database,
Core connection, authentication, attachments or visitor autoresponder is added.
See [ADR 0020](../../docs/adr/0020-public-website-contact-mail.md).

The shared validator normalizes Unicode, trims text, normalizes message line
breaks and lowercases only the email domain. It permits ordinary single ASCII
mailbox addresses (including plus addressing and punycode domains), not quoted
local parts, display names, lists or internationalized local parts. Limits:

| Field                  |   Maximum characters |
| ---------------------- | -------------------: |
| Name                   |                  100 |
| Email                  | 254 (local part: 64) |
| Subject                |                  160 |
| Company / organization |                  160 |
| Message                |                5,000 |
| Country                |                  100 |

Lengths use JavaScript UTF-16 string units, matching HTML `maxLength`. Contact
reason, experience and ecosystem choices are allowlisted. “None” is exclusive.
Testing fields remain optional and are omitted from mail for other reasons.
Privacy acknowledgement must be the boolean `true`; no policy link is invented.

The route accepts only same-origin JSON POST requests with a maximum streamed
body size of 32 KiB, including requests with absent/inaccurate Content-Length.
It rejects nonempty honeypots and disallows cross-site browser requests. The
allowed origin is explicitly configured in `CONTACT_FORM_ORIGIN`; Next.js may
use an internal request hostname behind a proxy, so request/forwarded host
headers are not treated as trusted origin configuration. Set the exact local
or preview origin when testing outside Production.
Origins can be forged by non-browser clients, so this is not a rate limiter.

`mail.ts` is marked `server-only`. All SMTP settings and routing addresses come
from server environment variables. From and To are fixed by configuration;
only a validated visitor mailbox is used for Reply-To. Text and HTML versions
contain the reason, name, email, company, subject, message and supplied testing
details. HTML escapes all visitor content. File/URL fetching is disabled in the
mail transport. No arbitrary visitor-supplied headers or mail options propagate.

SMTP uses verified TLS 1.2 or newer. Port 465 enables implicit TLS; port 587
requires STARTTLS before authentication. Other ports are rejected. DNS,
connection and greeting timeouts are five seconds; socket inactivity is limited
to fifteen seconds. The Vercel handler has a 60-second execution limit. The
browser ends an unresponsive request after 65 seconds and preserves its fields.

Failures return stable codes with no provider diagnostics. Server logs include
only `contact_delivery_failed`, a generated request ID and one bounded category:
`configuration`, `authentication`, `connection`, `timeout`, `rejected` or
`unknown`. Do not enable Nodemailer debug logging in production. The email
contains the correlation reference, but no IP address or user agent is collected
by application code. Vercel and the mail provider have their own operational logs.

## Required Vercel environment variables

Configure these **seven names**, all server-only, for the Production environment:

| Variable              | Value to configure                                                                       |
| --------------------- | ---------------------------------------------------------------------------------------- |
| `CONTACT_FORM_ORIGIN` | `https://kyrion.ch`; exact browser origin, without a path                                |
| `SMTP_HOST`           | `mail.infomaniak.com` for the existing Infomaniak mailbox                                |
| `SMTP_PORT`           | `465` (implicit TLS) or `587` (required STARTTLS)                                        |
| `SMTP_USER`           | Full mailbox login address                                                               |
| `SMTP_PASSWORD`       | The mailbox's SMTP/app password, as applicable to the account                            |
| `SMTP_FROM`           | One sender address authorized for that mailbox, normally the same address as `SMTP_USER` |
| `CONTACT_EMAIL_TO`    | One receiving mailbox address                                                            |

Do not include display names or comma-separated lists in address variables.
Do not use an Infomaniak Manager login password in place of the mailbox's SMTP
credential. Never use a `NEXT_PUBLIC_` prefix for these variables. No extra API
key or browser-exposed environment variable is required. `.env.example` contains
placeholders only; copy it to ignored `.env.local` for a deliberate local mail
test and replace values privately. Set `CONTACT_FORM_ORIGIN` to
`http://localhost:3001` for local development, or the exact preview URL for a
deliberate preview test. HTTPS is required except on loopback hosts. Redirect
alternate public hostnames to the configured canonical origin.

### Infomaniak preparation

1. Confirm that the intended mailbox exists, is active and can authenticate for
   SMTP. Retrieve or set its mailbox-specific credential in Infomaniak's account
   management; use its app-password mechanism if required by the account type.
2. Authorize the address used for `SMTP_FROM`. Prefer the authenticating mailbox
   itself; verify a configured alias is permitted before using it as sender.
3. Ensure `CONTACT_EMAIL_TO` is monitored and can receive mail. Replying to a
   delivered inquiry should target the visitor through Reply-To.
4. Use Infomaniak's Global Security tool to check SPF, DKIM and DMARC. If DNS is
   hosted elsewhere, apply the provider's required records at that authoritative
   DNS host. Keep the existing mail routing/MX records intact when configuring
   the Vercel website domain. Do not invent or duplicate SPF records.

Provider references:
[mailbox configuration](https://www.infomaniak.com/en/support/faq/2427/sync-your-emails-across-all-your-devices),
[SMTP ports](https://www.infomaniak.com/en/support/faq/468/understanding-mail-server-ports-and-protocols),
[SPF/DKIM/DMARC checks](https://www.infomaniak.com/en/support/faq/2692/automatically-check-spfdkimdmarc).

### Vercel preparation and live acceptance

1. Keep the current Next.js deployment and Node.js runtime. Do not switch this
   route to Edge or configure static-only export. Outbound SMTP 465/587 is
   supported; port 25 is blocked. See [Vercel SMTP guidance](https://vercel.com/kb/guide/serverless-functions-and-smtp).
2. Add the seven variables under Project Settings > Environment Variables. Scope
   real mailbox credentials to Production; enable Preview only deliberately,
   ideally with a separate test recipient and protected preview deployment.
3. Redeploy after saving environment variables. No Vercel or Infomaniak settings
   are changed by this implementation.
4. Submit one intentional inquiry from the deployed `/contact` page. Check the
   receiving inbox and spam folder, inspect both text/HTML content, and verify
   Reply-To. Also check an optional testing-interest submission and the German
   page. Do not infer final inbox placement solely from SMTP acceptance.
5. If delivery fails, inspect the safe failure category in Vercel function logs.
   Check configuration, mailbox authentication, permitted sender and provider
   limits privately; do not paste credentials or raw SMTP errors into tickets.

## Abuse, privacy and reliability follow-ups

- **Before a wider audience:** add distributed request limits, for example a
  Vercel Firewall rule on `POST /api/contact` or an appropriately scoped shared
  limiter. No suitable Vercel-compatible implementation exists in the monorepo.
  In-process maps would not protect across serverless instances and are not used.
- Add a server-verified CAPTCHA/Turnstile challenge if observed abuse warrants it.
  `ContactDependencies.checkAbuse` is the pre-delivery extension point. Verify
  tokens on the server and fail closed; keep provider secrets server-only.
- Publish a reviewed privacy policy, decide inquiry/mailbox retention and deletion
  procedures, and document Vercel/Infomaniak processing as appropriate. The required
  acknowledgement is not a complete policy. No `/privacy` page currently exists.
- Restrict mailbox access and monitor volume, delivery failures and provider
  sending limits. This endpoint has no newsletter subscription or marketing opt-in.
- Client locking prevents accidental duplicates during submission and removes
  the submit action after success. There is no automatic retry. SMTP timeouts can
  leave delivery uncertain; manual retries, reloads and separate tabs can still
  duplicate mail. Durable idempotency would require shared storage if later needed.
- Fields stay in the current page on failure, including testing selections.
  Inquiry drafts are not written to localStorage or server persistence. Reloading
  or leaving the page may lose the draft. JavaScript is required; without it the
  form uses POST (never a query string) and the route rejects the unsupported body.

## Verification

Run the existing lint, typecheck, formatting and production build commands, then
`pnpm --filter website test`. The existing Playwright runner also executes pure
validation, email rendering, SMTP configuration and injected delivery tests;
there is no second test framework. Browser tests cover validation, optional
fields, duplicate clicks, success, failure retention, themes and localization.

The test server explicitly sets a loopback form origin and blanks all six mail variables, even when local mail
configuration exists. Browser success/failure tests intercept their own requests;
server logic tests use injected delivery functions. Tests never send real email.
Live Infomaniak delivery remains an owner-configured deployment acceptance step.
