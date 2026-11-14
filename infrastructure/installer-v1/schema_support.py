"""Explicit reviewed Core schemas; signed releases cannot extend this set."""

CURRENT_CORE_SCHEMA = 50
SUPPORTED_CORE_SCHEMAS = frozenset({49, 50})


def restore_capability(value: object) -> int:
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "formatVersion",
            "coreSchema",
            "coreOwnedDisposition",
            "recoveryKeyTransfer",
        }
        or type(value.get("formatVersion")) is not int
        or value["formatVersion"] != 1
        or type(value.get("coreSchema")) is not int
        or value["coreSchema"] not in SUPPORTED_CORE_SCHEMAS
        or value.get("coreOwnedDisposition") is not True
        or value.get("recoveryKeyTransfer") is not True
    ):
        raise ValueError("E_RESTORE_CORE_UPGRADE_REQUIRED")
    return value["coreSchema"]
