CREATE TABLE integration_connection_capability (
    owner_id UUID NOT NULL REFERENCES user_account (id) ON DELETE CASCADE,
    connection_id UUID NOT NULL REFERENCES integration_connection (id) ON DELETE CASCADE,
    capability VARCHAR(160) NOT NULL,
    granted BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (owner_id, connection_id, capability)
);
