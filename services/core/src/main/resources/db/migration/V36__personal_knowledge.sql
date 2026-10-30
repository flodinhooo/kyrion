CREATE TABLE knowledge_spaces
(
  id            UUID PRIMARY KEY,
  owner_type    VARCHAR(20)  NOT NULL DEFAULT 'PERSONAL' CHECK (owner_type = 'PERSONAL'),
  owner_user_id UUID         NOT NULL UNIQUE REFERENCES user_account (id),
  name          VARCHAR(120) NOT NULL,
  created_at    TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- Organization ownership is deliberately unavailable until canonical Spaces lands.
CREATE FUNCTION knowledge_immutable_owner() RETURNS trigger
  LANGUAGE plpgsql AS
$$
BEGIN
  IF NEW.owner_type <> OLD.owner_type OR NEW.owner_user_id <> OLD.owner_user_id THEN
    RAISE EXCEPTION 'knowledge ownership is immutable';
  END IF;
  RETURN NEW;
END
$$;
CREATE TRIGGER knowledge_owner_immutable
  BEFORE UPDATE
  ON knowledge_spaces
  FOR EACH ROW
EXECUTE FUNCTION knowledge_immutable_owner();

CREATE TABLE knowledge_documents
(
  id                  UUID PRIMARY KEY,
  space_id            UUID         NOT NULL REFERENCES knowledge_spaces (id),
  uploaded_by_user_id UUID         NOT NULL REFERENCES user_account (id),
  original_filename   VARCHAR(200) NOT NULL,
  media_type          VARCHAR(40)  NOT NULL CHECK (media_type IN ('application/pdf', 'text/plain')),
  storage_key         UUID         NOT NULL UNIQUE,
  byte_size           BIGINT       NOT NULL CHECK (byte_size > 0),
  content_sha256      CHAR(64)     NOT NULL,
  status              VARCHAR(20)  NOT NULL CHECK (status IN ('PENDING', 'PROCESSING', 'READY', 'FAILED', 'DELETING')),
  error_code          VARCHAR(80),
  ingestion_revision  INTEGER      NOT NULL DEFAULT 1 CHECK (ingestion_revision > 0),
  created_at          TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at          TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at          TIMESTAMPTZ
);
CREATE INDEX knowledge_documents_space_idx ON knowledge_documents (space_id, created_at DESC, id);
CREATE INDEX knowledge_documents_status_idx ON knowledge_documents (status, updated_at);

CREATE TABLE knowledge_chunks
(
  id                  UUID PRIMARY KEY,
  document_id         UUID         NOT NULL REFERENCES knowledge_documents (id) ON DELETE CASCADE,
  ingestion_revision  INTEGER      NOT NULL,
  chunk_index         INTEGER      NOT NULL,
  content             TEXT         NOT NULL,
  token_count         INTEGER      NOT NULL CHECK (token_count > 0),
  source_page         INTEGER,
  source_start_offset INTEGER      NOT NULL,
  source_end_offset   INTEGER      NOT NULL,
  embedding_model_id  VARCHAR(128) NOT NULL,
  embedding_dimension INTEGER      NOT NULL CHECK (embedding_dimension BETWEEN 1 AND 4096),
  embedding           REAL[]       NOT NULL,
  created_at          TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (document_id, ingestion_revision, chunk_index),
  CHECK (cardinality(embedding) = embedding_dimension AND array_ndims(embedding) = 1),
  CHECK (source_end_offset > source_start_offset)
);
CREATE INDEX knowledge_chunks_model_idx ON knowledge_chunks (embedding_model_id, embedding_dimension, document_id);

CREATE TABLE knowledge_ingestion_jobs
(
  id                 UUID PRIMARY KEY,
  document_id        UUID        NOT NULL UNIQUE REFERENCES knowledge_documents (id) ON DELETE CASCADE,
  requested_revision INTEGER     NOT NULL,
  status             VARCHAR(20) NOT NULL CHECK (status IN ('PENDING', 'PROCESSING', 'DONE', 'FAILED')),
  attempt_count      INTEGER     NOT NULL DEFAULT 0,
  next_attempt_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  lease_owner        UUID,
  lease_expires_at   TIMESTAMPTZ,
  error_code         VARCHAR(80),
  created_at         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX knowledge_jobs_schedule_idx ON knowledge_ingestion_jobs (status, next_attempt_at, lease_expires_at);

CREATE TABLE knowledge_answer_sources
(
  conversation_id UUID         NOT NULL REFERENCES conversation (id) ON DELETE CASCADE,
  user_id         UUID         NOT NULL REFERENCES user_account (id),
  message_id      UUID         NOT NULL,
  document_id     UUID         NOT NULL REFERENCES knowledge_documents (id) ON DELETE CASCADE,
  reference       VARCHAR(100) NOT NULL,
  source_page     INTEGER,
  start_offset    INTEGER      NOT NULL,
  end_offset      INTEGER      NOT NULL,
  PRIMARY KEY (conversation_id, message_id, reference)
);

INSERT INTO rbac_permission(permission_key, resource, operation)
VALUES ('knowledge:read', 'knowledge', 'READ'),
       ('knowledge:create', 'knowledge', 'CREATE'),
       ('knowledge:delete', 'knowledge', 'DELETE');
INSERT INTO rbac_role_permission(role_id, permission_key)
SELECT r.id, p.permission_key
FROM rbac_role r
       CROSS JOIN rbac_permission p
WHERE p.resource = 'knowledge'
  AND (r.role_key IN ('OWNER', 'USER', 'ADMIN') OR
       (r.role_key = 'VIEWER' AND p.operation = 'READ'))
ON CONFLICT DO NOTHING;
