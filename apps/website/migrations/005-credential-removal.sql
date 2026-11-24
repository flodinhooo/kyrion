-- Dedicated website database only. Pending credential removal stays server-side.
ALTER TABLE website_oidc_flow ADD COLUMN IF NOT EXISTS credential_id text;
ALTER TABLE website_account_event ADD COLUMN IF NOT EXISTS credential_id uuid;
ALTER TABLE website_account_event DROP CONSTRAINT IF EXISTS website_account_event_event_code_check;
ALTER TABLE website_account_event ADD CONSTRAINT website_account_event_event_code_check CHECK (event_code IN ('SESSION_CREATED','SESSION_REVOKED','INSTALLATION_LINKED','INSTALLATION_UNLINKED','CREDENTIAL_REMOVAL_STARTED','CREDENTIAL_REMOVAL_RETURNED','CREDENTIAL_REMOVAL_ABSENT','CREDENTIAL_REMOVAL_RETAINED'));
