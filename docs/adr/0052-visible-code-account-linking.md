# ADR 0052: Visible code entry and streamlined local account linking

Status: accepted for implementation, 2026-11-12, explicitly requested by owner.

## Decision

Expose account linking as the first local Profile section and navigation item.
The authenticated local user confirms their password and explicitly starts
linking. Show the short code prominently with Copy and Open website actions.
The website account menu exposes Connect account and a dedicated account tab
accepts the code. A same-origin, CSRF-protected POST validates and normalizes it
and redirects only to the configured central provider's device-verification
page, with the code prefilled. The provider confirms the central identity.

Keep RFC 8628 and Core as the authoritative proof/link boundary. No website
database access to installations, email matching, callback relay, webhook,
arbitrary LAN URL or provider administration credential is introduced. The
provider validates the code; Core polls its confidential device credential and
checks signed issuer/audience/subject and the initiating local session.

After provider approval, the local UI finishes LINK automatically through the
existing complete endpoint. Initial local password-confirmed Link plus provider
approval are the explicit user consent; remove the redundant final local click.
Core's current-session, one-use, expiry, permission and audit checks remain.
LOGIN retains its existing confirmation behavior. This supersedes only the
final extra local LINK confirmation described by ADR 0041/identity UI docs.

The public website never claims a link succeeded based on code submission.
The local installation displays success only after Core completes it. Code
entry reveals no user identity, creates no permissions and accepts no target
host. Invalid codes, missing session and invalid CSRF fail safely. Preserve
local password login and offline access.

## Verification

Test code normalization/rejection and fixed-host verification URLs, browser
account-tab/menu behavior, local first-section discoverability, and automatic
completion only after CONFIRM with the existing authenticated flow cookie.
Verify DE/EN text encoding and the actual public/local pages after publishing.
