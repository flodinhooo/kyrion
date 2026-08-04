ALTER TABLE personal_memory ADD COLUMN conflicts_with_memory_id UUID REFERENCES personal_memory (id) ON DELETE SET NULL;

ALTER TABLE personal_memory DROP CONSTRAINT personal_memory_status_check;
ALTER TABLE personal_memory DROP CONSTRAINT personal_memory_confirmation_check;
ALTER TABLE personal_memory ADD CONSTRAINT personal_memory_status_check
    CHECK (status IN ('proposed', 'confirmed', 'superseded'));
ALTER TABLE personal_memory ADD CONSTRAINT personal_memory_confirmation_check CHECK (
    (status IN ('confirmed', 'superseded') AND confirmed_at IS NOT NULL)
    OR (status = 'proposed' AND confirmed_at IS NULL)
);

CREATE INDEX personal_memory_conflict_idx ON personal_memory (conflicts_with_memory_id);
