-- Default-private opt-in only: no existing calendars are automatically shared.
CREATE TABLE personal_calendar_disclosure (
    id UUID PRIMARY KEY,
    space_id UUID NOT NULL REFERENCES kyrion_space(id),
    user_id UUID NOT NULL,
    connection_id UUID NOT NULL,
    calendar_id VARCHAR(512) NOT NULL CHECK (length(trim(calendar_id)) > 0 AND calendar_id <> 'primary'),
    visibility VARCHAR(16) NOT NULL CHECK (visibility IN ('PRIVATE','AVAILABILITY','DETAILS')),
    revision BIGINT NOT NULL CHECK (revision > 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(connection_id,calendar_id),
    FOREIGN KEY(user_id,space_id) REFERENCES user_account(id,space_id) ON DELETE CASCADE,
    FOREIGN KEY(connection_id,user_id) REFERENCES integration_connection(id,owner_id) ON DELETE CASCADE
);
CREATE INDEX personal_calendar_disclosure_space_idx ON personal_calendar_disclosure(space_id);
