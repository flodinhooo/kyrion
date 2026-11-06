-- V42/V43 are reserved by concurrent Gateway/calendar work. No existing account changes.
CREATE TABLE central_identity_link (
    user_id UUID PRIMARY KEY REFERENCES user_account(id) ON DELETE CASCADE,
    issuer VARCHAR(2048) NOT NULL,
    subject VARCHAR(255) NOT NULL,
    linked_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT central_identity_unique UNIQUE (issuer, subject)
);

-- An opaque local session remains the only Core API credential. No OIDC tokens persist.
CREATE TABLE central_auth_session (
    session_id UUID PRIMARY KEY REFERENCES auth_session(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES central_identity_link(user_id) ON DELETE CASCADE
);
