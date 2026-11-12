CREATE TABLE central_account_profile
(
  user_id               UUID          NOT NULL REFERENCES user_account (id) ON DELETE CASCADE,
  issuer                VARCHAR(2048) NOT NULL,
  subject               VARCHAR(255)  NOT NULL,
  email                 VARCHAR(254),
  display_name          VARCHAR(160),
  verified_at           TIMESTAMPTZ   NOT NULL,
  directory_id          UUID,
  credential_ciphertext BYTEA,
  credential_nonce      BYTEA,
  last_attempt_at       TIMESTAMPTZ,
  synchronized_at       TIMESTAMPTZ,
  PRIMARY KEY (user_id, issuer, subject),
  CHECK ((directory_id IS NULL AND credential_ciphertext IS NULL AND credential_nonce IS NULL)
    OR (directory_id IS NOT NULL AND credential_ciphertext IS NOT NULL AND credential_nonce IS NOT NULL))
);
