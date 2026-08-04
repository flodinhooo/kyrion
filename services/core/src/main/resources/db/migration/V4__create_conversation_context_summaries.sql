CREATE TABLE conversation_context_summary (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversation (id) ON DELETE CASCADE,
    source_start_position INTEGER NOT NULL,
    source_end_position INTEGER NOT NULL,
    algorithm_version INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT conversation_context_summary_range_check
        CHECK (source_start_position >= 0 AND source_end_position >= source_start_position),
    CONSTRAINT conversation_context_summary_version_check CHECK (algorithm_version > 0),
    CONSTRAINT conversation_context_summary_range_unique
        UNIQUE (conversation_id, source_start_position, source_end_position, algorithm_version)
);

CREATE INDEX conversation_context_summary_latest_idx
    ON conversation_context_summary (conversation_id, source_end_position DESC, algorithm_version DESC);
