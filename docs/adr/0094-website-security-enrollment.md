# Website security enrollment

Status: accepted for implementation, 2026-11-24.

Extend ADR 0068's authenticated, CSRF-protected, expected-subject-bound actions
with optional TOTP and passwordless WebAuthn enrollment. Keycloak owns challenges,
credential storage, validation, login policy and recovery. The website never
receives OTP seeds, private keys or administrator credentials. Enrollment is
explicit; do not force enrollment on existing users or modify personal credentials.

Passkeys must use the identity origin's RP ID, discoverable credentials and user
verification. Preserve password login and test recovery before production rollout.
Do not claim enrollment proves login enforcement. Test TOTP challenge rejection,
valid login, virtual authenticator registration/login, cancellation and account
binding. Real Windows Hello/mobile authenticator acceptance remains separate.
