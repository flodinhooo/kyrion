CREATE TABLE zigbee_motion_event (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES user_account (id) ON DELETE CASCADE,
    sensor_connection_id UUID NOT NULL REFERENCES integration_connection (id) ON DELETE CASCADE,
    detected BOOLEAN NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX zigbee_motion_event_sensor_time_idx
    ON zigbee_motion_event (owner_id, sensor_connection_id, occurred_at DESC);
