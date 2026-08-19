CREATE TABLE action_execution (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
    idempotency_key UUID NOT NULL,
    correlation_id UUID NOT NULL,
    request_hash VARCHAR(64) NOT NULL,
    status VARCHAR(16) NOT NULL,
    outcome JSONB,
    created_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    CONSTRAINT action_execution_owner_idempotency_unique UNIQUE (owner_id, idempotency_key),
    CONSTRAINT action_execution_status_valid CHECK (status IN ('pending', 'completed'))
);

CREATE INDEX action_execution_owner_created_idx ON action_execution(owner_id, created_at DESC);
