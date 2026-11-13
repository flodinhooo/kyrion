# ADR 0065: Bound automatic update execution attempts

Status: Accepted

An approved automatic transaction can resume after interruption outside its start
window, but a broken migration or unavailable component must not be retried
indefinitely by the hourly/boot worker. Allow at most three automatic execution
attempts per transaction, including its initial execution. Reserve each attempt
in the protected journal before any further transaction side effects. A process
death consumes the reserved attempt. Locking, policy/trust validation and backend
locality checks still precede execution; unrelated update checks do not consume
execution attempts.

On exhaustion, preserve the startup fence, backups, retained runtime and original
approval. The worker records a stable actionable error and requires explicit
host-administrator continuation or recovery. Never rewind data automatically.
Manual continuation remains possible and does not erase the retry history.
A later new approved transaction receives its own budget.

For a compatible older pending automatic journal without the counter, count one
previous execution conservatively. Reject malformed/out-of-range counters rather
than treating them as zero. A new transaction with zero reservations can only be
in its initial `preparing` phase. Completed transactions are not charged again.

This changes neither account/Space authority nor release signing. It does not
establish OS scheduling or whole-host reboot acceptance. Existing process/Docker
transaction evidence remains separate from tests of this retry policy.
