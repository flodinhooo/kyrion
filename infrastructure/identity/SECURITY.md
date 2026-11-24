# Optional website security enrollment

The website starts authenticated, CSRF-protected actions for TOTP, passwordless
WebAuthn and recovery codes. Existing local password access remains independent.
No administrator credentials, OTP seed or WebAuthn private key enters the website.
The normal browser redirect uses the inherited Kyrion identity theme.

## Provider prerequisites

`security-policy.json` is a **partial settings patch**, never a complete realm
import. Read the current realm first and preserve all other settings. Snapshot
the realm, browser executions and required-action configuration privately before
applying. The RP ID is exactly `auth.kyrion.ch`; do not widen it to the parent
domain or substitute the website origin. Existing credentials must be reviewed
before changing an established RP ID. Password login remains available.

Enable these required actions without setting them as mandatory defaults:
`CONFIGURE_TOTP`, `webauthn-register-passwordless`,
`CONFIGURE_RECOVERY_AUTHN_CODES`. In the existing browser's conditional 2FA
subflow, enable `auth-recovery-authn-code-form` as `ALTERNATIVE`, preserving
the configured-user condition, credential condition and OTP alternative.
Do not turn recovery into an unconditional password bypass or disable OTP.

Users enroll explicitly on their own device. After authenticator enrollment,
choose Save recovery codes and store them outside that device. Do not send codes,
seeds or authenticator exports to support. Losing a device is not resolved by
silently clearing its credential; credential removal requires separate verified
account recovery. This slice adds enrollment and login, not a credential listing
or removal UI. Advanced provider administration stays operator-only.

## Verification

`apps/website/full-identity/security.spec.ts` uses only the fixed disposable
loopback provider. It creates a synthetic verified account and tests actual
enrollment, wrong-code rejection, fresh TOTP login, recovery login and a virtual
CTAP2 resident authenticator with user verification. It restores provider settings
and deletes its synthetic identity. No personal credentials are changed.
Virtual WebAuthn acceptance does not replace Windows Hello, phone or security-key
hardware acceptance. Website ordinary tests separately check action allowlisting,
signed identity binding and DE/EN forms. Preserve password fallback for browsers
without passkey support; no new browser polyfill or password service is added.
