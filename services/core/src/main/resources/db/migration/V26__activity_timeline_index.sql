CREATE INDEX activity_owner_correlation_idx ON activity_event(owner_id, correlation_id, integrity_sequence);
ALTER TABLE gateway_command ADD COLUMN correlation_id UUID;
CREATE INDEX action_execution_owner_correlation_idx ON action_execution(owner_id, correlation_id);
