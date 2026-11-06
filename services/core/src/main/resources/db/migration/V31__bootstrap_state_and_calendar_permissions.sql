-- Additive only: existing accounts and role grants remain unchanged.
CREATE TABLE installation_bootstrap_state (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    initialized BOOLEAN NOT NULL
);
INSERT INTO installation_bootstrap_state(singleton, initialized)
SELECT TRUE, EXISTS(SELECT 1 FROM user_account);

INSERT INTO rbac_permission(permission_key, resource, operation) VALUES
    ('calendar:read', 'calendar', 'READ'),
    ('calendar:create', 'calendar', 'CREATE'),
    ('calendar:update', 'calendar', 'UPDATE'),
    ('calendar:delete', 'calendar', 'DELETE')
ON CONFLICT DO NOTHING;
