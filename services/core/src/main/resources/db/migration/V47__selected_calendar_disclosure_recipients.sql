ALTER TABLE personal_calendar_disclosure
  ADD CONSTRAINT calendar_disclosure_space_unique UNIQUE (id, space_id);

CREATE TABLE personal_calendar_disclosure_recipient
(
  disclosure_id UUID NOT NULL,
  space_id      UUID NOT NULL,
  recipient_id  UUID NOT NULL,
  PRIMARY KEY (disclosure_id, recipient_id),
  FOREIGN KEY (disclosure_id, space_id) REFERENCES personal_calendar_disclosure (id, space_id) ON DELETE CASCADE,
  FOREIGN KEY (recipient_id, space_id) REFERENCES user_account (id, space_id) ON DELETE CASCADE
);

-- Preserve existing audiences as a fixed snapshot, never future household members.
-- Read permissions and current membership are additionally checked at request time.
INSERT INTO personal_calendar_disclosure_recipient(disclosure_id, space_id, recipient_id)
SELECT d.id, d.space_id, u.id
FROM personal_calendar_disclosure d
       JOIN user_account u ON u.space_id = d.space_id AND u.enabled AND u.id <> d.user_id
WHERE d.visibility <> 'PRIVATE';

CREATE INDEX calendar_disclosure_recipient_account_idx
  ON personal_calendar_disclosure_recipient (space_id, recipient_id);
