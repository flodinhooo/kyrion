"""Strict scheduled-backup consent and UTC slots; no OS effects."""

from __future__ import annotations

import datetime as dt
import re
import uuid

from backup_store import validate_binding


def validate(value: dict) -> None:
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "formatVersion",
            "revision",
            "enabled",
            "workerFile",
            "utcDays",
            "startMinute",
            "durationMinutes",
            "keep",
            "store",
            "keySha256",
        }
        or type(value.get("formatVersion")) is not int
        or value["formatVersion"] != 1
        or type(value.get("enabled")) is not bool
        or not isinstance(value.get("workerFile"), str)
        or not re.fullmatch(r"maintenance-[a-f0-9]{32}(?:\.exe)?", value["workerFile"])
        or not isinstance(value.get("utcDays"), list)
        or not 1 <= len(value["utcDays"]) <= 7
        or any(type(day) is not int or not 1 <= day <= 7 for day in value["utcDays"])
        or len(set(value["utcDays"])) != len(value["utcDays"])
        or type(value.get("startMinute")) is not int
        or not 0 <= value["startMinute"] < 1440
        or type(value.get("durationMinutes")) is not int
        or not 30 <= value["durationMinutes"] <= 1440
        or type(value.get("keep")) is not int
        or not 1 <= value["keep"] <= 90
        or not isinstance(value.get("keySha256"), str)
        or not re.fullmatch(r"[a-f0-9]{64}", value["keySha256"])
    ):
        raise ValueError("E_BACKUP_POLICY")
    try:
        if str(uuid.UUID(value["revision"])) != value["revision"]:
            raise ValueError()
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ValueError("E_BACKUP_POLICY") from None
    validate_binding(value["store"])


def slot(value: dict, instant: dt.datetime | None = None) -> str | None:
    validate(value)
    instant = instant or dt.datetime.now(dt.timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("E_BACKUP_TIME")
    instant = instant.astimezone(dt.timezone.utc)
    for offset in (0, 1):
        day = instant.date() - dt.timedelta(days=offset)
        start = dt.datetime.combine(day, dt.time(), dt.timezone.utc) + dt.timedelta(
            minutes=value["startMinute"]
        )
        if day.isoweekday() in value[
            "utcDays"
        ] and start <= instant < start + dt.timedelta(minutes=value["durationMinutes"]):
            return start.isoformat()
    return None
