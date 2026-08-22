ALTER TABLE zigbee_button_binding
    ALTER COLUMN target_connection_id DROP NOT NULL,
    ADD COLUMN target_room_id UUID REFERENCES owner_room (id) ON DELETE CASCADE,
    ADD CONSTRAINT zigbee_button_binding_single_target_check CHECK (
        (target_connection_id IS NOT NULL AND target_room_id IS NULL)
        OR (target_connection_id IS NULL AND target_room_id IS NOT NULL)
    );
