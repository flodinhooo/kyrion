ALTER TABLE personal_memory
  ADD COLUMN active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE personal_memory
  ADD COLUMN expires_at TIMESTAMPTZ;
ALTER TABLE owner_memory_settings
  ADD COLUMN history_enabled BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE owner_memory_settings
  ADD COLUMN preferences_enabled BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE owner_memory_settings
  ADD COLUMN categories TEXT NOT NULL DEFAULT 'preference,person,project,value,other';
CREATE INDEX personal_memory_context_idx ON personal_memory (owner_id, status, active, expires_at);
