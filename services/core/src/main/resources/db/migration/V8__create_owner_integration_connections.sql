CREATE TABLE integration_connection (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES user_account (id) ON DELETE CASCADE,
    provider VARCHAR(80) NOT NULL,
    display_name VARCHAR(160) NOT NULL,
    endpoint_host VARCHAR(45) NOT NULL,
    credential_ciphertext BYTEA NOT NULL,
    credential_nonce BYTEA NOT NULL,
    credential_version SMALLINT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT integration_connection_owner_provider_host_unique UNIQUE (owner_id, provider, endpoint_host)
);

CREATE INDEX integration_connection_owner_provider_idx ON integration_connection (owner_id, provider);
