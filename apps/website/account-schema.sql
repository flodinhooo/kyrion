-- Apply to a dedicated CENTRAL website database, never an installation database.
CREATE TABLE IF NOT EXISTS website_account (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    issuer text NOT NULL,
    subject text NOT NULL,
    UNIQUE (issuer, subject)
);
CREATE TABLE IF NOT EXISTS website_oidc_flow (
    id_hash text PRIMARY KEY,
    state text NOT NULL,
    nonce text NOT NULL,
    verifier text NOT NULL,
    locale text NOT NULL CHECK (locale IN ('en','de')),
    expires_at timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS website_session (
    token_hash text PRIMARY KEY,
    account_id uuid NOT NULL REFERENCES website_account(id) ON DELETE CASCADE,
    csrf text NOT NULL,
    refresh_credential text,
    verified_until timestamptz,
    expires_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS website_session_expiry ON website_session(expires_at);
CREATE TABLE IF NOT EXISTS website_account_event (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id uuid REFERENCES website_account(id) ON DELETE SET NULL,
    event_code text NOT NULL CHECK (event_code IN ('SESSION_CREATED','SESSION_REVOKED')),
    correlation_id uuid NOT NULL DEFAULT gen_random_uuid(),
    created_at timestamptz NOT NULL DEFAULT now()
);
