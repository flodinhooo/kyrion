-- Preserve historical owner keys, ciphertext and role permission sets.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM user_account) AND
       (SELECT count(*) FROM user_account WHERE workspace_owner_id IS NULL AND enabled) <> 1 THEN
        RAISE EXCEPTION 'SPACES_MIGRATION_AMBIGUOUS_OWNER: require exactly one enabled root workspace owner; restore a backup and reconcile ownership locally before retrying';
    END IF;
    IF (SELECT count(*) FROM user_account WHERE workspace_owner_id IS NULL) > 1 OR
       EXISTS (SELECT 1 FROM user_account u JOIN user_account p ON p.id=u.workspace_owner_id WHERE p.workspace_owner_id IS NOT NULL) THEN
        RAISE EXCEPTION 'SPACES_MIGRATION_AMBIGUOUS_WORKSPACE: multiple or nested workspace roots require explicit local reconciliation';
    END IF;
    IF EXISTS (SELECT 1 FROM rbac_user_role ur JOIN user_account u ON u.id=ur.user_id
               JOIN rbac_role r ON r.id=ur.role_id
               WHERE r.installation_owner_id<>COALESCE(u.workspace_owner_id,u.id)) THEN
        RAISE EXCEPTION 'SPACES_MIGRATION_CROSS_SPACE_ROLE: reconcile invalid role assignments before retrying';
    END IF;
    IF EXISTS (SELECT 1 FROM registration_invitation i JOIN user_account u ON u.id=i.created_by
               WHERE COALESCE(u.workspace_owner_id,u.id)<>i.workspace_owner_id) THEN
        RAISE EXCEPTION 'SPACES_MIGRATION_CROSS_SPACE_INVITATION: revoke and reconcile invalid legacy invitations before retrying';
    END IF;
END $$;

CREATE TABLE kyrion_space (
    id UUID PRIMARY KEY REFERENCES user_account(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    type VARCHAR(8) NOT NULL DEFAULT 'HOME' CHECK (type IN ('HOME','BUSINESS')),
    name VARCHAR(120) NOT NULL DEFAULT 'Kyrion' CHECK (length(trim(name)) BETWEEN 1 AND 120),
    status VARCHAR(10) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','SUSPENDED')),
    default_role_key VARCHAR(80) NOT NULL DEFAULT 'USER' CHECK (default_role_key <> 'OWNER'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO kyrion_space(id, created_at)
SELECT id,created_at FROM user_account WHERE workspace_owner_id IS NULL;

ALTER TABLE user_account ADD COLUMN space_id UUID GENERATED ALWAYS AS (COALESCE(workspace_owner_id,id)) STORED;
ALTER TABLE user_account ADD CONSTRAINT user_account_space_fk FOREIGN KEY(space_id) REFERENCES kyrion_space(id) DEFERRABLE INITIALLY DEFERRED;
CREATE INDEX user_account_space_idx ON user_account(space_id);
ALTER TABLE rbac_role ADD CONSTRAINT rbac_role_space_fk FOREIGN KEY(installation_owner_id) REFERENCES kyrion_space(id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE registration_invitation ADD CONSTRAINT registration_invitation_space_fk FOREIGN KEY(workspace_owner_id) REFERENCES kyrion_space(id);

-- Root insertion is already serialized by the durable first-owner bootstrap.
CREATE FUNCTION initialize_account_space() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.workspace_owner_id IS NULL THEN
        INSERT INTO kyrion_space(id,created_at) VALUES(NEW.id,NEW.created_at);
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER initialize_account_space AFTER INSERT ON user_account
FOR EACH ROW EXECUTE FUNCTION initialize_account_space();

CREATE FUNCTION protect_account_space() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.workspace_owner_id IS DISTINCT FROM OLD.workspace_owner_id OR NEW.id<>OLD.id THEN
        RAISE EXCEPTION 'SPACE_MEMBERSHIP_IMMUTABLE';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER protect_account_space BEFORE UPDATE ON user_account
FOR EACH ROW EXECUTE FUNCTION protect_account_space();

CREATE FUNCTION validate_space_role_assignment() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM user_account u JOIN rbac_role r ON r.installation_owner_id=u.space_id
                   WHERE u.id=NEW.user_id AND r.id=NEW.role_id) THEN
        RAISE EXCEPTION 'CROSS_SPACE_ROLE_ASSIGNMENT';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER validate_space_role_assignment BEFORE INSERT OR UPDATE ON rbac_user_role
FOR EACH ROW EXECUTE FUNCTION validate_space_role_assignment();

ALTER TABLE registration_invitation
    ADD COLUMN id UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    ADD COLUMN created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN revoked_at TIMESTAMPTZ,
    ADD COLUMN role_id UUID REFERENCES rbac_role(id),
    ADD COLUMN max_uses INTEGER NOT NULL DEFAULT 1 CHECK (max_uses BETWEEN 1 AND 20),
    ADD COLUMN use_count INTEGER NOT NULL DEFAULT 0 CHECK (use_count>=0 AND use_count<=max_uses);
UPDATE registration_invitation SET use_count=1 WHERE redeemed_at IS NOT NULL;
CREATE INDEX registration_invitation_space_idx ON registration_invitation(workspace_owner_id,created_at);

CREATE FUNCTION validate_space_invitation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM user_account WHERE id=NEW.created_by AND space_id=NEW.workspace_owner_id)
       OR (NEW.role_id IS NOT NULL AND NOT EXISTS (
           SELECT 1 FROM rbac_role WHERE id=NEW.role_id AND installation_owner_id=NEW.workspace_owner_id AND role_key<>'OWNER')) THEN
        RAISE EXCEPTION 'INVALID_SPACE_INVITATION';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER validate_space_invitation BEFORE INSERT OR UPDATE ON registration_invitation
FOR EACH ROW EXECUTE FUNCTION validate_space_invitation();
