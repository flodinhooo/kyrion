import { expect, test } from "@playwright/test";
import { createServer } from "node:http";
import { generateKeyPairSync, sign } from "node:crypto";
import { accountConfig, type AccountConfig } from "../src/lib/account/config";
import { authenticate, authorizationUrl } from "../src/lib/account/oidc";
import { hash, secret } from "../src/lib/account/store";

test("optional accounts do not require provider configuration", () => {
  expect(accountConfig({})).toBeNull();
  expect(() =>
    accountConfig({ KYRION_WEBSITE_ACCOUNT_ENABLED: "yes" }),
  ).toThrow("must be true or false");
  expect(() =>
    accountConfig({ KYRION_WEBSITE_ACCOUNT_ENABLED: "true" }),
  ).toThrow("Missing account configuration");
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

for (const defect of [
  "none",
  "signature",
  "issuer",
  "audience",
  "nonce",
  "expired",
  "state",
  "algorithm",
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
      const callback = new URL(
        `${config.callback}?code=single-use-code&state=${defect === "state" ? "foreign-state" : flow.state}`,
      );
      if (defect === "none") {
        expect(await authenticate(config, callback, flow)).toMatchObject({
          issuer,
          subject: "stable-subject",
        });
        expect(exchangedVerifier).toBe(flow.verifier);
      } else {
        await expect(authenticate(config, callback, flow)).rejects.toThrow();
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
    page.getByRole("heading", { name: "Kyrion Account" }),
  ).toBeVisible();
  await expect(
    page.getByText("Central sign-in is not enabled", { exact: false }),
  ).toBeVisible();
  await page.goto("/account");
  await expect(
    page.getByRole("heading", { name: "Kyrion-Account" }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "Die zentrale Anmeldung ist auf dieser Website nicht aktiviert",
      { exact: false },
    ),
  ).toBeVisible();
});
