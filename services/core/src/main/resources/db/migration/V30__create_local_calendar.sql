CREATE TABLE local_calendar_event (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    time_zone VARCHAR(80) NOT NULL,
    google_calendar_id VARCHAR(512),
    google_event_id VARCHAR(512),
    content_fingerprint VARCHAR(64) NOT NULL,
    sync_to_google BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT local_calendar_google_event_unique UNIQUE (owner_id, google_calendar_id, google_event_id)
);
CREATE INDEX local_calendar_owner_time_idx ON local_calendar_event(owner_id, starts_at);
