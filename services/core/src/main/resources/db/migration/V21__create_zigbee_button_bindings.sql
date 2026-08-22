CREATE TABLE zigbee_button_binding (
    owner_id UUID NOT NULL REFERENCES user_account (id) ON DELETE CASCADE,
    button_connection_id UUID NOT NULL REFERENCES integration_connection (id) ON DELETE CASCADE,
    gesture VARCHAR(12) NOT NULL CHECK (gesture IN ('single', 'double', 'long')),
    target_connection_id UUID NOT NULL REFERENCES integration_connection (id) ON DELETE CASCADE,
    action VARCHAR(12) NOT NULL CHECK (action IN ('toggle', 'turn_on', 'turn_off')),
    updated_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (button_connection_id, gesture)
);

CREATE INDEX zigbee_button_binding_owner_idx ON zigbee_button_binding (owner_id);
