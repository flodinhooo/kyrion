ALTER TABLE user_account
    ADD COLUMN workspace_owner_id UUID REFERENCES user_account (id);

CREATE INDEX user_account_workspace_owner_idx ON user_account (workspace_owner_id);

CREATE TABLE registration_invitation (
    token_hash CHAR(64) PRIMARY KEY,
    created_by UUID NOT NULL REFERENCES user_account (id),
    workspace_owner_id UUID NOT NULL REFERENCES user_account (id),
    expires_at TIMESTAMPTZ NOT NULL,
    redeemed_at TIMESTAMPTZ
);
