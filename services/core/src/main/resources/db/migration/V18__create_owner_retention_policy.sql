CREATE TABLE owner_retention_policy (
    owner_id UUID PRIMARY KEY REFERENCES user_account (id) ON DELETE CASCADE,
    conversation_policy VARCHAR(20) NOT NULL DEFAULT 'keep_forever',
    activity_policy VARCHAR(20) NOT NULL DEFAULT 'keep_forever',
    personal_memory_policy VARCHAR(20) NOT NULL DEFAULT 'keep_forever',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT owner_retention_conversation_check CHECK (conversation_policy IN ('keep_forever', '30_days', '90_days', '365_days', '3_years')),
    CONSTRAINT owner_retention_activity_check CHECK (activity_policy IN ('keep_forever', '30_days', '90_days', '365_days', '3_years')),
    CONSTRAINT owner_retention_memory_check CHECK (personal_memory_policy IN ('keep_forever', '30_days', '90_days', '365_days', '3_years'))
);
