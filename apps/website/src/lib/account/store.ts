import { createHash, randomBytes } from "node:crypto";
import { Pool } from "pg";
import type { AccountConfig } from "./config";
import { protectRefresh, readRefresh } from "./credentials";
import { IdentityRevoked, renewIdentity } from "./oidc";

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
export const rememberedLifetime = 30 * 24 * 60 * 60_000;
type StoredSession = WebsiteSession & {
  issuer: string;
  subject: string;
  refresh_credential: string | null;
  verified_until: string | null;
};

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
  constructor(
    private pool: Pool,
    private config?: AccountConfig,
    private renew = renewIdentity,
  ) {}

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

  async issue(
    issuer: string,
    subject: string,
    tokenExpiresAt: number,
    refreshToken?: string,
  ) {
    const id = secret();
    const csrf = secret();
    const remembered = Boolean(refreshToken && this.config);
    const expiresAt = new Date(
      remembered
        ? Date.now() + rememberedLifetime
        : Math.min(Date.now() + 15 * 60_000, tokenExpiresAt * 1000),
    );
    if (tokenExpiresAt * 1000 <= Date.now())
      throw new Error("Expired central authentication");
    const client = await this.pool.connect();
    try {
      await client.query("BEGIN");
      const account = await client.query<{ id: string }>(
        "INSERT INTO website_account (issuer,subject) VALUES ($1,$2) ON CONFLICT (issuer,subject) DO UPDATE SET issuer=EXCLUDED.issuer RETURNING id",
        [issuer, subject],
      );
      await client.query(
        "INSERT INTO website_session (token_hash,account_id,csrf,expires_at,refresh_credential,verified_until) VALUES ($1,$2,$3,$4,$5,$6)",
        [
          hash(id),
          account.rows[0].id,
          csrf,
          expiresAt,
          remembered
            ? protectRefresh(refreshToken!, this.config!.clientSecret, hash(id))
            : null,
          new Date(Math.min(tokenExpiresAt * 1000, Date.now() + 5 * 60_000)),
        ],
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
    return this.load(token, true);
  }

  async forLogout(token: string): Promise<WebsiteSession | null> {
    return this.load(token, false);
  }

  private async load(
    token: string,
    verify: boolean,
  ): Promise<WebsiteSession | null> {
    if (!token) return null;
    const client = await this.pool.connect();
    try {
      await client.query("BEGIN");
      const result = await client.query<StoredSession>(
        'SELECT s.account_id AS id,s.csrf,s.expires_at AS "expiresAt",s.refresh_credential,s.verified_until,a.issuer,a.subject FROM website_session s JOIN website_account a ON a.id=s.account_id WHERE s.token_hash=$1 AND s.expires_at>now() FOR UPDATE OF s',
        [hash(token)],
      );
      const row = result.rows[0];
      if (!row) {
        await client.query("COMMIT");
        return null;
      }
      if (
        verify &&
        row.refresh_credential &&
        (!row.verified_until ||
          new Date(row.verified_until).getTime() <= Date.now())
      ) {
        if (!this.config) throw new Error("Session renewal unavailable");
        try {
          let credential: string;
          try {
            credential = readRefresh(
              row.refresh_credential,
              this.config.clientSecret,
              hash(token),
            );
          } catch {
            throw new IdentityRevoked("Credential unavailable");
          }
          const identity = await this.renew(this.config, credential);
          if (
            identity.issuer !== row.issuer ||
            identity.subject !== row.subject ||
            identity.expiresAt * 1000 <= Date.now()
          )
            throw new IdentityRevoked("Identity changed");
          await client.query(
            "UPDATE website_session SET refresh_credential=$2,verified_until=$3 WHERE token_hash=$1",
            [
              hash(token),
              protectRefresh(
                identity.refreshToken,
                this.config.clientSecret,
                hash(token),
              ),
              new Date(
                Math.min(identity.expiresAt * 1000, Date.now() + 5 * 60_000),
              ),
            ],
          );
        } catch (error) {
          if (!(error instanceof IdentityRevoked)) throw error;
          await client.query(
            "DELETE FROM website_session WHERE token_hash=$1",
            [hash(token)],
          );
          await client.query(
            "INSERT INTO website_account_event (account_id,event_code) VALUES ($1,'SESSION_REVOKED')",
            [row.id],
          );
          await client.query("COMMIT");
          return null;
        }
      }
      await client.query("COMMIT");
      return { id: row.id, csrf: row.csrf, expiresAt: row.expiresAt };
    } catch (error) {
      await client.query("ROLLBACK");
      throw error;
    } finally {
      client.release();
    }
  }

  async revoke(token: string) {
    const client = await this.pool.connect();
    let encrypted: string | null = null;
    try {
      await client.query("BEGIN");
      const result = await client.query<{
        account_id: string;
        refresh_credential: string | null;
      }>(
        "DELETE FROM website_session WHERE token_hash=$1 RETURNING account_id,refresh_credential",
        [hash(token)],
      );
      if (result.rows[0]) {
        encrypted = result.rows[0].refresh_credential;
        await client.query(
          "INSERT INTO website_account_event (account_id,event_code) VALUES ($1,'SESSION_REVOKED')",
          [result.rows[0].account_id],
        );
      }
      await client.query("COMMIT");
    } catch (error) {
      await client.query("ROLLBACK");
      throw error;
    } finally {
      client.release();
    }
    if (encrypted && this.config) {
      try {
        return readRefresh(encrypted, this.config.clientSecret, hash(token));
      } catch {
        /* Already revoked locally. */
      }
    }
  }
}
