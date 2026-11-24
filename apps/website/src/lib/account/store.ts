import {
  credentialId,
  fetchInventory,
  type CredentialInventory,
} from "./credential-inventory";
import type { AccountAction } from "./actions";
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
  destination?: "account" | "connect" | AccountAction;
  expectedSubject?: string | null;
  credentialId?: string | null;
  removalCorrelation?: string;
};
export type WebsiteSession = { id: string; csrf: string; expiresAt: string };
export const rememberedLifetime = 30 * 24 * 60 * 60_000;
export type RemovalAudit = {
  credentialId: string;
  correlationId: string;
  result:
    | "CREDENTIAL_REMOVAL_RETURNED"
    | "CREDENTIAL_REMOVAL_ABSENT"
    | "CREDENTIAL_REMOVAL_RETAINED";
};
function removalCorrelation(id: string) {
  const value = hash(id).slice(0, 32);
  return [
    value.slice(0, 8),
    value.slice(8, 12),
    value.slice(12, 16),
    value.slice(16, 20),
    value.slice(20),
  ].join("-");
}

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
    private readInventory = fetchInventory,
  ) {}

  async begin(id: string, flow: Flow) {
    const client = await this.pool.connect();
    try {
      await client.query("BEGIN");
      await client.query(
        "DELETE FROM website_oidc_flow WHERE expires_at<now()",
      );
      await client.query(
        "INSERT INTO website_oidc_flow (id_hash,state,nonce,verifier,locale,destination,expected_subject,credential_id,expires_at) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,now()+interval '5 minutes')",
        [
          hash(id),
          flow.state,
          flow.nonce,
          flow.verifier,
          flow.locale,
          flow.destination ?? "account",
          flow.expectedSubject ?? null,
          flow.credentialId ?? null,
        ],
      );
      if (flow.destination === "remove") {
        if (
          !credentialId(flow.credentialId) ||
          !this.config ||
          !flow.expectedSubject
        )
          throw Error("Invalid removal intent");
        const event = await client.query(
          "INSERT INTO website_account_event (account_id,event_code,correlation_id,credential_id) SELECT id,'CREDENTIAL_REMOVAL_STARTED',$3,$4 FROM website_account WHERE issuer=$1 AND subject=$2",
          [
            this.config.issuer.href,
            flow.expectedSubject,
            removalCorrelation(id),
            flow.credentialId,
          ],
        );
        if (event.rowCount !== 1) throw Error("Removal account unavailable");
      }
      await client.query("COMMIT");
    } catch (error) {
      await client.query("ROLLBACK");
      throw error;
    } finally {
      client.release();
    }
  }

  async consume(id: string): Promise<Flow | null> {
    const result = await this.pool.query<Flow>(
      'DELETE FROM website_oidc_flow WHERE id_hash=$1 AND expires_at>now() RETURNING state,nonce,verifier,locale,destination,expected_subject AS "expectedSubject",credential_id AS "credentialId"',
      [hash(id)],
    );
    const flow = result.rows[0] ?? null;
    return flow?.destination === "remove"
      ? { ...flow, removalCorrelation: removalCorrelation(id) }
      : flow;
  }

  async issue(
    issuer: string,
    subject: string,
    tokenExpiresAt: number,
    refreshToken?: string,
    removal?: RemovalAudit,
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
      if (removal)
        await client.query(
          "INSERT INTO website_account_event (account_id,event_code,correlation_id,credential_id) VALUES ($1,$2,$3,$4)",
          [
            account.rows[0].id,
            removal.result,
            removal.correlationId,
            removal.credentialId,
          ],
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

  async actionSubject(token: string): Promise<string | null> {
    const result = await this.pool.query<{ subject: string }>(
      "SELECT a.subject FROM website_session s JOIN website_account a ON a.id=s.account_id WHERE s.token_hash=$1 AND s.expires_at>now() AND a.issuer=$2",
      [hash(token), this.config?.issuer.href],
    );
    return result.rows[0]?.subject ?? null;
  }

  async forLogout(token: string): Promise<WebsiteSession | null> {
    return this.load(token, false);
  }

  async credentialInventory(
    token: string,
  ): Promise<CredentialInventory | null> {
    let inventory: CredentialInventory | null = null;
    const session = await this.load(token, true, async (accessToken) => {
      if (!this.config) throw Error("Account configuration unavailable");
      inventory = await this.readInventory(this.config, accessToken);
    });
    return session ? inventory : null;
  }

  private async load(
    token: string,
    verify: boolean,
    read?: (accessToken: string) => Promise<void>,
  ): Promise<WebsiteSession | null> {
    if (!token) return null;
    const client = await this.pool.connect();
    let committed = false;
    try {
      await client.query("BEGIN");
      const result = await client.query<StoredSession>(
        'SELECT s.account_id AS id,s.csrf,s.expires_at AS "expiresAt",s.refresh_credential,s.verified_until,a.issuer,a.subject FROM website_session s JOIN website_account a ON a.id=s.account_id WHERE s.token_hash=$1 AND s.expires_at>now() FOR UPDATE OF s',
        [hash(token)],
      );
      const row = result.rows[0];
      if (!row || (read && !row.refresh_credential)) {
        await client.query("COMMIT");
        return null;
      }
      if (
        verify &&
        row.refresh_credential &&
        (read ||
          !row.verified_until ||
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
          if (read) {
            try {
              if (!identity.accessToken)
                throw Error("User account proof unavailable");
              await read(identity.accessToken);
            } catch {
              // Provider refresh rotation already happened. Preserve its replacement
              // even when the separate read fails, so retry cannot strand the session.
              await client.query("COMMIT");
              committed = true;
              throw Error("Credential inventory unavailable");
            }
          }
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
      if (!committed) await client.query("ROLLBACK");
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
