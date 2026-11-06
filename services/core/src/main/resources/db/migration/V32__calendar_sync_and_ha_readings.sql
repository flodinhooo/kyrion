ALTER TABLE local_calendar_event
    ADD COLUMN sync_actor_id UUID REFERENCES user_account(id),
    ADD COLUMN google_etag TEXT,
    ADD COLUMN sync_status VARCHAR(24) NOT NULL DEFAULT 'local',
    ADD COLUMN sync_error VARCHAR(80),
    ADD COLUMN revision BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN pending_deletion BOOLEAN NOT NULL DEFAULT FALSE;

-- Legacy flags never performed exports. Preserve those flags, but require an
-- explicit calendar selection before creating any external event.
UPDATE local_calendar_event SET sync_status='configuration_required'
WHERE sync_to_google=TRUE;

ALTER TABLE home_assistant_device
    ADD COLUMN brightness INTEGER,
    ADD COLUMN hue DOUBLE PRECISION,
    ADD COLUMN saturation DOUBLE PRECISION;
