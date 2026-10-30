CREATE TABLE ai_user_preferences
(
  user_id    UUID PRIMARY KEY REFERENCES user_account (id) ON DELETE CASCADE,
  settings   JSONB       NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE ai_workspace_policy
(
  owner_id   UUID PRIMARY KEY REFERENCES user_account (id) ON DELETE CASCADE,
  settings   JSONB       NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE ai_usage_attempt
(
  id                     UUID PRIMARY KEY,
  actor_id               UUID         NOT NULL REFERENCES user_account (id) ON DELETE CASCADE,
  request_id             UUID         NOT NULL,
  attempt                INTEGER      NOT NULL CHECK (attempt >= 0),
  provider               VARCHAR(24)  NOT NULL,
  profile_id             VARCHAR(128) NOT NULL,
  model_id               VARCHAR(128) NOT NULL,
  period                 VARCHAR(7)   NOT NULL,
  charged_tokens         BIGINT       NOT NULL CHECK (charged_tokens >= 0),
  reported_input_tokens  BIGINT,
  reported_output_tokens BIGINT,
  estimated_cost         NUMERIC(24, 8),
  currency               VARCHAR(3),
  state                  VARCHAR(24)  NOT NULL DEFAULT 'pending',
  error_code             VARCHAR(80),
  created_at             TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
  settled_at             TIMESTAMPTZ,
  UNIQUE (actor_id, request_id, attempt)
);
CREATE INDEX ai_usage_actor_period_idx ON ai_usage_attempt (actor_id, period);
