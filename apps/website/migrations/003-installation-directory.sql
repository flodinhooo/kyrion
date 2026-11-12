BEGIN;
ALTER TABLE website_oidc_flow
  ADD COLUMN IF NOT EXISTS destination text NOT NULL DEFAULT 'account';
CREATE TABLE IF NOT EXISTS website_installation_link
(
  id              uuid PRIMARY KEY     DEFAULT gen_random_uuid(),
  account_id      uuid        NOT NULL REFERENCES website_account (id) ON DELETE CASCADE,
  installation_id uuid        NOT NULL,
  local_user_id   uuid        NOT NULL,
  name            text        NOT NULL,
  space_type      text        NOT NULL CHECK (space_type IN ('HOME', 'BUSINESS')),
  local_username  text        NOT NULL,
  linked_at       timestamptz NOT NULL,
  confirmed_at    timestamptz NOT NULL DEFAULT now(),
  credential_hash text        NOT NULL,
  UNIQUE (account_id, installation_id, local_user_id)
);
GRANT SELECT, INSERT, UPDATE, DELETE ON website_installation_link TO kyrion_website_app;
ALTER TABLE website_account_event
  DROP CONSTRAINT IF EXISTS website_account_event_event_code_check;
ALTER TABLE website_account_event
  ADD CONSTRAINT website_account_event_event_code_check
    CHECK (event_code IN ('SESSION_CREATED', 'SESSION_REVOKED', 'INSTALLATION_LINKED', 'INSTALLATION_UNLINKED'));
COMMIT;
