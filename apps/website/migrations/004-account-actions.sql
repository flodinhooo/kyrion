-- Dedicated website database only. Existing flows and sessions remain valid.
ALTER TABLE website_oidc_flow ADD COLUMN IF NOT EXISTS expected_subject text;
