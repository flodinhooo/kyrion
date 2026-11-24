import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { createHmac, randomBytes } from "node:crypto";

// Fixed disposable provider only. Never accepts a public issuer or user account.
const provider = "http://localhost:18089";
const website = "http://localhost:3119";
const settings = Object.fromEntries(
  readFileSync("../../.run/stabilization/identity-acceptance.env", "utf8")
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => {
      const i = line.indexOf("=");
      return [line.slice(0, i), line.slice(i + 1)];
    }),
);

function otp(secret: string) {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  const bits = [...secret.toUpperCase().replace(/\s|=/g, "")]
    .map((c) => {
      const n = alphabet.indexOf(c);
      if (n < 0) throw Error("Invalid disposable OTP seed");
      return n.toString(2).padStart(5, "0");
    })
    .join("");
  const key = Buffer.from(bits.match(/.{8}/g)!.map((b) => parseInt(b, 2)));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30000)));
  const digest = createHmac("sha1", key).update(counter).digest();
  return ((digest.readUInt32BE(digest[19] & 15) & 0x7fffffff) % 1000000)
    .toString()
    .padStart(6, "0");
}

test("website security enrollment enforces TOTP and supports passkey login", async ({
  browser,
  request,
}) => {
  test.setTimeout(180000);
  const response = await request.post(
    `${provider}/realms/master/protocol/openid-connect/token`,
    {
      form: {
        client_id: "admin-cli",
        grant_type: "password",
        username: "acceptance-admin",
        password: settings.IDENTITY_ADMIN_PASSWORD,
      },
    },
  );
  expect(response.status()).toBe(200);
  const token: string = (await response.json()).access_token;
  async function admin(path: string, method = "GET", data?: unknown) {
    const result = await request.fetch(
      `${provider}/admin/realms/kyrion${path}`,
      { method, headers: { authorization: `Bearer ${token}` }, data },
    );
    expect(result.status()).toBeLessThan(300);
    return result;
  }
  const realm = await (await admin("")).json();
  const executions: { id: string; providerId: string; requirement: string }[] =
    await (await admin("/authentication/flows/browser/executions")).json();
  const recoveryExecution = executions.find(
    (e) => e.providerId === "auth-recovery-authn-code-form",
  )!;
  const username = `security-${randomBytes(6).toString("hex")}`;
  const password = randomBytes(32).toString("base64url");
  const created = await admin("/users", "POST", {
    username,
    email: username + "@acceptance.invalid",
    emailVerified: true,
    enabled: true,
    firstName: "Security",
    lastName: "Test",
    credentials: [{ type: "password", value: password, temporary: false }],
  });
  const id = created.headers().location.split("/").at(-1)!;
  const context = await browser.newContext({ locale: "en-US" });
  const page = await context.newPage();
  const submit = () =>
    page
      .locator(
        'button[type="submit"]:not([name="cancel-aia"]),input[type="submit"]',
      )
      .click();
  try {
    await admin("/authentication/flows/browser/executions", "PUT", {
      ...recoveryExecution,
      requirement: "ALTERNATIVE",
    });
    await admin("", "PUT", {
      ...realm,
      webAuthnPolicyPasswordlessRpId: "localhost",
      webAuthnPolicyPasswordlessResidentKey: "required",
      webAuthnPolicyPasswordlessUserVerificationRequirement: "required",
      webAuthnPolicyPasswordlessPasskeysEnabled: true,
    });
    await page.goto(website + "/en/account");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.locator("#username").fill(username);
    await page.locator("#password").fill(password);
    await page.locator("#kc-login").click();
    await page
      .getByRole("button", { name: "Set up authenticator app", exact: true })
      .click();
    await page.locator("#mode-manual").click();
    const seed = (await page
      .locator("#kc-totp-secret-key")
      .textContent())!.trim();
    const enrollmentCode = otp(seed);
    await page.locator("#totp").fill(enrollmentCode);
    await page.locator("#userLabel").fill("Isolated test authenticator");
    await submit();
    await expect(
      page.getByRole("heading", { name: "My account", exact: true }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Save recovery codes", exact: true })
      .click();
    const recovery = (
      await page.locator("#kc-recovery-codes-list li").first().innerText()
    )
      .replace(/^\d+:\s*/, "")
      .trim();
    await page.locator("#kcRecoveryCodesConfirmationCheck").check();
    await page.locator("#saveRecoveryAuthnCodesBtn").click();
    await expect(
      page.getByRole("heading", { name: "My account", exact: true }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await context.clearCookies();
    await page.reload();
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.locator("#username").fill(username);
    await page.locator("#password").fill(password);
    await page.locator("#kc-login").click();
    await expect(page.locator("#otp")).toBeVisible();
    const valid = otp(seed);
    await page.locator("#otp").fill(valid === "000000" ? "111111" : "000000");
    await submit();
    await expect(page.locator("#otp")).toBeVisible();
    // Enrollment codes cannot be replayed in the same time window.
    await expect
      .poll(() => otp(seed) !== enrollmentCode, {
        timeout: 35000,
        intervals: [1000],
      })
      .toBe(true);
    await page.locator("#otp").fill(otp(seed));
    await submit();
    await expect(
      page.getByRole("heading", { name: "My account", exact: true }),
    ).toBeVisible();
    const cdp = await context.newCDPSession(page);
    // Recovery is a real alternative to the configured OTP, not a password bypass.
    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await context.clearCookies();
    await page.reload();
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.locator("#username").fill(username);
    await page.locator("#password").fill(password);
    await page.locator("#kc-login").click();
    await page.getByRole("link", { name: /Try another way/i }).click();
    await page
      .getByText("Recovery Authentication Code", { exact: false })
      .first()
      .click();
    await page.locator("#recoveryCodeInput").fill(recovery);
    await submit();
    await expect(
      page.getByRole("heading", { name: "My account", exact: true }),
    ).toBeVisible();
    await cdp.send("WebAuthn.enable");
    let assertions = 0;
    cdp.on("WebAuthn.credentialAsserted", () => {
      assertions++;
    });
    await cdp.send("WebAuthn.addVirtualAuthenticator", {
      options: {
        protocol: "ctap2",
        transport: "internal",
        hasResidentKey: true,
        hasUserVerification: true,
        isUserVerified: true,
        automaticPresenceSimulation: true,
      },
    });
    await page
      .getByRole("button", { name: "Add passkey", exact: true })
      .click();
    page.on("dialog", (dialog) => dialog.accept("Isolated test passkey"));
    await page
      .getByRole("button", { name: /Register|Create passkey/i })
      .click();
    await expect(
      page.getByRole("heading", { name: "My account", exact: true }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await context.clearCookies();
    await page.reload();
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect
      .poll(
        async () =>
          (await page
            .getByRole("heading", { name: "My account", exact: true })
            .isVisible()) ||
          (await page
            .getByRole("button", { name: /Sign in with Passkey/i })
            .isVisible()),
      )
      .toBe(true);
    if (
      await page
        .getByRole("button", { name: /Sign in with Passkey/i })
        .isVisible()
    )
      await page.getByRole("button", { name: /Sign in with Passkey/i }).click();
    await expect(
      page.getByRole("heading", { name: "My account", exact: true }),
    ).toBeVisible();
    await expect.poll(() => assertions).toBeGreaterThan(0);
  } finally {
    await context.close();
    await admin(`/users/${id}`, "DELETE");
    await admin(
      "/authentication/flows/browser/executions",
      "PUT",
      recoveryExecution,
    );
    await admin("", "PUT", realm);
  }
});
