# Shared user and RBAC closeout

Date: 2026-09-14

## Result

The shared installation flow is usable on the Raspberry Pi. An owner can issue
a one-time invitation, a colleague can register at
`https://kyrion-node.local/signup`, and the owner can manage the colleague's
account and role from the Web interface.

The roles screen now presents role creation in a separate card above the role
list and permission editor. Its role-name input and create action have visible
borders and consistent spacing. The user management screen identifies the
current account by its authenticated ID instead of assuming that the first
alphabetically sorted account is the owner.

Owners can edit permissions on existing system roles, including `USER`, so an
installation can grant a shared user only the capabilities needed for an event.
The `OWNER` role remains protected by Core. The colleague's account remains a
normal invited account and does not receive a separate role automatically.

## Deployment

The updated ARM64 Core and Web images were built locally, transferred to the
Pi, loaded as `kyrion/core:pi-local` and `kyrion/web:pi-local`, and activated
with the existing Compose installation. PostgreSQL was preserved. The Core and
Web containers were recreated without rebuilding on the Pi.

Temporary deployment bundles, including the database dump and key copies, were
removed from the Pi after activation.

## Verification

- Core readiness returned `UP`.
- Web responded on its local port.
- `https://kyrion-node.local/` returned the expected redirect to authentication.
- The production ARM64 Core and Web image builds completed successfully.
- Web TypeScript checking and `git diff --check` passed.

The focused Core test run was blocked by an unrelated existing compile failure
in `YouTubeLinksTest.kt`, where the test fixture does not provide the required
`gateways` and `commands` parameters. Physical light and Spotify playback were
not re-tested as part of this deployment; the new account flow and permissions
should be verified once from the browser after the rollout.

## Owner handoff

1. Open **Profil → Sicherheit → Freund einladen**.
2. Send the generated code and `https://kyrion-node.local/signup` to the colleague.
3. After registration, open **Benutzerverwaltung**.
4. Assign the required permissions through the selected role, then test one
   light command and the Lounge from the colleague's account.

Invitation codes remain single-use and expire after 24 hours.
