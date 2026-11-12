-- Dedicated website DB only. Additive rollout; old sessions keep their expiry.
BEGIN;
ALTER TABLE website_session ADD COLUMN IF NOT EXISTS refresh_credential text;
ALTER TABLE website_session ADD COLUMN IF NOT EXISTS verified_until timestamptz;
GRANT UPDATE (refresh_credential, verified_until) ON website_session TO kyrion_website_app;
COMMIT;
