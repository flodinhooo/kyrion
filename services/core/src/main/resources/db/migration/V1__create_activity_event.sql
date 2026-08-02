CREATE TABLE activity_event (
    id UUID PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL,
    category VARCHAR(32) NOT NULL,
    event_type VARCHAR(120) NOT NULL,
    status VARCHAR(32) NOT NULL,
    actor_type VARCHAR(32) NOT NULL,
    actor_id VARCHAR(120),
    source VARCHAR(120) NOT NULL,
    correlation_id UUID NOT NULL,
    summary_code VARCHAR(160) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT activity_event_category_check
        CHECK (category IN ('SYSTEM', 'CAPABILITY', 'INTEGRATION', 'AUTOMATION', 'SECURITY')),
    CONSTRAINT activity_event_status_check
        CHECK (status IN ('PROPOSED', 'CONFIRMED', 'SUCCEEDED', 'FAILED', 'DENIED')),
    CONSTRAINT activity_event_actor_type_check
        CHECK (actor_type IN ('SYSTEM', 'USER', 'AI', 'INTEGRATION'))
);

CREATE INDEX activity_event_occurred_at_idx
    ON activity_event (occurred_at DESC);

CREATE INDEX activity_event_correlation_id_idx
    ON activity_event (correlation_id);
