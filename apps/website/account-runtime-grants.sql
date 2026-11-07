-- Dedicated CENTRAL website database only, after account-schema.sql.
-- Create kyrion_website_app separately with an independent private password.
-- Never use an installation/provider database or a provider-administrator role.
BEGIN;
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kyrion_website_app'
        AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)
    ) OR pg_has_role('kyrion_website_app', current_user, 'MEMBER') THEN
        RAISE EXCEPTION 'Website runtime role must not have administrative privileges';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'neon_superuser') THEN
        IF pg_has_role('kyrion_website_app', 'neon_superuser', 'MEMBER') THEN
            RAISE EXCEPTION 'Website runtime role must not inherit provider administration';
        END IF;
    END IF;
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO kyrion_website_app', current_database());
END $$;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO kyrion_website_app;
REVOKE ALL ON website_account, website_oidc_flow, website_session,
    website_account_event FROM kyrion_website_app;
GRANT SELECT, INSERT, UPDATE ON website_account TO kyrion_website_app;
GRANT SELECT, INSERT, DELETE ON website_oidc_flow, website_session TO kyrion_website_app;
GRANT INSERT ON website_account_event TO kyrion_website_app;

DO $$
BEGIN
    IF has_schema_privilege('kyrion_website_app', 'public', 'CREATE')
       OR has_table_privilege('kyrion_website_app', 'website_account_event', 'DELETE') THEN
        RAISE EXCEPTION 'Website runtime effective privileges exceed policy';
    END IF;
END $$;
COMMIT;
