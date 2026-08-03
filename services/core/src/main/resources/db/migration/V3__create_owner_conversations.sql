CREATE TABLE conversation (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES user_account (id) ON DELETE CASCADE,
    title VARCHAR(160) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE conversation_message (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversation (id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    position INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT conversation_message_role_check CHECK (role IN ('user', 'assistant')),
    CONSTRAINT conversation_message_position_unique UNIQUE (conversation_id, position)
);

CREATE INDEX conversation_owner_updated_idx ON conversation (owner_id, updated_at DESC);
