-- No existing email or domain is assumed verified. HOME behavior remains unchanged.
CREATE TABLE installation_identity (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    id UUID NOT NULL UNIQUE DEFAULT gen_random_uuid()
);
INSERT INTO installation_identity(singleton) VALUES(TRUE);
ALTER TABLE user_account ADD CONSTRAINT account_space_identity_unique UNIQUE(id,space_id);

CREATE TABLE business_identity_policy (
    space_id UUID PRIMARY KEY REFERENCES kyrion_space(id) ON DELETE CASCADE,
    mode VARCHAR(10) NOT NULL DEFAULT 'OFF' CHECK(mode IN ('OFF','STRICT')),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE business_domain (
    space_id UUID NOT NULL REFERENCES kyrion_space(id) ON DELETE CASCADE,
    domain VARCHAR(253) NOT NULL,
    allowed BOOLEAN NOT NULL DEFAULT FALSE,
    challenge_hash CHAR(64) NOT NULL,
    challenge_expires_at TIMESTAMPTZ NOT NULL,
    verified_at TIMESTAMPTZ,
    verified_until TIMESTAMPTZ,
    PRIMARY KEY(space_id,domain)
);
CREATE TABLE account_email_identity (
    user_id UUID PRIMARY KEY,
    space_id UUID NOT NULL,
    email VARCHAR(254),
    proof_method VARCHAR(20) CHECK(proof_method IN ('SMTP','LOCAL_ATTESTATION')),
    verified_at TIMESTAMPTZ,
    pending_email VARCHAR(254),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id,space_id) REFERENCES user_account(id,space_id) ON DELETE CASCADE,
    CHECK ((email IS NULL AND proof_method IS NULL AND verified_at IS NULL) OR
           (email IS NOT NULL AND proof_method IS NOT NULL AND verified_at IS NOT NULL))
);
CREATE TABLE business_email_challenge (
    token_hash CHAR(64) PRIMARY KEY,
    space_id UUID NOT NULL REFERENCES kyrion_space(id) ON DELETE CASCADE,
    user_id UUID,
    invitation_hash CHAR(64) REFERENCES registration_invitation(token_hash) ON DELETE CASCADE,
    email VARCHAR(254) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    CHECK ((user_id IS NULL) <> (invitation_hash IS NULL)),
    FOREIGN KEY(user_id,space_id) REFERENCES user_account(id,space_id) ON DELETE CASCADE
);
CREATE INDEX email_challenge_user_idx ON business_email_challenge(user_id,created_at);
CREATE INDEX email_challenge_invitation_idx ON business_email_challenge(invitation_hash,created_at);
ALTER TABLE registration_invitation ADD COLUMN email_constraint VARCHAR(254);
ALTER TABLE registration_invitation ADD CONSTRAINT invitation_space_token_unique UNIQUE(token_hash,workspace_owner_id);
ALTER TABLE business_email_challenge ADD CONSTRAINT email_invitation_space_fk FOREIGN KEY(invitation_hash,space_id)
    REFERENCES registration_invitation(token_hash,workspace_owner_id) ON DELETE CASCADE;

CREATE TABLE space_recovery_material (
    space_id UUID PRIMARY KEY REFERENCES kyrion_space(id) ON DELETE CASCADE,
    owner_id UUID NOT NULL,
    host_key_hash CHAR(64) NOT NULL,
    code_hash CHAR(64),
    code_expires_at TIMESTAMPTZ NOT NULL,
    generation BIGINT NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(owner_id,space_id) REFERENCES user_account(id,space_id) ON DELETE CASCADE
);
CREATE TABLE space_recovery_session (
    token_hash CHAR(64) PRIMARY KEY,
    space_id UUID NOT NULL REFERENCES space_recovery_material(space_id) ON DELETE CASCADE,
    generation BIGINT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ
);

-- Nested IDs must agree on ownership even when a worker bypasses an HTTP handler.
DO $$ BEGIN
    IF EXISTS(SELECT 1 FROM integration_connection c JOIN owner_room r ON r.id=c.room_id WHERE c.owner_id<>r.owner_id)
       OR EXISTS(SELECT 1 FROM gateway_command c JOIN gateway_node n ON n.id=c.node_id WHERE c.owner_id<>n.owner_id)
       OR EXISTS(SELECT 1 FROM voice_dialogue_session s JOIN voice_satellite v ON v.id=s.satellite_id WHERE s.owner_id<>v.owner_id)
       OR EXISTS(SELECT 1 FROM home_assistant_device h JOIN integration_connection c ON c.id=h.connection_id WHERE h.owner_id<>c.owner_id) THEN
        RAISE EXCEPTION 'TENANT_NESTED_OWNERSHIP_INVALID: reconcile mismatched rooms, gateway commands, voice sessions or imported devices on a restored copy before retrying';
    END IF;
END $$;
ALTER TABLE owner_room ADD CONSTRAINT room_owner_unique UNIQUE(id,owner_id);
ALTER TABLE integration_connection ADD CONSTRAINT connection_owner_unique UNIQUE(id,owner_id);
ALTER TABLE integration_connection ADD CONSTRAINT connection_room_owner_fk FOREIGN KEY(room_id,owner_id)
    REFERENCES owner_room(id,owner_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE gateway_node ADD CONSTRAINT gateway_owner_unique UNIQUE(id,owner_id);
ALTER TABLE gateway_command ADD CONSTRAINT command_node_owner_fk FOREIGN KEY(node_id,owner_id)
    REFERENCES gateway_node(id,owner_id) ON DELETE CASCADE;
ALTER TABLE voice_satellite ADD CONSTRAINT satellite_owner_unique UNIQUE(id,owner_id);
ALTER TABLE voice_dialogue_session ADD CONSTRAINT voice_session_satellite_owner_fk FOREIGN KEY(satellite_id,owner_id)
    REFERENCES voice_satellite(id,owner_id) ON DELETE CASCADE;
ALTER TABLE home_assistant_device ADD CONSTRAINT imported_device_owner_fk FOREIGN KEY(connection_id,owner_id)
    REFERENCES integration_connection(id,owner_id) ON DELETE CASCADE;
