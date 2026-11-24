import { test, expect } from "@playwright/test";
import {
  credentialId,
  parseInventory,
} from "../src/lib/account/credential-inventory";

const passkey = "11111111-1111-4111-8111-111111111111";
const otp = "22222222-2222-4222-8222-222222222222";
const group = (
  type: string,
  id: string,
  extra: Record<string, unknown> = {},
) => ({
  type,
  removeable: true,
  userCredentialMetadatas: [
    {
      credential: {
        id,
        type,
        userLabel: "My device",
        createdDate: 1700000000000,
        ...extra,
      },
    },
  ],
});

test("inventory returns only safe own-account metadata and protects passwordless primary credentials", () => {
  const raw = [
    group("password", "password-id"),
    group("webauthn-passwordless", passkey, {
      secretData: "never-return",
      credentialData: "never-return",
      value: "never-return",
    }),
    group("otp", otp),
  ];
  const result = parseInventory(raw);
  expect(result.hasPassword).toBe(true);
  expect(result.methods.map((m) => m.kind)).toEqual(["passkey", "otp"]);
  expect(result.methods.every((m) => m.removable)).toBe(true);
  expect(JSON.stringify(result)).not.toContain("never-return");
  const passwordless = parseInventory(raw.slice(1));
  expect(
    passwordless.methods.find((m) => m.kind === "passkey")?.removable,
  ).toBe(false);
  expect(passwordless.methods.find((m) => m.kind === "otp")?.removable).toBe(
    true,
  );
  const twoFactorOnly = parseInventory([
    group("webauthn", passkey),
    group("otp", otp),
  ]);
  expect(twoFactorOnly.methods.every((m) => !m.removable)).toBe(true);
});

test("invalid or ambiguous provider metadata fails closed rather than presenting an empty inventory", () => {
  for (const value of [
    null,
    {},
    [{}],
    [{ type: "otp", userCredentialMetadatas: null }],
    [group("otp", "../other")],
    [group("otp", otp), group("otp", otp)],
    [group("otp", otp, { userLabel: { bad: true } })],
    [group("otp", otp, { type: "password" })],
  ])
    expect(() => parseInventory(value)).toThrow();
  expect(parseInventory([])).toEqual({ methods: [], hasPassword: false });
  expect(credentialId(passkey)).toBe(true);
  for (const value of [
    null,
    "",
    "__proto__",
    "https://example.test",
    "id:other",
    "../password",
  ])
    expect(credentialId(value)).toBe(false);
});
