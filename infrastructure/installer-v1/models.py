"""Reviewed data and conservative recommendations, never inference authority."""

from __future__ import annotations

import datetime
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from release_policy import PolicyError, parse, verify

GIB = 1024**3


def https_source(value: object) -> bool:
    if not isinstance(value, str) or len(value) > 500:
        return False
    try:
        url = urlsplit(value)
        return (
            url.scheme == "https"
            and bool(url.hostname)
            and url.username is None
            and url.password is None
            and url.port in {None, 443}
            and not url.fragment
        )
    except ValueError:
        return False


def validate_catalog(
    value: dict, minimum_sequence: int = 0, now: int | None = None
) -> dict:
    current = time.time() if now is None else now
    if (
        set(value)
        != {"formatVersion", "kind", "sequence", "reviewedAt", "expiresAt", "models"}
        or type(value["formatVersion"]) is not int
        or value["formatVersion"] != 1
        or value["kind"] != "model-catalog"
    ):
        raise PolicyError("E_MODEL_CATALOG")
    try:
        reviewed = datetime.date.fromisoformat(value["reviewedAt"])
    except (TypeError, ValueError, AttributeError):
        raise PolicyError("E_MODEL_CATALOG_DATE") from None
    if (
        type(value["expiresAt"]) is not int
        or value["expiresAt"] <= current
        or reviewed > datetime.datetime.fromtimestamp(current, datetime.UTC).date()
    ):
        raise PolicyError("E_MODEL_CATALOG_EXPIRED")
    if (
        type(value["sequence"]) is not int
        or value["sequence"] < max(1, minimum_sequence)
        or not isinstance(value["models"], list)
        or not 1 <= len(value["models"]) <= 100
    ):
        raise PolicyError("E_MODEL_CATALOG_SEQUENCE")
    identifiers = set()
    fields = {
        "id",
        "manifestSha256",
        "quantization",
        "downloadBytes",
        "memoryEstimateBytes",
        "estimateContextTokens",
        "architectures",
        "purposes",
        "languages",
        "license",
        "licenseUrl",
        "sourceUrl",
        "registryUrl",
    }
    for model in value["models"]:
        if not isinstance(model, dict) or set(model) != fields:
            raise PolicyError("E_MODEL_CATALOG_ENTRY")
        if (
            not isinstance(model["id"], str)
            or not re.fullmatch(
                r"[a-z0-9][a-z0-9_.-]{0,80}:[a-z0-9][a-z0-9_.-]{0,80}", model["id"]
            )
            or model["id"].endswith(":latest")
            or model["id"] in identifiers
        ):
            raise PolicyError("E_MODEL_CATALOG_ID")
        identifiers.add(model["id"])
        if (
            not isinstance(model["manifestSha256"], str)
            or not re.fullmatch(r"[a-f0-9]{64}", model["manifestSha256"])
            or not isinstance(model["quantization"], str)
            or not re.fullmatch(r"[A-Z0-9_]{1,30}", model["quantization"])
        ):
            raise PolicyError("E_MODEL_CATALOG_VARIANT")
        for key, maximum in (
            ("downloadBytes", 1024 * GIB),
            ("memoryEstimateBytes", 2048 * GIB),
            ("estimateContextTokens", 1024**2),
        ):
            if type(model[key]) is not int or not 1 <= model[key] <= maximum:
                raise PolicyError("E_MODEL_CATALOG_SIZE")
        for key, allowed in (
            ("architectures", {"amd64", "arm64"}),
            ("purposes", {"everyday", "smart-home", "coding"}),
            ("languages", {"de", "en"}),
        ):
            rows = model[key]
            if (
                not isinstance(rows, list)
                or not rows
                or any(not isinstance(row, str) or row not in allowed for row in rows)
                or len(rows) != len(set(rows))
            ):
                raise PolicyError("E_MODEL_CATALOG_REQUIREMENT")
        if (
            not isinstance(model["license"], str)
            or not re.fullmatch(r"[A-Za-z0-9.+-]{1,80}", model["license"])
            or not all(
                https_source(model[key])
                for key in ("licenseUrl", "sourceUrl", "registryUrl")
            )
        ):
            raise PolicyError("E_MODEL_CATALOG_SOURCE")
    return value


def load_catalog(
    envelope: bytes | None = None,
    trust: dict | None = None,
    minimum_sequence: int = 0,
    now: int | None = None,
) -> dict:
    if envelope is None:
        value = parse(Path(__file__).with_name("model-catalog.json").read_bytes())
    else:
        if trust is None:
            raise PolicyError("E_MODEL_TRUST_REQUIRED")
        value = verify(envelope, trust, "model-catalog", now)
    return validate_catalog(value, minimum_sequence, now)


@dataclass(frozen=True)
class Preferences:
    purpose: str
    languages: tuple[str, ...]
    priority: str
    concurrent_use: str
    memory_budget_bytes: int

    def validate(self) -> None:
        if (
            self.purpose not in {"everyday", "smart-home", "coding"}
            or self.priority not in {"speed", "quality", "resources"}
            or self.concurrent_use not in {"dedicated", "work", "gaming"}
            or not self.languages
            or any(language not in {"de", "en"} for language in self.languages)
            or type(self.memory_budget_bytes) is not int
            or not 0 < self.memory_budget_bytes <= 2048 * GIB
        ):
            raise ValueError("E_MODEL_PREFERENCES")


def recommend(catalog: dict, target: dict, preferences: Preferences) -> dict:
    preferences.validate()
    validate_catalog(catalog)
    memory, disk, cpus = (
        target.get("ramBytes"),
        target.get("freeBytes"),
        target.get("cpuCount"),
    )
    observation = {
        "architecture": target.get("architecture"),
        "cpuCount": cpus,
        "ramBytes": memory,
        "freeBytes": disk,
        "usableAcceleration": target.get("usableAcceleration"),
    }
    result = {
        "catalogSequence": catalog["sequence"],
        "reviewedAt": catalog["reviewedAt"],
        "target": observation,
        "estimates": True,
        "benchmarkMeasured": False,
        "recommended": None,
        "alternatives": [],
        "reason": None,
        "cloudEnabled": False,
        "downloadsStarted": False,
    }
    if target.get("architecture") not in {"amd64", "arm64"} or any(
        type(value) is not int or value <= 0 for value in (memory, disk, cpus)
    ):
        return {**result, "reason": "hardware_unknown"}
    # RAM and disk estimates deliberately retain OS/Core and parallel-use headroom.
    os_reserve = max(3 * GIB, memory // 5)
    core_reserve = 2 * GIB
    concurrent_reserve = {"dedicated": 0, "work": 2 * GIB, "gaming": 4 * GIB}[
        preferences.concurrent_use
    ]
    budget = max(
        0,
        min(
            preferences.memory_budget_bytes,
            memory - os_reserve - core_reserve - concurrent_reserve,
        ),
    )
    result.update(
        {
            "memoryBudgetBytes": budget,
            "reservedBytes": os_reserve + core_reserve + concurrent_reserve,
            "executionEstimate": "cpu-unbenchmarked",
        }
    )
    compatible = [
        model
        for model in catalog["models"]
        if target["architecture"] in model["architectures"]
        and preferences.purpose in model["purposes"]
        and set(preferences.languages) <= set(model["languages"])
        and model["memoryEstimateBytes"] <= budget
        and 2 * model["downloadBytes"] + GIB <= disk
        and cpus >= 2
    ]
    compatible.sort(
        key=lambda model: model["memoryEstimateBytes"],
        reverse=preferences.priority == "quality",
    )
    if not compatible:
        return {**result, "reason": "insufficient_resources"}
    return {**result, "recommended": compatible[0], "alternatives": compatible[1:]}


def guided_recommendation(
    target: dict,
    messages: dict[str, str],
    catalog: dict | Callable[[], dict] | None = None,
) -> dict | None:
    import json

    if input(messages["aiPlanNow"] + " [PLAN/skip]: ").strip() != "PLAN":
        return None
    if callable(catalog):
        catalog = catalog()
    purpose = input(messages["aiPurpose"] + " [everyday/smart-home/coding]: ").strip()
    languages = tuple(
        part.strip()
        for part in input(messages["aiLanguages"] + " [de,en]: ").split(",")
    )
    priority = input(messages["aiPriority"] + " [speed/quality/resources]: ").strip()
    concurrent = input(messages["aiConcurrent"] + " [dedicated/work/gaming]: ").strip()
    budget = input(messages["aiBudget"] + " [GiB]: ").strip()
    if not budget.isascii() or not budget.isdigit():
        raise ValueError("E_MODEL_PREFERENCES")
    preferences = Preferences(
        purpose, languages, priority, concurrent, int(budget) * GIB
    )
    result = recommend(
        catalog if catalog is not None else load_catalog(), target, preferences
    )
    print(messages["aiEstimates"])
    print(json.dumps(result, ensure_ascii=True, indent=2))
    if result["recommended"] is None:
        print(messages["aiAlternatives"])
    return result
