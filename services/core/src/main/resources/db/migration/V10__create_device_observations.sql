CREATE TABLE device_observation (
    connection_id UUID PRIMARY KEY REFERENCES integration_connection (id) ON DELETE CASCADE,
    owner_id UUID NOT NULL REFERENCES user_account (id) ON DELETE CASCADE,
    availability VARCHAR(20) NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT device_observation_availability_check
        CHECK (availability IN ('online', 'offline', 'degraded'))
);

CREATE INDEX device_observation_owner_idx ON device_observation (owner_id);
