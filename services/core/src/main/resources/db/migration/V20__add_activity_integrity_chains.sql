ALTER TABLE activity_event
    ADD COLUMN integrity_sequence BIGINT GENERATED ALWAYS AS IDENTITY,
    ADD COLUMN integrity_version SMALLINT,
    ADD COLUMN chain_scope VARCHAR(64),
    ADD COLUMN previous_hash BYTEA,
    ADD COLUMN event_hash BYTEA;

ALTER TABLE activity_event ADD CONSTRAINT activity_event_integrity_check CHECK (
    (integrity_version IS NULL AND chain_scope IS NULL AND previous_hash IS NULL AND event_hash IS NULL)
    OR (integrity_version = 1 AND chain_scope IS NOT NULL AND event_hash IS NOT NULL)
);

CREATE INDEX activity_event_chain_sequence_idx
    ON activity_event (chain_scope, integrity_sequence)
    WHERE integrity_version IS NOT NULL;

CREATE TABLE activity_integrity_chain (
    chain_scope VARCHAR(64) PRIMARY KEY,
    last_event_id UUID,
    last_hash BYTEA,
    anchor_previous_hash BYTEA,
    anchor_mac BYTEA,
    updated_at TIMESTAMPTZ NOT NULL
);
