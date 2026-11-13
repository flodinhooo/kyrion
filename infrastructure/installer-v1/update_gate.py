"""Fail-closed startup fence for the existing installer/service entrypoints."""

from __future__ import annotations

FINAL = frozenset({"complete", "recovered"})
ACTIVATING = frozenset({"activating", "reactivating"})
MAINTENANCE = frozenset({"migrating", "checking", "recovery-checking"})


def fenced(state: dict) -> bool:
    transaction = state.get("updateTransaction")
    return transaction is not None and (
        not isinstance(transaction, dict) or transaction.get("phase") not in FINAL
    )


def role_mode(state: dict, role: str) -> bool:
    """Return maintenance mode only for the explicitly journaled Core start."""
    if not fenced(state):
        return False
    phase = state.get("updateTransaction", {}).get("phase")
    if phase in ACTIVATING:
        return False
    if role == "core" and phase in MAINTENANCE:
        return True
    raise ValueError("E_UPDATE_IN_PROGRESS")
