CREATE TABLE calendar_sync_schedule (
    actor_id UUID PRIMARY KEY REFERENCES user_account(id) ON DELETE CASCADE,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    interval_seconds INTEGER NOT NULL DEFAULT 300 CHECK(interval_seconds BETWEEN 60 AND 86400),
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_attempt_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    failure_count INTEGER NOT NULL DEFAULT 0,
    last_error VARCHAR(80),
    lease_token UUID,
    lease_until TIMESTAMPTZ
);
