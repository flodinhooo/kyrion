// Explicit isolated acceptance helper. Never run against a production issuer.
import { chromium } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { randomBytes } from "node:crypto";

const requestPath = process.argv[process.argv.indexOf("--request") + 1];
if (!process.argv.includes("--request") || !requestPath)
  throw new Error("--request absolutePath is required");
const env = Object.fromEntries(
  (
    await readFile(
      new URL("../../../infrastructure/identity/.env", import.meta.url),
      "utf8",
    )
  )
    .split(/\r?\n/)
    .filter((line) => line && !line.startsWith("#"))
    .map((line) => {
      const index = line.indexOf("=");
      return [line.slice(0, index), line.slice(index + 1)];
    }),
);
const username = `core-acceptance-${randomBytes(8).toString("hex")}`;
const password = randomBytes(32).toString("base64url");
const tokenResponse = await fetch(
  "http://localhost:8089/realms/master/protocol/openid-connect/token",
  {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "password",
      client_id: "admin-cli",
      username: env.IDENTITY_ADMIN_USERNAME,
      password: env.IDENTITY_ADMIN_PASSWORD,
    }),
  },
);
if (!tokenResponse.ok)
  throw new Error("Development administrator authentication failed");
const admin = await tokenResponse.json();
const headers = {
  authorization: `Bearer ${admin.access_token}`,
  "content-type": "application/json",
};
const created = await fetch("http://localhost:8089/admin/realms/kyrion/users", {
  method: "POST",
  headers,
  body: JSON.stringify({
    username,
    enabled: true,
    email: `${username}@example.invalid`,
    emailVerified: true,
    firstName: "Core",
    lastName: "Acceptance",
    requiredActions: [],
    credentials: [{ type: "password", value: password, temporary: false }],
  }),
});
if (created.status !== 201)
  throw new Error("Disposable account creation failed");
const userLocation = created.headers.get("location");
const browser = await chromium.launch();
try {
  let request;
  const deadline = Date.now() + 120_000;
  while (!request && Date.now() < deadline) {
    try {
      request = JSON.parse(await readFile(requestPath, "utf8"));
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
  }
  if (
    !request ||
    typeof request.userCode !== "string" ||
    typeof request.verificationUri !== "string"
  )
    throw new Error("Missing Core device acceptance request");
  const verification = new URL(request.verificationUri);
  if (verification.origin !== "http://localhost:8089")
    throw new Error("Only isolated loopback provider supported");
  const page = await browser.newPage();
  await page.goto(verification.href);
  await page.locator("input[type=text]").fill(request.userCode);
  await page.locator("input[type=submit], button[type=submit]").click();
  await page.locator("#username").fill(username);
  await page.locator("#password").fill(password);
  await page.locator("#kc-login").click();
  await page.getByRole("button", { name: /Yes|Confirm|Allow/i }).click();
  console.log(
    "Disposable user explicitly authorized Core device request at local Keycloak.",
  );
  // Give the Core poller time to validate before removing this disposable identity.
  const completionDeadline = Date.now() + 90_000;
  while (Date.now() < completionDeadline) {
    try {
      await readFile(requestPath);
    } catch (error) {
      if (error.code === "ENOENT") break;
      throw error;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
} finally {
  await browser.close();
  if (userLocation) await fetch(userLocation, { method: "DELETE", headers });
}
