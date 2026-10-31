ALTER TABLE ai_usage_attempt
  ADD COLUMN reserved_tokens BIGINT CHECK (reserved_tokens >= 0),
  ADD COLUMN reserved_cost NUMERIC(24, 8),
  ADD COLUMN input_price NUMERIC CHECK (input_price >= 0),
  ADD COLUMN output_price NUMERIC CHECK (output_price >= 0),
  ADD COLUMN reported_total_tokens BIGINT,
  ADD COLUMN invoked_at TIMESTAMPTZ;

-- Legacy pending attempts may already have reached a provider. Never replay or
-- refund them merely because the older implementation lacked an invocation mark.
UPDATE ai_usage_attempt SET state='uncertain', error_code='LEGACY_REVIEW_REQUIRED'
WHERE state='pending';
UPDATE ai_usage_attempt SET reserved_tokens=charged_tokens, reserved_cost=estimated_cost;
ALTER TABLE ai_usage_attempt ALTER COLUMN reserved_tokens SET NOT NULL;
CREATE INDEX ai_usage_unresolved_actor_idx ON ai_usage_attempt(actor_id, created_at)
WHERE state IN ('pending','invoked','uncertain','estimated')
   OR (state!='rejected' AND (estimated_cost IS NULL OR currency IS NULL));
