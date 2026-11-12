import { expect, test } from "@playwright/test";
import { createServer } from "node:http";
import { generateKeyPairSync, sign } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";
import pilotRealm from "../../../infrastructure/identity/pilot-realm.json";
import { accountConfig, type AccountConfig } from "../src/lib/account/config";
import {
  authenticate,
  authorizationUrl,
  renewIdentity,
} from "../src/lib/account/oidc";
import { hash, secret } from "../src/lib/account/store";
import { dictionaries } from "../src/lib/site";

test("privacy pages explain cookies and retention and are linked from the localized contact form", async ({
  page,
}) => {
  for (const locale of ["en", "de"] as const) {
    const sections = dictionaries[locale].legal.privacy.sections;
    expect(sections.some((section) => section.body.includes("HttpOnly"))).toBe(
      true,
    );
    expect(
      sections.some(
        (section) =>
          section.title ===
          (locale === "en"
            ? "Optional website account"
            : "Optionaler Website-Account"),
      ),
    ).toBe(true);
    const prefix = locale === "en" ? "/en" : "";
    await page.goto(`${prefix}/privacy`);
    await expect(page.locator("main")).toContainText("HttpOnly");
    await expect(
      page.getByRole("heading", {
        name:
          locale === "en"
            ? "Session validity and stored records"
            : "Sitzungsgültigkeit und gespeicherte Datensätze",
        exact: true,
      }),
    ).toBeVisible();
    await page.goto(`${prefix}/contact`);
    const notice = page.getByRole("link", {
      name: dictionaries[locale].contact.privacyLink,
      exact: true,
    });
    await expect(notice).toHaveAttribute("href", `${prefix}/privacy`);
    await notice.click();
    await expect(page).toHaveURL(`http://127.0.0.1:3101${prefix}/privacy`);
  }
});

test("optional accounts do not require provider configuration", () => {
  expect(accountConfig({})).toBeNull();
  expect(() =>
    accountConfig({ KYRION_WEBSITE_ACCOUNT_ENABLED: "yes" }),
  ).toThrow("must be true or false");
  expect(() =>
    accountConfig({ KYRION_WEBSITE_ACCOUNT_ENABLED: "true" }),
  ).toThrow("Missing account configuration");
});

test("production template and provider share the canonical www callback", () => {
  const template = Object.fromEntries(
    readFileSync(
      path.resolve(__dirname, "../account.production.env.example"),
      "utf8",
    )
      .split(/\r?\n/)
      .filter((line) => line && !line.startsWith("#"))
      .map((line) => {
        const index = line.indexOf("=");
        return [line.slice(0, index), line.slice(index + 1)];
      }),
  );
  const config = accountConfig({
    ...template,
    KYRION_WEBSITE_ACCOUNT_ENABLED: "true",
    NODE_ENV: "production",
  });
  expect(config?.callback).toBe("https://www.kyrion.ch/api/account/callback");
  const client = pilotRealm.clients.find(
    (value) => value.clientId === "kyrion-website",
  );
  expect(client?.redirectUris).toEqual([config?.callback]);
  expect(client?.attributes["pkce.code.challenge.method"]).toBe("S256");
});

test("account origins reject paths, credentials, queries, LAN HTTP and production HTTP", () => {
  const base = {
    KYRION_WEBSITE_ACCOUNT_ENABLED: "true",
    KYRION_WEBSITE_OIDC_ISSUER: "https://auth.example.test/realms/kyrion",
    KYRION_WEBSITE_ORIGIN: "https://kyrion.example.test",
    KYRION_WEBSITE_OIDC_CLIENT_ID: "website",
    KYRION_WEBSITE_OIDC_CLIENT_SECRET: "private-test-fixture",
    KYRION_WEBSITE_ACCOUNT_DATABASE_URL: "postgresql://test",
  };
  for (const origin of [
    "https://kyrion.example.test/evil",
    "https://a:b@kyrion.example.test",
    "https://kyrion.example.test?redirect=evil",
    "http://192.168.1.2",
    "http://localhost:3001",
  ]) {
    expect(() =>
      accountConfig({
        ...base,
        KYRION_WEBSITE_ORIGIN: origin,
        NODE_ENV: "production",
        KYRION_WEBSITE_ACCOUNT_DEV_HTTP: "true",
      }),
    ).toThrow();
  }
});

test("opaque cookie material has sufficient entropy and only its digest identifies persisted rows", () => {
  const values = new Set(Array.from({ length: 100 }, secret));
  expect(values.size).toBe(100);
  for (const value of values) {
    expect(value).toHaveLength(43);
    expect(hash(value)).toHaveLength(64);
    expect(hash(value)).not.toBe(value);
  }
});

test("central account database requires verified TLS and redacts malformed credentials", () => {
  const base = {
    KYRION_WEBSITE_ACCOUNT_ENABLED: "true",
    KYRION_WEBSITE_OIDC_ISSUER: "https://auth.example.test/realms/kyrion",
    KYRION_WEBSITE_ORIGIN: "https://kyrion.example.test",
    KYRION_WEBSITE_OIDC_CLIENT_ID: "website",
    KYRION_WEBSITE_OIDC_CLIENT_SECRET: "private-test-fixture",
    NODE_ENV: "production",
  };
  const configure = (database: string, development = false) =>
    accountConfig({
      ...base,
      NODE_ENV: development ? "development" : "production",
      KYRION_WEBSITE_ACCOUNT_DEV_HTTP: development ? "true" : "false",
      KYRION_WEBSITE_ACCOUNT_DATABASE_URL: database,
    });
  expect(
    configure(
      "postgresql://website:fixture@db.example.test/sessions?sslmode=verify-full",
    ),
  ).not.toBeNull();
  for (const mode of ["", "disable", "prefer", "require", "no-verify"]) {
    expect(() =>
      configure(
        `postgresql://website:fixture@db.example.test/sessions?sslmode=${mode}`,
      ),
    ).toThrow("sslmode=verify-full");
  }
  expect(
    configure("postgresql://website:fixture@127.0.0.1:5432/sessions", true),
  ).not.toBeNull();
  expect(() =>
    configure("postgresql://website:fixture@db.example.test/sessions", true),
  ).toThrow("sslmode=verify-full");
  expect(() =>
    configure("postgresql://website:fixture@localhost/sessions"),
  ).toThrow("sslmode=verify-full");
  for (const database of [
    "postgresql://website:do-not-disclose@[invalid/sessions",
    "https://website:do-not-disclose@db.example.test/sessions",
    "postgresql://website:do-not-disclose@db.example.test",
  ]) {
    expect(() => configure(database)).toThrow(
      "Invalid website account PostgreSQL configuration",
    );
    try {
      configure(database);
    } catch (error) {
      expect(String(error)).not.toContain("do-not-disclose");
    }
  }
});

for (const defect of [
  "none",
  "signature",
  "issuer",
  "audience",
  "nonce",
  "expired",
  "state",
  "algorithm",
  "unverified-email",
] as const) {
  test(`OIDC validates real RSA signatures and claims: ${defect}`, async () => {
    const key = generateKeyPairSync("rsa", { modulusLength: 2048 });
    const other = generateKeyPairSync("rsa", { modulusLength: 2048 });
    const flow = {
      state: secret(),
      nonce: secret(),
      verifier: secret(),
      locale: "en",
    } as const;
    let issuer = "";
    let exchangedVerifier = "";
    const server = createServer(async (request, response) => {
      response.setHeader("Content-Type", "application/json");
      if (request.url === "/.well-known/openid-configuration") {
        response.end(
          JSON.stringify({
            issuer,
            authorization_endpoint: `${issuer}/authorize`,
            token_endpoint: `${issuer}/token`,
            jwks_uri: `${issuer}/jwks`,
            response_types_supported: ["code"],
            subject_types_supported: ["public"],
            id_token_signing_alg_values_supported: ["RS256"],
          }),
        );
      } else if (request.url === "/jwks") {
        response.end(
          JSON.stringify({
            keys: [
              {
                ...key.publicKey.export({ format: "jwk" }),
                kid: "fixture",
                alg: "RS256",
                use: "sig",
              },
            ],
          }),
        );
      } else if (request.url === "/token") {
        let body = "";
        for await (const chunk of request) body += chunk;
        exchangedVerifier =
          new URLSearchParams(body).get("code_verifier") ?? "";
        const now = Math.floor(Date.now() / 1000);
        const encode = (value: unknown) =>
          Buffer.from(JSON.stringify(value)).toString("base64url");
        const header = encode({
          alg: defect === "algorithm" ? "RS384" : "RS256",
          kid: "fixture",
        });
        const claims = encode({
          iss: defect === "issuer" ? "https://foreign.example.test" : issuer,
          sub: "stable-subject",
          aud: defect === "audience" ? "foreign-client" : "website",
          iat: now,
          auth_time: now,
          email_verified: defect !== "unverified-email",
          exp: defect === "expired" ? now - 100 : now + 300,
          nonce: defect === "nonce" ? "foreign-nonce" : flow.nonce,
        });
        const payload = `${header}.${claims}`;
        const signature = sign(
          defect === "algorithm" ? "RSA-SHA384" : "RSA-SHA256",
          Buffer.from(payload),
          defect === "signature" ? other.privateKey : key.privateKey,
        ).toString("base64url");
        response.end(
          JSON.stringify({
            access_token: "not-an-api-credential",
            refresh_token: "fixture-renewal-credential",
            token_type: "Bearer",
            expires_in: 300,
            id_token: `${payload}.${signature}`,
          }),
        );
      } else {
        response.statusCode = 404;
        response.end("{}");
      }
    });
    await new Promise<void>((resolve) =>
      server.listen(0, "127.0.0.1", resolve),
    );
    const address = server.address();
    if (!address || typeof address === "string")
      throw new Error("No loopback address");
    issuer = `http://127.0.0.1:${address.port}`;
    const config: AccountConfig = {
      issuer: new URL(issuer),
      origin: "http://localhost:3001",
      callback: "http://localhost:3001/api/account/callback",
      clientId: "website",
      clientSecret: "private-fixture",
      databaseUrl: "unused",
      developmentHttp: true,
    };
    try {
      const authorize = await authorizationUrl(config, flow);
      expect(authorize.searchParams.get("code_challenge_method")).toBe("S256");
      expect(authorize.searchParams.get("code_challenge")).not.toBe(
        flow.verifier,
      );
      expect(authorize.searchParams.get("redirect_uri")).toBe(config.callback);
      expect(authorize.searchParams.has("max_age")).toBe(false);
      const registration = await authorizationUrl(config, flow, true);
      expect(registration.searchParams.get("prompt")).toBe("create");
      expect(registration.searchParams.get("state")).toBe(flow.state);
      expect(registration.searchParams.get("code_challenge")).toBe(
        authorize.searchParams.get("code_challenge"),
      );
      const callback = new URL(
        `${config.callback}?code=single-use-code&state=${defect === "state" ? "foreign-state" : flow.state}`,
      );
      if (defect === "none") {
        expect(await authenticate(config, callback, flow)).toMatchObject({
          issuer,
          subject: "stable-subject",
        });
        expect(exchangedVerifier).toBe(flow.verifier);
        expect(
          await renewIdentity(config, "fixture-renewal-credential"),
        ).toMatchObject({
          issuer,
          subject: "stable-subject",
          refreshToken: "fixture-renewal-credential",
        });
      } else {
        await expect(authenticate(config, callback, flow)).rejects.toThrow();
        if (defect !== "state" && defect !== "nonce")
          await expect(
            renewIdentity(config, "fixture-renewal-credential"),
          ).rejects.toThrow();
      }
    } finally {
      await new Promise<void>((resolve, reject) =>
        server.close((error) => (error ? reject(error) : resolve())),
      );
    }
  });
}

test("account pages explain independence in both languages", async ({
  page,
}) => {
  await page.goto("/en/account");
  await expect(
    page.getByRole("heading", { name: dictionaries.en.account.title }),
  ).toBeVisible();
  await expect(
    page.getByText("Central sign-in is not enabled", { exact: false }),
  ).toBeVisible();
  await page.goto("/account");
  await expect(
    page.getByRole("heading", { name: dictionaries.de.account.title }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "Die zentrale Anmeldung ist auf dieser Website nicht aktiviert",
      { exact: false },
    ),
  ).toBeVisible();
});

test("customer account menu, browser registration and local help work in both languages", async ({
  page,
}) => {
  for (const locale of ["de", "en"] as const) {
    const copy = dictionaries[locale].account;
    const prefix = locale === "en" ? "/en" : "";
    for (const signedIn of [false, true]) {
      await page.route("**/api/account/session", (route) =>
        route.fulfill({
          json: {
            enabled: true,
            session: signedIn
              ? {
                  id: "browser-fixture",
                  csrf: "fixture-csrf",
                  expiresAt: new Date(Date.now() + 86400000).toISOString(),
                }
              : null,
          },
        }),
      );
      await page.goto(`${prefix}/account`);
      if (signedIn) {
        await expect(
          page.getByRole("heading", { name: copy.menu, exact: true }),
        ).toBeVisible();
        await expect(
          page.getByText(copy.connectIntro, { exact: true }),
        ).not.toBeVisible();
        await page.locator("main summary").click();
        await expect(page.locator("main ol li")).toHaveCount(3);
        await expect(
          page.getByText(copy.connectIntro, { exact: true }),
        ).toBeVisible();
        await expect(page.locator("main")).not.toContainText("15");
        await page.locator("header summary").click();
        await page.setViewportSize({ width: 320, height: 900 });
        const menuBounds = await page
          .getByRole("navigation", { name: copy.menu })
          .boundingBox();
        expect(menuBounds).not.toBeNull();
        expect(menuBounds!.x).toBeGreaterThanOrEqual(0);
        expect(menuBounds!.x + menuBounds!.width).toBeLessThanOrEqual(320);
        await page.setViewportSize({ width: 1280, height: 720 });
        await expect(
          page
            .getByRole("navigation", { name: copy.menu })
            .getByRole("link", { name: copy.overview }),
        ).toHaveAttribute("href", `${prefix}/account`);
        await page.keyboard.press("Escape");
        await expect(
          page.getByRole("navigation", { name: copy.menu }),
        ).not.toBeVisible();
        await page.locator("header summary").click();
        await page.route("**/api/account/logout", (route) => {
          expect(route.request().headers()["x-kyrion-csrf"]).toBe(
            "fixture-csrf",
          );
          return route.fulfill({ json: { ok: true } });
        });
        await page
          .getByRole("navigation", { name: copy.menu })
          .getByRole("button", { name: copy.logout })
          .click();
        await expect(
          page.getByRole("heading", { name: copy.title, exact: true }),
        ).toBeVisible();
        await expect(page.locator("header summary")).toHaveCount(0);
        await page.unroute("**/api/account/logout");
      } else {
        await expect(
          page.getByRole("button", { name: copy.register, exact: true }),
        ).toBeVisible();
        await expect(
          page.locator('form[action="/api/account/register"]'),
        ).toHaveAttribute("method", "post");
        await expect(
          page.locator(
            'form[action="/api/account/register"] input[name="locale"]',
          ),
        ).toHaveValue(locale);
        await expect(page.locator("main")).not.toContainText("Einladung");
        await expect(
          page
            .locator("header")
            .getByRole("link", { name: copy.login, exact: true }),
        ).toBeVisible();
      }
      await page.unroute("**/api/account/session");
    }
  }
});
