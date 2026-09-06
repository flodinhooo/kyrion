CREATE TABLE home_assistant_device (
    connection_id UUID PRIMARY KEY REFERENCES integration_connection(id) ON DELETE CASCADE,
    owner_id UUID NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
    hardware_name VARCHAR(321) NOT NULL,
    on_state BOOLEAN,
    temperature_celsius DOUBLE PRECISION,
    relative_humidity DOUBLE PRECISION,
    battery DOUBLE PRECISION,
    occupancy BOOLEAN,
    measured_at TIMESTAMPTZ,
    capabilities VARCHAR(250) NOT NULL
);
CREATE INDEX home_assistant_device_owner_idx ON home_assistant_device(owner_id);

ALTER TABLE device_observation DROP CONSTRAINT device_observation_availability_check;
ALTER TABLE device_observation ADD CONSTRAINT device_observation_availability_check
    CHECK (availability IN ('online', 'offline', 'degraded', 'unknown'));

CREATE TABLE home_assistant_sync (
    owner_id UUID PRIMARY KEY REFERENCES user_account(id) ON DELETE CASCADE,
    attempted_at TIMESTAMPTZ NOT NULL,
    succeeded_at TIMESTAMPTZ,
    reason VARCHAR(80),
    correlation_id UUID NOT NULL
);
