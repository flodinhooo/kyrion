CREATE TABLE home_assistant_selection_state (
    owner_id UUID PRIMARY KEY REFERENCES user_account (id) ON DELETE CASCADE,
    revision BIGINT NOT NULL CHECK (revision > 0),
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE home_assistant_device_selection (
    owner_id UUID NOT NULL REFERENCES user_account (id) ON DELETE CASCADE,
    external_id VARCHAR(64) NOT NULL,
    entity_ids TEXT NOT NULL,
    control_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    room_override BOOLEAN NOT NULL DEFAULT FALSE,
    room_id UUID REFERENCES owner_room (id) ON DELETE SET NULL,
    PRIMARY KEY (owner_id, external_id)
);
