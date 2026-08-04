CREATE TABLE conversation_turn (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversation (id) ON DELETE CASCADE,
    user_message_id UUID NOT NULL REFERENCES conversation_message (id) ON DELETE CASCADE,
    assistant_message_id UUID REFERENCES conversation_message (id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL,
    error_code VARCHAR(80),
    started_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT conversation_turn_user_unique UNIQUE (user_message_id),
    CONSTRAINT conversation_turn_status_check CHECK (status IN ('started', 'completed', 'stopped', 'failed')),
    CONSTRAINT conversation_turn_completion_check CHECK (
        (status IN ('completed', 'stopped') AND assistant_message_id IS NOT NULL AND error_code IS NULL)
        OR (status = 'failed' AND assistant_message_id IS NULL AND error_code IS NOT NULL)
        OR (status = 'started' AND assistant_message_id IS NULL AND error_code IS NULL)
    )
);

CREATE INDEX conversation_turn_conversation_started_idx
    ON conversation_turn (conversation_id, started_at DESC);
