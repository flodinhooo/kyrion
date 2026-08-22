CREATE TABLE personal_backup_import_record (
    owner_id UUID NOT NULL REFERENCES user_account (id) ON DELETE CASCADE,
    record_type VARCHAR(20) NOT NULL,
    source_id UUID NOT NULL,
    target_id UUID NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (owner_id, record_type, source_id),
    CONSTRAINT personal_backup_import_record_type_check CHECK (record_type IN ('conversation', 'message', 'memory'))
);
