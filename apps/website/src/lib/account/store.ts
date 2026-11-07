import { createHash, randomBytes } from "node:crypto";
import { Pool } from "pg";

export const secret = () => randomBytes(32).toString("base64url");
export const hash = (value: string) =>
  createHash("sha256").update(value).digest("hex");
export type Flow = {
  state: string;
  nonce: string;
  verifier: string;
  locale: "en" | "de";
};
export type WebsiteSession = { id: string; csrf: string; expiresAt: string };

const pools = new Map<string, Pool>();
export function database(connectionString: string) {
  let pool = pools.get(connectionString);
  if (!pool) {
    pool = new Pool({
      connectionString,
      enableChannelBinding: true,
      max: 5,
      connectionTimeoutMillis: 5000,
      statement_timeout: 5000,
    });
    pools.set(connectionString, pool);
  }
  return pool;
}

export class AccountStore {
  constructor(private pool: Pool) {}

  async begin(id: string, flow: Flow) {
    await this.pool.query(
      "DELETE FROM website_oidc_flow WHERE expires_at < now()",
    );
    await this.pool.query(
      "INSERT INTO website_oidc_flow (id_hash,state,nonce,verifier,locale,expires_at) VALUES ($1,$2,$3,$4,$5,now()+interval '5 minutes')",
      [hash(id), flow.state, flow.nonce, flow.verifier, flow.locale],
    );
  }

  async consume(id: string): Promise<Flow | null> {
    const result = await this.pool.query<Flow>(
      "DELETE FROM website_oidc_flow WHERE id_hash=$1 AND expires_at>now() RETURNING state,nonce,verifier,locale",
      [hash(id)],
    );
    return result.rows[0] ?? null;
  }

  async issue(issuer: string, subject: string, tokenExpiresAt: number) {
    const id = secret();
    const csrf = secret();
    const expiresAt = new Date(
      Math.min(Date.now() + 15 * 60_000, tokenExpiresAt * 1000),
    );
    if (expiresAt.getTime() <= Date.now())
      throw new Error("Expired central authentication");
    const client = await this.pool.connect();
    try {
      await client.query("BEGIN");
      const account = await client.query<{ id: string }>(
        "INSERT INTO website_account (issuer,subject) VALUES ($1,$2) ON CONFLICT (issuer,subject) DO UPDATE SET issuer=EXCLUDED.issuer RETURNING id",
        [issuer, subject],
      );
      await client.query(
        "INSERT INTO website_session (token_hash,account_id,csrf,expires_at) VALUES ($1,$2,$3,$4)",
        [hash(id), account.rows[0].id, csrf, expiresAt],
      );
      await client.query(
        "INSERT INTO website_account_event (account_id,event_code) VALUES ($1,'SESSION_CREATED')",
        [account.rows[0].id],
      );
      await client.query("COMMIT");
      return { id, csrf, expiresAt: expiresAt.toISOString() };
    } catch (error) {
      await client.query("ROLLBACK");
      throw error;
    } finally {
      client.release();
    }
  }

  async session(token: string): Promise<WebsiteSession | null> {
    const result = await this.pool.query<WebsiteSession>(
      'SELECT account_id AS id,csrf,expires_at AS "expiresAt" FROM website_session WHERE token_hash=$1 AND expires_at>now()',
      [hash(token)],
    );
    return result.rows[0] ?? null;
  }

  async revoke(token: string) {
    await this.pool.query(
      "WITH revoked AS (DELETE FROM website_session WHERE token_hash=$1 RETURNING account_id) INSERT INTO website_account_event (account_id,event_code) SELECT account_id,'SESSION_REVOKED' FROM revoked",
      [hash(token)],
    );
  }
}
