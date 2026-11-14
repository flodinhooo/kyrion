-- Legacy registrations remain unassociated; never infer provenance by hostname.
ALTER TABLE gateway_enrollment
    ADD CONSTRAINT gateway_enrollment_id_owner_unique UNIQUE (id, owner_id);

ALTER TABLE gateway_node ADD COLUMN enrollment_id UUID;

ALTER TABLE gateway_node
    ADD CONSTRAINT gateway_node_enrollment_owner_fk
    FOREIGN KEY (enrollment_id, owner_id) REFERENCES gateway_enrollment (id, owner_id)
    ON DELETE SET NULL (enrollment_id);

CREATE UNIQUE INDEX gateway_node_enrollment_unique
    ON gateway_node (enrollment_id) WHERE enrollment_id IS NOT NULL;
