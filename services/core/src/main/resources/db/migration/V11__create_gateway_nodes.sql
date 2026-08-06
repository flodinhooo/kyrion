CREATE TABLE gateway_enrollment (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES user_account (id) ON DELETE CASCADE,
    token_hash CHAR(64) NOT NULL UNIQUE,
    display_name VARCHAR(120) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX gateway_enrollment_owner_idx ON gateway_enrollment (owner_id, created_at DESC);

CREATE TABLE gateway_node (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES user_account (id) ON DELETE CASCADE,
    display_name VARCHAR(120) NOT NULL,
    hostname VARCHAR(253) NOT NULL,
    credential_hash CHAR(64) NOT NULL UNIQUE,
    agent_version VARCHAR(40) NOT NULL,
    os_name VARCHAR(120) NOT NULL,
    os_version VARCHAR(80) NOT NULL,
    architecture VARCHAR(40) NOT NULL,
    last_seen_at TIMESTAMPTZ,
    health JSONB,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT gateway_node_owner_hostname_unique UNIQUE (owner_id, hostname)
);

CREATE INDEX gateway_node_owner_idx ON gateway_node (owner_id, display_name);
