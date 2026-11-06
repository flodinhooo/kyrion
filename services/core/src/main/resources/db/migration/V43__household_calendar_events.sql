-- New native joint events only. Preserve legacy local events and Google mappings.
CREATE TABLE household_calendar_event (
    id UUID PRIMARY KEY,
    space_id UUID NOT NULL REFERENCES kyrion_space(id),
    created_by UUID NOT NULL,
    title VARCHAR(500) NOT NULL CHECK (length(trim(title)) > 0),
    description VARCHAR(10000),
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL CHECK (ends_at > starts_at),
    time_zone VARCHAR(120) NOT NULL,
    revision BIGINT NOT NULL DEFAULT 0 CHECK (revision >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (id, space_id),
    FOREIGN KEY (created_by, space_id) REFERENCES user_account(id, space_id)
);
CREATE INDEX household_calendar_event_range_idx ON household_calendar_event(space_id, starts_at);

CREATE TABLE household_calendar_participant (
    event_id UUID NOT NULL,
    space_id UUID NOT NULL,
    user_id UUID NOT NULL,
    PRIMARY KEY (event_id, user_id),
    FOREIGN KEY (event_id, space_id) REFERENCES household_calendar_event(id, space_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id, space_id) REFERENCES user_account(id, space_id)
);
