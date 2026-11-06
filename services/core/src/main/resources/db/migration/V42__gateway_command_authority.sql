ALTER TABLE gateway_command ADD COLUMN authority JSONB;

-- No provenance is inferred for existing commands or automation bindings.
ALTER TABLE zigbee_button_binding ADD COLUMN grant_id UUID;
ALTER TABLE zigbee_button_binding ADD COLUMN granted_by UUID REFERENCES user_account(id);
ALTER TABLE zigbee_button_binding ADD COLUMN source_node_id UUID REFERENCES gateway_node(id);
ALTER TABLE zigbee_button_binding ADD CONSTRAINT button_grant_provenance_complete CHECK (
    (grant_id IS NULL AND granted_by IS NULL AND source_node_id IS NULL) OR
    (grant_id IS NOT NULL AND granted_by IS NOT NULL AND source_node_id IS NOT NULL)
);
CREATE UNIQUE INDEX zigbee_button_binding_grant_idx ON zigbee_button_binding(grant_id);
