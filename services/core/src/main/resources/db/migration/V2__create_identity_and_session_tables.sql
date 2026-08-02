CREATE TABLE user_account (
    id UUID PRIMARY KEY,
    username VARCHAR(120) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT user_account_username_unique UNIQUE (username)
);

CREATE TABLE auth_session (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES user_account (id) ON DELETE CASCADE,
    token_hash CHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    CONSTRAINT auth_session_token_hash_unique UNIQUE (token_hash),
    CONSTRAINT auth_session_expiry_check CHECK (expires_at > created_at)
);

CREATE INDEX auth_session_user_id_idx ON auth_session (user_id);
CREATE INDEX auth_session_expires_at_idx ON auth_session (expires_at);
