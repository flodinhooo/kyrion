CREATE TABLE gateway_command (
    id UUID PRIMARY KEY,
    node_id UUID NOT NULL REFERENCES gateway_node(id) ON DELETE CASCADE,
    owner_id UUID NOT NULL,
    command_type VARCHAR(80) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(24) NOT NULL,
    error_code VARCHAR(80),
    created_at TIMESTAMPTZ NOT NULL,
    claimed_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX gateway_command_pending_idx ON gateway_command(node_id, created_at)
    WHERE status = 'pending';
