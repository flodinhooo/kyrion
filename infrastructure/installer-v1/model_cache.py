"""Authenticated, restart-safe catalog refresh in the existing install journal."""

from __future__ import annotations

import base64
import copy
import hashlib
import time
from pathlib import Path

from models import load_catalog
from release_policy import PolicyError, fetch_document, parse, validate_trust

LIMIT = 256 * 1024


def cached_catalog(installation) -> dict:
    state = installation.state.get("modelCatalog")
    if state is None:
        return load_catalog()
    if (
        not isinstance(state, dict)
        or set(state) != {"sequence", "envelope", "sha256", "trust", "checkedAt"}
        or type(state["sequence"]) is not int
        or state["sequence"] < 1
        or not isinstance(state["envelope"], str)
        or len(state["envelope"]) > 4 * LIMIT // 3 + 4
        or type(state["checkedAt"]) is not int
    ):
        raise PolicyError("E_MODEL_CACHE")
    try:
        envelope = base64.b64decode(state["envelope"], validate=True)
    except ValueError:
        raise PolicyError("E_MODEL_CACHE") from None
    if len(envelope) > LIMIT or hashlib.sha256(envelope).hexdigest() != state["sha256"]:
        raise PolicyError("E_MODEL_CACHE")
    return load_catalog(envelope, state["trust"], state["sequence"])


def refresh_catalog(installation, feed: str, trust: dict) -> dict:
    validate_trust(trust)
    # Even an expired previous catalog still establishes the persisted sequence
    # floor. Never erase it or silently fall back to older bundled data.
    previous = installation.state.get("modelCatalog")
    if previous is not None and (
        not isinstance(previous, dict)
        or type(previous.get("sequence")) is not int
        or previous["sequence"] < 1
    ):
        raise PolicyError("E_MODEL_CACHE")
    if previous:
        validate_trust(previous["trust"])
        if trust["epoch"] < previous["trust"]["epoch"] or (
            trust["epoch"] == previous["trust"]["epoch"] and trust != previous["trust"]
        ):
            raise PolicyError("E_MODEL_TRUST_ROLLBACK")
    raw = fetch_document(feed)
    if len(raw) > LIMIT:
        raise PolicyError("E_MODEL_CACHE_SIZE")
    bundled = parse(Path(__file__).with_name("model-catalog.json").read_bytes())[
        "sequence"
    ]
    if type(bundled) is not int or bundled < 1:
        raise PolicyError("E_MODEL_CACHE")
    floor = max(bundled, previous["sequence"] if previous else 0)
    catalog = load_catalog(raw, trust, floor)
    digest = hashlib.sha256(raw).hexdigest()
    if (
        previous
        and catalog["sequence"] == previous["sequence"]
        and digest != previous.get("sha256")
    ):
        # Compare signed payloads: renewed signatures/whitespace may change the
        # envelope without changing an immutable catalog sequence.
        old = parse(base64.b64decode(previous["envelope"], validate=True))
        new = parse(raw)
        if base64.b64decode(old["payload"], validate=True) != base64.b64decode(
            new["payload"], validate=True
        ):
            raise PolicyError("E_MODEL_CATALOG_EQUIVOCATION")
    state = {
        "sequence": catalog["sequence"],
        "envelope": base64.b64encode(raw).decode("ascii"),
        "sha256": digest,
        "trust": copy.deepcopy(trust),
        "checkedAt": int(time.time()),
    }
    # One atomic existing journal write publishes bytes, trust and high-water
    # mark together. A failed save must not leave process state looking updated.
    installation.state["modelCatalog"] = state
    try:
        installation.save()
    except BaseException:
        if previous is None:
            installation.state.pop("modelCatalog", None)
        else:
            installation.state["modelCatalog"] = previous
        raise
    return {
        "sequence": catalog["sequence"],
        "models": len(catalog["models"]),
        "signatureVerified": True,
        "downloadsStarted": False,
    }
