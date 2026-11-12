import { Pool } from "pg";
import { hash, secret } from "./store";
import type { AccountConfig } from "./config";
import { discover } from "./oidc";
import * as oidc from "openid-client";

export type InstallationReport = {
  installationId: string;
  localUserId: string;
  name: string;
  spaceType: "HOME" | "BUSINESS";
  localUsername: string;
  linkedAt: string;
};
export type LinkedInstallation = {
  id: string;
  name: string;
  spaceType: "HOME" | "BUSINESS";
  localUsername: string;
  linkedAt: string;
  confirmedAt: string;
};
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function validDirectoryId(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value);
}

export function installationReport(value: unknown): InstallationReport | null {
  if (!value || typeof value !== "object") return null;
  const v = value as Record<string, unknown>;
  const text = (x: unknown, max: number): x is string =>
    typeof x === "string" &&
    x.trim().length > 0 &&
    x.length <= max &&
    !/[\u0000-\u001f\u007f]/.test(x);
  if (
    !validDirectoryId(v.installationId) ||
    !validDirectoryId(v.localUserId) ||
    !text(v.name, 120) ||
    !text(v.localUsername, 120) ||
    !["HOME", "BUSINESS"].includes(String(v.spaceType)) ||
    typeof v.linkedAt !== "string"
  )
    return null;
  const time = Date.parse(v.linkedAt);
  if (
    !Number.isFinite(time) ||
    time < Date.UTC(2000, 0, 1) ||
    time > Date.now() + 300000
  )
    return null;
  return {
    installationId: v.installationId,
    localUserId: v.localUserId,
    name: v.name.trim(),
    localUsername: v.localUsername.trim(),
    spaceType: v.spaceType as "HOME" | "BUSINESS",
    linkedAt: new Date(time).toISOString(),
  };
}

export async function reportSubject(
  config: AccountConfig,
  token: string,
): Promise<string | null> {
  const value = await oidc.tokenIntrospection(await discover(config), token);
  const audience = typeof value.aud === "string" ? [value.aud] : value.aud;
  return value.active &&
    value.iss === config.issuer.href &&
    value.client_id === "kyrion-local" &&
    Array.isArray(audience) &&
    audience.includes(config.clientId) &&
    typeof value.sub === "string" &&
    value.sub.length <= 255 &&
    value.sub.length > 0
    ? value.sub
    : null;
}

export class InstallationStore {
  constructor(private pool: Pool) {}

  async list(accountId: string): Promise<LinkedInstallation[]> {
    const result = await this.pool.query<LinkedInstallation>(
      'SELECT id,name,space_type AS "spaceType",local_username AS "localUsername",linked_at AS "linkedAt",confirmed_at AS "confirmedAt" FROM website_installation_link WHERE account_id=$1 ORDER BY linked_at DESC,id LIMIT 100',
      [accountId],
    );
    return result.rows;
  }

  async report(issuer: string, subject: string, body: InstallationReport) {
    const credential = secret();
    const client = await this.pool.connect();
    try {
      await client.query("BEGIN");
      const account = await client.query<{
        id: string;
      }>(
        "INSERT INTO website_account(issuer,subject) VALUES($1,$2) ON CONFLICT(issuer,subject) DO UPDATE SET issuer=EXCLUDED.issuer RETURNING id",
        [issuer, subject],
      );
      const result = await client.query<{ id: string }>(
        `INSERT INTO website_installation_link(account_id,installation_id,local_user_id,name,space_type,local_username,linked_at,credential_hash)
        VALUES($1,$2,$3,$4,$5,$6,$7,$8) ON CONFLICT(account_id,installation_id,local_user_id) DO UPDATE SET
        name=EXCLUDED.name,space_type=EXCLUDED.space_type,local_username=EXCLUDED.local_username,linked_at=EXCLUDED.linked_at,confirmed_at=now(),credential_hash=EXCLUDED.credential_hash RETURNING id`,
        [
          account.rows[0].id,
          body.installationId,
          body.localUserId,
          body.name,
          body.spaceType,
          body.localUsername,
          body.linkedAt,
          hash(credential),
        ],
      );
      await client.query(
        "INSERT INTO website_account_event(account_id,event_code,correlation_id) VALUES($1,'INSTALLATION_LINKED',$2)",
        [account.rows[0].id, result.rows[0].id],
      );
      await client.query("COMMIT");
      return { id: result.rows[0].id, credential };
    } catch (error) {
      await client.query("ROLLBACK");
      throw error;
    } finally {
      client.release();
    }
  }

  async update(id: string, credential: string, body: InstallationReport) {
    const result = await this.pool.query(
      "UPDATE website_installation_link SET name=$3,space_type=$4,local_username=$5,linked_at=$6,confirmed_at=now() WHERE id=$1 AND credential_hash=$2 AND installation_id=$7 AND local_user_id=$8",
      [
        id,
        hash(credential),
        body.name,
        body.spaceType,
        body.localUsername,
        body.linkedAt,
        body.installationId,
        body.localUserId,
      ],
    );
    return result.rowCount === 1;
  }

  async remove(id: string, credential: string) {
    const result = await this.pool.query(
      "WITH removed AS (DELETE FROM website_installation_link WHERE id=$1 AND credential_hash=$2 RETURNING account_id,id) INSERT INTO website_account_event(account_id,event_code,correlation_id) SELECT account_id,'INSTALLATION_UNLINKED',id FROM removed",
      [id, hash(credential)],
    );
    return result.rowCount === 1;
  }
}
