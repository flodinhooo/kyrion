import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { randomUUID } from "node:crypto";
import { Pool } from "pg";
import {
  InstallationStore,
  installationReport,
} from "../src/lib/account/installations";

test("directory rows isolate accounts, hash receipts and reject cross-row maintenance", async () => {
  const settings = Object.fromEntries(
    readFileSync("../../.run/stabilization/identity-acceptance.env", "utf8")
      .split(/\r?\n/)
      .filter(Boolean)
      .map((line) => {
        const i = line.indexOf("=");
        return [line.slice(0, i), line.slice(i + 1)];
      }),
  );
  const pool = new Pool({
    host: "127.0.0.1",
    port: 15549,
    database: "kyrion_website",
    user: "kyrion_website",
    password: settings.WEBSITE_DB_PASSWORD,
  });
  const store = new InstallationStore(pool);
  const issuer = "https://directory.acceptance.invalid/realms/test";
  const body = {
    installationId: randomUUID(),
    localUserId: randomUUID(),
    name: "Directory fixture",
    spaceType: "HOME" as const,
    localUsername: "local-fixture",
    linkedAt: new Date().toISOString(),
  };
  try {
    expect(installationReport({ ...body, name: "bad\nname" })).toBeNull();
    expect(
      installationReport({ ...body, installationId: "not-a-uuid" }),
    ).toBeNull();
    const a = await store.report(issuer, "account-a", body),
      b = await store.report(issuer, "account-b", body);
    const accounts = await pool.query<{
      id: string;
      subject: string;
    }>("SELECT id,subject FROM website_account WHERE issuer=$1", [issuer]);
    const aid = accounts.rows.find((x) => x.subject === "account-a")!.id,
      bid = accounts.rows.find((x) => x.subject === "account-b")!.id;
    expect((await store.list(aid)).map((x) => x.id)).toEqual([a.id]);
    expect((await store.list(bid)).map((x) => x.id)).toEqual([b.id]);
    expect(JSON.stringify(await store.list(aid))).not.toContain(a.credential);
    const hash = (
      await pool.query(
        "SELECT credential_hash FROM website_installation_link WHERE id=$1",
        [a.id],
      )
    ).rows[0].credential_hash;
    expect(hash).not.toBe(a.credential);
    expect(await store.remove(a.id, b.credential)).toBe(false);
    expect(
      await store.update(a.id, a.credential, {
        ...body,
        localUserId: randomUUID(),
      }),
    ).toBe(false);
    expect(
      await store.update(a.id, a.credential, {
        ...body,
        name: "Renamed fixture",
      }),
    ).toBe(true);
    const rotated = await store.report(issuer, "account-a", body);
    expect(rotated.id).toBe(a.id);
    expect(await store.remove(a.id, a.credential)).toBe(false);
    expect(await store.remove(a.id, rotated.credential)).toBe(true);
    expect(await store.list(aid)).toEqual([]);
    expect((await store.list(bid)).length).toBe(1);
  } finally {
    await pool.query("DELETE FROM website_account WHERE issuer=$1", [issuer]);
    await pool.end();
  }
});
