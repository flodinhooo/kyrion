CREATE TABLE owner_room (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES user_account (id) ON DELETE CASCADE,
    name VARCHAR(120) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT owner_room_owner_name_unique UNIQUE (owner_id, name)
);

ALTER TABLE integration_connection
    ADD COLUMN room_id UUID REFERENCES owner_room (id) ON DELETE SET NULL;

CREATE INDEX owner_room_owner_idx ON owner_room (owner_id);
CREATE INDEX integration_connection_room_idx ON integration_connection (room_id);
