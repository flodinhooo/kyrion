import { test, expect } from "@playwright/test";
import { Pool } from "pg";
import { readFileSync } from "node:fs";
import { protectRefresh, readRefresh } from "../src/lib/account/credentials";
import {
  AccountStore,
  hash,
  rememberedLifetime,
} from "../src/lib/account/store";
import { IdentityRevoked } from "../src/lib/account/oidc";
import type { AccountConfig } from "../src/lib/account/config";

test("renewal credentials are authenticated, randomized and bound to the session and server key", () => {
  const encrypted = protectRefresh(
    "private-renewal",
    "server-key",
    "session-a",
  );
  expect(encrypted).not.toContain("private-renewal");
  expect(readRefresh(encrypted, "server-key", "session-a")).toBe(
    "private-renewal",
  );
  expect(protectRefresh("private-renewal", "server-key", "session-a")).not.toBe(
    encrypted,
  );
  expect(() => readRefresh(encrypted, "server-key", "session-b")).toThrow();
  expect(() => readRefresh(encrypted, "rotated-key", "session-a")).toThrow();
  const parts = encrypted.split(".");
  const bytes = Buffer.from(parts[3], "base64url");
  bytes[0] ^= 1;
  parts[3] = bytes.toString("base64url");
  expect(() =>
    readRefresh(parts.join("."), "server-key", "session-a"),
  ).toThrow();
});

test("real PostgreSQL serializes renewal and logout, preserves transient retries and rejects revoked identities", async () => {
  test.skip(
    !process.env.KYRION_ACCOUNT_TEST_DATABASE,
    "Opt-in disposable database only",
  );
  const url = new URL(process.env.KYRION_ACCOUNT_TEST_DATABASE!);
  expect(url.hostname).toBe("127.0.0.1");
  expect(url.port).toBe("15559");
  expect(url.pathname).toBe("/website_acceptance");
  const owner = new Pool({ connectionString: url.href });
  const config: AccountConfig = {
    issuer: new URL("https://identity.example.test/realms/test"),
    origin: "https://website.example.test",
    callback: "https://website.example.test/api/account/callback",
    clientId: "website",
    clientSecret: "isolated-encryption-key",
    databaseUrl: url.href,
    developmentHttp: true,
  };
  let runtime: Pool | undefined;
  try {
    await owner.query(
      "CREATE ROLE kyrion_website_app LOGIN PASSWORD 'disposable-fixture-only'",
    );
    await owner.query(readFileSync("account-schema.sql", "utf8"));
    await owner.query(readFileSync("account-runtime-grants.sql", "utf8"));
    await owner.query(
      readFileSync("migrations/004-account-actions.sql", "utf8"),
    );
    await owner.query(
      readFileSync("migrations/004-account-actions.sql", "utf8"),
    );
    await owner.query(
      readFileSync("migrations/002-remembered-sessions.sql", "utf8"),
    );
    await owner.query(
      readFileSync("migrations/002-remembered-sessions.sql", "utf8"),
    );
    url.username = "kyrion_website_app";
    url.password = "disposable-fixture-only";
    runtime = new Pool({ connectionString: url.href, max: 5 });
    let renewals = 0;
    const identity = {
      issuer: config.issuer.href,
      subject: "verified-user",
      expiresAt: Math.floor(Date.now() / 1000) + 300,
      refreshToken: "rotated-renewal",
    };
    const store = new AccountStore(
      runtime,
      config,
      async (_config, credential) => {
        expect(credential).toBe("initial-renewal");
        renewals++;
        return identity;
      },
    );
    const session = await store.issue(
      identity.issuer,
      identity.subject,
      identity.expiresAt,
      "initial-renewal",
    );
    expect(await store.actionSubject(session.id)).toBe(identity.subject);
    expect(await store.actionSubject("unknown")).toBeNull();
    const flowId = "one-use-account-action";
    const flow = {
      state: "state",
      nonce: "nonce",
      verifier: "verifier",
      locale: "en",
      destination: "password",
      expectedSubject: identity.subject,
    } as const;
    await store.begin(flowId, flow);
    expect(await store.consume(flowId)).toEqual(flow);
    expect(await store.consume(flowId)).toBeNull();
    expect(Date.parse(session.expiresAt) - Date.now()).toBeGreaterThan(
      rememberedLifetime - 10000,
    );
    const expireProof = async (token: string) =>
      owner.query(
        "UPDATE website_session SET verified_until=now()-interval '1 minute' WHERE token_hash=$1",
        [hash(token)],
      );
    await expireProof(session.id);
    const values = await Promise.all([
      store.session(session.id),
      store.session(session.id),
    ]);
    expect(values[0]?.id).toBe(values[1]?.id);
    expect(renewals).toBe(1);
    expect(JSON.stringify(values)).not.toContain("renewal");
    expect(JSON.stringify(values)).not.toContain("verified-user");
    const stored = await owner.query(
      "SELECT refresh_credential,expires_at FROM website_session WHERE token_hash=$1",
      [hash(session.id)],
    );
    expect(stored.rows[0].refresh_credential).not.toContain("rotated-renewal");
    expect(new Date(stored.rows[0].expires_at).toISOString()).toBe(
      session.expiresAt,
    );
    await expect(
      runtime.query("UPDATE website_session SET expires_at=now()"),
    ).rejects.toThrow();
    await expireProof(session.id);
    const outage = new AccountStore(runtime, config, async () => {
      throw new Error("Provider temporarily unavailable");
    });
    await expect(outage.session(session.id)).rejects.toThrow("temporarily");
    expect((await outage.forLogout(session.id))?.id).toBe(values[0]?.id);
    const changed = new AccountStore(runtime, config, async () => ({
      ...identity,
      subject: "another-user",
    }));
    expect(await changed.session(session.id)).toBeNull();
    expect(await store.session(session.id)).toBeNull();
    const revoked = await store.issue(
      identity.issuer,
      identity.subject,
      identity.expiresAt,
      "initial-renewal",
    );
    await expireProof(revoked.id);
    const disabled = new AccountStore(runtime, config, async () => {
      throw new IdentityRevoked("Provider revoked access");
    });
    expect(await disabled.session(revoked.id)).toBeNull();
    const race = await store.issue(
      identity.issuer,
      identity.subject,
      identity.expiresAt,
      "initial-renewal",
    );
    await expireProof(race.id);
    let release!: () => void;
    let entered!: () => void;
    const arrived = new Promise<void>((resolve) => {
      entered = resolve;
    });
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const delayed = new AccountStore(runtime, config, async () => {
      entered();
      await gate;
      return identity;
    });
    const pending = delayed.session(race.id);
    await arrived;
    const logout = delayed.revoke(race.id);
    release();
    await pending;
    await logout;
    expect(await store.session(race.id)).toBeNull();
    const expired = await store.issue(
      identity.issuer,
      identity.subject,
      identity.expiresAt,
      "initial-renewal",
    );
    await owner.query(
      "UPDATE website_session SET expires_at=now()-interval '1 minute' WHERE token_hash=$1",
      [hash(expired.id)],
    );
    expect(await store.session(expired.id)).toBeNull();
  } finally {
    await runtime?.end();
    await owner.end();
  }
});
