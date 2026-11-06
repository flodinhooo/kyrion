-- Immutable consent generations; no destination is opted in by migration.
CREATE TABLE household_calendar_destination (
    id UUID PRIMARY KEY,
    space_id UUID NOT NULL REFERENCES kyrion_space(id),
    user_id UUID NOT NULL,
    connection_id UUID,
    calendar_id VARCHAR(512),
    active BOOLEAN NOT NULL,
    revision BIGINT NOT NULL CHECK(revision > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id,revision),
    UNIQUE(id,space_id),
    UNIQUE(id,space_id,user_id),
    FOREIGN KEY(user_id,space_id) REFERENCES user_account(id,space_id) ON DELETE CASCADE,
    FOREIGN KEY(connection_id,user_id) REFERENCES integration_connection(id,owner_id) ON DELETE SET NULL(connection_id),
    CHECK(calendar_id IS NULL OR (length(trim(calendar_id)) > 0 AND calendar_id <> 'primary')),
    CHECK(NOT active OR calendar_id IS NOT NULL)
);
CREATE UNIQUE INDEX household_destination_one_active_idx ON household_calendar_destination(user_id) WHERE active;

CREATE TABLE household_calendar_delivery (
    id UUID PRIMARY KEY,
    space_id UUID NOT NULL,
    event_id UUID NOT NULL,
    target_user_id UUID NOT NULL,
    grant_id UUID NOT NULL,
    destination_key VARCHAR(64) NOT NULL,
    remote_id VARCHAR(64) NOT NULL,
    etag VARCHAR(512),
    delivered_revision BIGINT,
    write_started BOOLEAN NOT NULL DEFAULT FALSE,
    state VARCHAR(24) NOT NULL CHECK(state IN ('RUNNING','SYNCED','ERROR','CONFLICT','BLOCKED','NEEDS_REVIEW')),
    error_code VARCHAR(80),
    attempt_id UUID NOT NULL,
    lease_until TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(event_id,target_user_id,destination_key),
    FOREIGN KEY(event_id,space_id) REFERENCES household_calendar_event(id,space_id) ON DELETE CASCADE,
    FOREIGN KEY(grant_id,space_id,target_user_id) REFERENCES household_calendar_destination(id,space_id,user_id),
    FOREIGN KEY(target_user_id,space_id) REFERENCES user_account(id,space_id)
);
CREATE INDEX household_delivery_event_idx ON household_calendar_delivery(space_id,event_id);
