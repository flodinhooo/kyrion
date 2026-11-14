# ADR 0068: Kyrion-branded identity screens and website-initiated account actions

Status: accepted for implementation, 2026-11-14, explicit owner request.

Keep authorization code + PKCE, state/nonce, verified email and protected website
sessions. Keycloak remains the password, verification and recovery authority.
Do not introduce password grant, iframe login, browser tokens, a password proxy or
administrator credentials in the website. Browser authentication still uses the
visible `auth.kyrion.ch` origin; branding does not make it same-origin or headless.

Provide an inherited Kyrion login theme: CSS/brand assets only, preserving upstream
forms, validation, password-manager attributes, error accessibility and security
templates. Registration, verification, recovery and device approval share that theme.
Keep production caching enabled; mount versioned theme resources and preserve the
previous realm settings before activation. No provider upgrade is part of branding.

Website account settings expose profile/password actions through supported Keycloak
application-initiated OIDC actions and return to the website. Start requires a
verified website session and CSRF proof; persist the expected central subject in
the short-lived, one-use flow and reject a different signed identity at callback.
An additive website-only migration preserves existing flows/sessions. The legacy
manage link returns to website settings, not the generic Keycloak account console.
MFA/passkey/session administration is not implied by these two implemented actions.

Test actual registration/mail verification, password recovery, session renewal,
browser restart, logout and replay rejection in an isolated Keycloak/Mailpit stack.
Use only the owner-designated separate mailbox for public acceptance; never reset
the owner's personal credentials. Read only new matching test mail, retain secrets
in ignored protected evidence, and report test stages without tokens or passwords.
