CREATE TABLE rbac_role (
    id UUID PRIMARY KEY,
    installation_owner_id UUID NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
    role_key VARCHAR(80) NOT NULL,
    display_name VARCHAR(120) NOT NULL,
    system_role BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (installation_owner_id, role_key)
);

CREATE TABLE rbac_permission (
    permission_key VARCHAR(120) PRIMARY KEY,
    resource VARCHAR(80) NOT NULL,
    operation VARCHAR(20) NOT NULL
);

CREATE TABLE rbac_role_permission (
    role_id UUID NOT NULL REFERENCES rbac_role(id) ON DELETE CASCADE,
    permission_key VARCHAR(120) NOT NULL REFERENCES rbac_permission(permission_key) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_key)
);

CREATE TABLE rbac_user_role (
    user_id UUID NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES rbac_role(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

CREATE INDEX rbac_user_role_user_idx ON rbac_user_role(user_id);
CREATE INDEX rbac_role_permission_role_idx ON rbac_role_permission(role_id);

INSERT INTO rbac_permission(permission_key, resource, operation) VALUES
 ('users:read','users','READ'), ('users:create','users','CREATE'), ('users:update','users','UPDATE'), ('users:delete','users','DELETE'),
 ('roles:read','roles','READ'), ('roles:create','roles','CREATE'), ('roles:update','roles','UPDATE'), ('roles:delete','roles','DELETE'),
 ('permissions:read','permissions','READ'), ('invitations:create','invitations','CREATE'),
 ('rooms:read','rooms','READ'), ('rooms:create','rooms','CREATE'), ('rooms:update','rooms','UPDATE'), ('rooms:delete','rooms','DELETE'),
 ('devices:read','devices','READ'), ('devices:create','devices','CREATE'), ('devices:update','devices','UPDATE'), ('devices:delete','devices','DELETE'), ('devices:execute','devices','EXECUTE'),
 ('integrations:read','integrations','READ'), ('integrations:create','integrations','CREATE'), ('integrations:update','integrations','UPDATE'), ('integrations:delete','integrations','DELETE'), ('integrations:execute','integrations','EXECUTE'),
 ('gateways:read','gateways','READ'), ('gateways:create','gateways','CREATE'), ('gateways:update','gateways','UPDATE'), ('gateways:delete','gateways','DELETE'), ('gateways:execute','gateways','EXECUTE'),
 ('voice_satellites:read','voice_satellites','READ'), ('voice_satellites:create','voice_satellites','CREATE'), ('voice_satellites:update','voice_satellites','UPDATE'), ('voice_satellites:delete','voice_satellites','DELETE'), ('voice_satellites:execute','voice_satellites','EXECUTE'),
 ('automations:read','automations','READ'), ('automations:create','automations','CREATE'), ('automations:update','automations','UPDATE'), ('automations:delete','automations','DELETE'), ('automations:execute','automations','EXECUTE'),
 ('conversations:read','conversations','READ'), ('conversations:create','conversations','CREATE'), ('conversations:update','conversations','UPDATE'), ('conversations:delete','conversations','DELETE'),
 ('personal_memories:read','personal_memories','READ'), ('personal_memories:create','personal_memories','CREATE'), ('personal_memories:update','personal_memories','UPDATE'), ('personal_memories:delete','personal_memories','DELETE'),
 ('activity_log:read','activity_log','READ'), ('backups:read','backups','READ'), ('backups:create','backups','CREATE'), ('backups:delete','backups','DELETE'),
 ('system_settings:read','system_settings','READ'), ('system_settings:update','system_settings','UPDATE')
ON CONFLICT DO NOTHING;

INSERT INTO rbac_role(id, installation_owner_id, role_key, display_name, system_role)
SELECT gen_random_uuid(), COALESCE(u.workspace_owner_id, u.id), role_key, role_key, TRUE FROM user_account u
CROSS JOIN (VALUES ('OWNER'), ('ADMIN'), ('USER'), ('VIEWER')) roles(role_key)
ON CONFLICT DO NOTHING;

INSERT INTO rbac_role_permission(role_id, permission_key)
SELECT r.id, p.permission_key FROM rbac_role r CROSS JOIN rbac_permission p WHERE r.role_key = 'OWNER'
ON CONFLICT DO NOTHING;
INSERT INTO rbac_role_permission(role_id, permission_key)
SELECT r.id, p.permission_key FROM rbac_role r JOIN rbac_permission p ON p.permission_key IN (
 'users:read','users:create','users:update','users:delete','roles:read','roles:create','roles:update','roles:delete','permissions:read','invitations:create',
 'rooms:read','rooms:create','rooms:update','rooms:delete','devices:read','devices:create','devices:update','devices:delete','devices:execute',
 'integrations:read','integrations:create','integrations:update','integrations:delete','integrations:execute','gateways:read','gateways:create','gateways:update','gateways:delete','gateways:execute',
 'voice_satellites:read','voice_satellites:create','voice_satellites:update','voice_satellites:delete','voice_satellites:execute','automations:read','automations:create','automations:update','automations:delete','automations:execute',
 'activity_log:read','backups:read','backups:create','backups:delete','system_settings:read','system_settings:update') WHERE r.role_key='ADMIN' ON CONFLICT DO NOTHING;
INSERT INTO rbac_role_permission(role_id, permission_key)
SELECT r.id, p.permission_key FROM rbac_role r JOIN rbac_permission p ON p.permission_key IN ('rooms:read','rooms:create','rooms:update','rooms:delete','devices:read','devices:execute','automations:read','automations:create','automations:update','automations:delete','automations:execute','conversations:read','conversations:create','conversations:update','conversations:delete','personal_memories:read','personal_memories:create','personal_memories:update','personal_memories:delete','integrations:read','integrations:execute') WHERE r.role_key='USER' ON CONFLICT DO NOTHING;
INSERT INTO rbac_role_permission(role_id, permission_key)
SELECT r.id, p.permission_key FROM rbac_role r JOIN rbac_permission p ON p.operation='READ' AND p.resource NOT IN ('users','roles','permissions','invitations','backups','system_settings','activity_log') WHERE r.role_key='VIEWER' ON CONFLICT DO NOTHING;
INSERT INTO rbac_user_role(user_id, role_id)
SELECT u.id, r.id FROM user_account u JOIN rbac_role r ON r.installation_owner_id=COALESCE(u.workspace_owner_id, u.id) AND r.role_key=CASE WHEN u.workspace_owner_id IS NULL THEN 'OWNER' ELSE 'USER' END
ON CONFLICT DO NOTHING;
