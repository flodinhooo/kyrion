CREATE TABLE voice_satellite_enrollment (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES user_account (id) ON DELETE CASCADE,
    token_hash CHAR(64) NOT NULL UNIQUE,
    display_name VARCHAR(120) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE voice_satellite (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES user_account (id) ON DELETE CASCADE,
    display_name VARCHAR(120) NOT NULL,
    hostname VARCHAR(253) NOT NULL,
    credential_hash CHAR(64) NOT NULL UNIQUE,
    runtime_version VARCHAR(40) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT voice_satellite_owner_hostname_unique UNIQUE (owner_id, hostname)
);

CREATE TABLE voice_dialogue_session (
    id UUID PRIMARY KEY,
    satellite_id UUID NOT NULL REFERENCES voice_satellite (id) ON DELETE CASCADE,
    owner_id UUID NOT NULL REFERENCES user_account (id) ON DELETE CASCADE,
    conversation_id UUID NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('active', 'closed', 'expired', 'failed')),
    close_reason VARCHAR(40),
    started_at TIMESTAMPTZ NOT NULL,
    last_activity_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    closed_at TIMESTAMPTZ
);

CREATE INDEX voice_satellite_owner_idx ON voice_satellite (owner_id, display_name);
CREATE INDEX voice_dialogue_session_active_idx
    ON voice_dialogue_session (satellite_id, status, expires_at);
