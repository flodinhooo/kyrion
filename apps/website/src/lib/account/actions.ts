export const accountActions = {
  profile: "UPDATE_PROFILE",
  password: "UPDATE_PASSWORD",
  otp: "CONFIGURE_TOTP",
  passkey: "webauthn-register-passwordless",
  remove: "delete_credential",
  recovery: "CONFIGURE_RECOVERY_AUTHN_CODES",
} as const;

export type AccountAction = keyof typeof accountActions;

export function isAccountAction(value: unknown): value is AccountAction {
  return typeof value === "string" && Object.hasOwn(accountActions, value);
}
