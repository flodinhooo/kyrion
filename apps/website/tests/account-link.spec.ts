import { test, expect } from "@playwright/test";
import {
  normalizedLinkCode,
  deviceVerificationUrl,
} from "../src/lib/account/device-link";

test("device codes normalize without accepting URLs, control characters or arbitrary verification hosts", () => {
  expect(normalizedLinkCode(" abcd efgh ")).toBe("ABCD-EFGH");
  expect(normalizedLinkCode("1234-5678")).toBe("1234-5678");
  for (const value of [
    null,
    12345678,
    "ABCD",
    "ABCDE-FGHI",
    "ABCD/EFGH",
    "ABCD\nEFGH",
    "https://evil.example",
    "<script>",
  ])
    expect(normalizedLinkCode(value)).toBeNull();
  const target = deviceVerificationUrl(
    new URL("https://auth.kyrion.ch/realms/kyrion"),
    "abcd-efgh",
    "de",
  );
  expect(target.origin).toBe("https://auth.kyrion.ch");
  expect(target.pathname).toBe("/realms/kyrion/device");
  expect(target.searchParams.get("user_code")).toBe("ABCD-EFGH");
  expect(target.searchParams.get("ui_locales")).toBe("de");
});
