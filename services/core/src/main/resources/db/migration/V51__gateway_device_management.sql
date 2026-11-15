ALTER TABLE gateway_node
    ADD COLUMN expected_availability text NOT NULL DEFAULT 'unknown'
        CHECK (expected_availability IN ('unknown', 'always_on', 'intermittent')),
    ADD COLUMN management_revision uuid NOT NULL DEFAULT gen_random_uuid(),
    ADD COLUMN revoked_at timestamptz,
    ADD COLUMN task_policy jsonb CHECK (task_policy IS NULL OR
        (jsonb_typeof(task_policy) = 'array' AND task_policy <@ '["integration","voice"]'::jsonb));

ALTER TABLE gateway_node ADD CONSTRAINT gateway_node_id_owner_unique UNIQUE (id, owner_id);
ALTER TABLE gateway_node DROP CONSTRAINT gateway_node_owner_hostname_unique;
CREATE UNIQUE INDEX gateway_node_active_hostname_unique ON gateway_node(owner_id, hostname)
    WHERE revoked_at IS NULL;
ALTER TABLE voice_satellite
    ADD COLUMN source_gateway_node_id uuid,
    ADD COLUMN revoked_at timestamptz;
ALTER TABLE voice_satellite DROP CONSTRAINT voice_satellite_owner_hostname_unique;
CREATE UNIQUE INDEX voice_satellite_active_hostname_unique ON voice_satellite(owner_id, hostname)
    WHERE revoked_at IS NULL;
ALTER TABLE voice_satellite ADD CONSTRAINT voice_satellite_source_gateway_fk
    FOREIGN KEY (source_gateway_node_id, owner_id) REFERENCES gateway_node(id, owner_id);
CREATE INDEX voice_satellite_source_gateway_idx ON voice_satellite(source_gateway_node_id)
    WHERE source_gateway_node_id IS NOT NULL;
