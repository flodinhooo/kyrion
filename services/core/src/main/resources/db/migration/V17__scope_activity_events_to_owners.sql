ALTER TABLE activity_event
    ADD COLUMN owner_id UUID REFERENCES user_account (id) ON DELETE CASCADE;

UPDATE activity_event
SET owner_id = actor_id::UUID
WHERE actor_type = 'USER'
  AND actor_id ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
  AND EXISTS (SELECT 1 FROM user_account WHERE id = actor_id::UUID);

CREATE INDEX activity_event_owner_occurred_at_idx
    ON activity_event (owner_id, occurred_at DESC);
