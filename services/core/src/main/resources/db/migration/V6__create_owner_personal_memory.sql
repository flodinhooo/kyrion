CREATE TABLE owner_memory_settings (
    owner_id UUID PRIMARY KEY REFERENCES user_account (id) ON DELETE CASCADE,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE personal_memory (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES user_account (id) ON DELETE CASCADE,
    category VARCHAR(30) NOT NULL,
    content TEXT NOT NULL,
    sensitivity VARCHAR(20) NOT NULL,
    origin VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    source_conversation_id UUID REFERENCES conversation (id) ON DELETE SET NULL,
    source_message_id UUID REFERENCES conversation_message (id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    confirmed_at TIMESTAMPTZ,
    CONSTRAINT personal_memory_category_check
        CHECK (category IN ('preference', 'person', 'project', 'value', 'other')),
    CONSTRAINT personal_memory_sensitivity_check CHECK (sensitivity IN ('standard', 'sensitive')),
    CONSTRAINT personal_memory_origin_check CHECK (origin = 'explicit'),
    CONSTRAINT personal_memory_status_check CHECK (status IN ('proposed', 'confirmed')),
    CONSTRAINT personal_memory_confirmation_check CHECK (
        (status = 'confirmed' AND confirmed_at IS NOT NULL)
        OR (status = 'proposed' AND confirmed_at IS NULL)
    )
);

CREATE INDEX personal_memory_owner_updated_idx ON personal_memory (owner_id, updated_at DESC);
