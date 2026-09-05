CREATE TABLE shelly_sensor_reading (
    connection_id UUID PRIMARY KEY REFERENCES integration_connection(id) ON DELETE CASCADE,
    owner_id UUID NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
    temperature_celsius DOUBLE PRECISION CHECK (temperature_celsius BETWEEN -100 AND 150),
    relative_humidity DOUBLE PRECISION CHECK (relative_humidity BETWEEN 0 AND 100),
    battery DOUBLE PRECISION CHECK (battery BETWEEN 0 AND 100),
    observed_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX shelly_sensor_reading_owner_idx ON shelly_sensor_reading(owner_id);
