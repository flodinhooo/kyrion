import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";
import * as oidc from "openid-client";
import { randomBytes } from "node:crypto";
import { AccountStore, database, secret } from "../src/lib/account/store";

const env = Object.fromEntries(
  readFileSync(
    path.resolve(__dirname, "../../../infrastructure/identity/.env"),
    "utf8",
  )
    .split(/\r?\n/)
    .filter((line) => line && !line.startsWith("#"))
    .map((line) => {
      const index = line.indexOf("=");
      return [line.slice(0, index), line.slice(index + 1)];
    }),
);
const issuer = "http://localhost:8089/realms/kyrion";
const username = `acceptance-${randomBytes(8).toString("hex")}`;
const password = randomBytes(32).toString("base64url");
let userId = "";
let adminToken = "";

async function login(page: Page) {
  await page.locator("#username").fill(username);
  await page.locator("#password").fill(password);
  await page.locator("#kc-login").click();
}

test.beforeAll(async () => {
  const response = await fetch(
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
  expect(response.ok, "Local development administrator authentication").toBe(
    true,
  );
  const token: { access_token: string } = await response.json();
  adminToken = token.access_token;
  const created = await fetch(
    "http://localhost:8089/admin/realms/kyrion/users",
    {
      method: "POST",
      headers: {
        authorization: `Bearer ${adminToken}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({
        username,
        enabled: true,
        email: `${username}@example.invalid`,
        emailVerified: true,
        firstName: "Isolated",
        lastName: "Acceptance",
        requiredActions: [],
        credentials: [{ type: "password", value: password, temporary: false }],
      }),
    },
  );
  expect(created.status, "Create disposable local provider account").toBe(201);
  userId = created.headers.get("location")?.split("/").pop() ?? "";
});

test.afterAll(async () => {
  if (userId) {
    const deleted = await fetch(
      `http://localhost:8089/admin/realms/kyrion/users/${userId}`,
      { method: "DELETE", headers: { authorization: `Bearer ${adminToken}` } },
    );
    expect(deleted.ok, "Delete disposable provider account").toBe(true);
  }
  await database(
    `postgresql://kyrion_website:${env.WEBSITE_DB_PASSWORD}@localhost:5549/kyrion_website`,
  ).end();
});

test("real Keycloak code flow establishes a server session and logout requires CSRF", async ({
  page,
  context,
}) => {
  let callback = "";
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === "/api/account/callback")
      callback = request.url();
  });
  await page.goto("/en/account");
  await page
    .getByRole("button", { name: "Sign in with Kyrion Account" })
    .click();
  await expect(page.locator("#username")).toBeVisible();
  await login(page);
  await expect(
    page.getByText("You are signed in to the Kyrion website."),
  ).toBeVisible();
  expect(callback).toContain("/api/account/callback?");
  const session = await page.request.get("/api/account/session");
  const data = await session.json();
  expect(data.session.id).toMatch(/^[a-f0-9-]{36}$/);
  expect(
    new Date(data.session.expiresAt).getTime() - Date.now(),
  ).toBeLessThanOrEqual(15 * 60_000);
  const cookie = (await context.cookies()).find(
    (cookie) => cookie.name === "kyrion_website_session",
  );
  expect(cookie?.httpOnly).toBe(true);
  expect(cookie?.sameSite).toBe("Strict");
  const suspended = await fetch(
    `http://localhost:8089/admin/realms/kyrion/users/${userId}`,
    {
      method: "PUT",
      headers: {
        authorization: `Bearer ${adminToken}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({ enabled: false }),
    },
  );
  expect(suspended.ok).toBe(true);
  // Suspension cannot invalidate a previously issued local website session
  // without a provider callback. Its short expiry is the documented bound.
  expect(
    (await (await page.request.get("/api/account/session")).json()).session.id,
  ).toBe(data.session.id);
  const csrfFailure = await page.request.post("/api/account/logout", {
    headers: { origin: "http://localhost:3109" },
  });
  expect(csrfFailure.status()).toBe(403);
  const replay = await page.request.get(callback);
  expect(replay.url()).toContain("ACCOUNT_AUTHENTICATION_FAILED");
  await page.getByRole("button", { name: "Sign out of this website" }).click();
  await expect(
    page.getByRole("button", { name: "Sign in with Kyrion Account" }),
  ).toBeVisible();
  expect(
    (await (await page.request.get("/api/account/session")).json()).session,
  ).toBeNull();
  await page
    .getByRole("button", { name: "Sign in with Kyrion Account" })
    .click();
  await login(page);
  await expect(
    page.getByText("Account is disabled, contact your administrator.", {
      exact: false,
    }),
  ).toBeVisible();
  expect(
    (
      await (
        await page.request.get("http://localhost:3109/api/account/session")
      ).json()
    ).session,
  ).toBeNull();
  const restored = await fetch(
    `http://localhost:8089/admin/realms/kyrion/users/${userId}`,
    {
      method: "PUT",
      headers: {
        authorization: `Bearer ${adminToken}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({ enabled: true }),
    },
  );
  expect(restored.ok).toBe(true);
});

test("real Keycloak public device grant requires explicit browser confirmation", async ({
  page,
}) => {
  const config = await oidc.discovery(
    new URL(issuer),
    "kyrion-local",
    { id_token_signed_response_alg: "RS256" },
    oidc.None(),
    { execute: [oidc.allowInsecureRequests, oidc.enableNonRepudiationChecks] },
  );
  const device = await oidc.initiateDeviceAuthorization(config, {
    scope: "openid",
  });
  await page.goto(device.verification_uri);
  await page.locator("input[type=text]").fill(device.user_code);
  await page.locator("input[type=submit], button[type=submit]").click();
  await login(page);
  await page.getByRole("button", { name: /Yes|Confirm|Allow/i }).click();
  const result = await oidc.pollDeviceAuthorizationGrant(
    config,
    device,
    undefined,
    { signal: AbortSignal.timeout(20_000) },
  );
  expect(result.claims()?.iss).toBe(issuer);
  expect(result.claims()?.sub).toBe(userId);
});

test("real PostgreSQL consumes flows atomically and keys accounts only by issuer and subject", async () => {
  const pool = database(
    `postgresql://kyrion_website:${env.WEBSITE_DB_PASSWORD}@localhost:5549/kyrion_website`,
  );
  const store = new AccountStore(pool);
  const id = secret();
  const flow = {
    state: secret(),
    nonce: secret(),
    verifier: secret(),
    locale: "en",
  } as const;
  await store.begin(id, flow);
  const consumed = await Promise.all(
    Array.from({ length: 8 }, () => store.consume(id)),
  );
  expect(consumed.filter(Boolean)).toHaveLength(1);
  expect(await store.consume(secret())).toBeNull();
  const expiry = Math.floor(Date.now() / 1000) + 300;
  const first = await store.issue(issuer, `${userId}-distinct-a`, expiry);
  const second = await store.issue(issuer, `${userId}-distinct-b`, expiry);
  const same = await store.issue(issuer, `${userId}-distinct-a`, expiry);
  expect((await store.session(first.id))?.id).not.toBe(
    (await store.session(second.id))?.id,
  );
  expect((await store.session(first.id))?.id).toBe(
    (await store.session(same.id))?.id,
  );
  await Promise.all(
    [first, second, same].map((session) => store.revoke(session.id)),
  );
  await pool.query(
    "DELETE FROM website_account WHERE issuer=$1 AND subject=ANY($2)",
    [issuer, [`${userId}-distinct-a`, `${userId}-distinct-b`]],
  );
});
