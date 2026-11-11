#!/usr/bin/env python3
"""Local guided installer entrypoint. Public website has no setup state."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from bundle import authenticated_review
from host import inventory
from maintenance import run as run_maintenance
from models import guided_recommendation, load_catalog
from onboarding import guided_setup
from runtime import (
    Installation,
    image_plan,
    installation_lock,
    provision,
    validate_inputs,
)

ROOT = Path(__file__).resolve().parent


def main() -> int:
    if sys.version_info < (3, 12):
        print("E_PYTHON: Python 3.12 or newer is required", file=sys.stderr)
        return 2
    parser = argparse.ArgumentParser(description="Kyrion local guided installer")
    parser.add_argument(
        "--probe", action="store_true", help="Read-only target inventory, no install"
    )
    parser.add_argument("--bundle", type=Path, default=ROOT / "release")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--recommend-ai", action="store_true")
    actions.add_argument("--backup", type=Path)
    actions.add_argument("--verify-backup", type=Path)
    actions.add_argument("--diagnostics", type=Path)
    actions.add_argument("--repair", action="store_true")
    actions.add_argument("--uninstall", action="store_true")
    actions.add_argument("--check-updates", action="store_true")
    parser.add_argument("--feed")
    parser.add_argument("--trust-store", type=Path)
    parser.add_argument(
        "--model-catalog",
        type=Path,
        help="Signed model-catalog envelope; requires --trust-store",
    )
    parser.add_argument("--minimum-catalog-sequence", type=int, default=0)
    parser.add_argument("--installer-version", default="1.0.0")
    parser.add_argument("--installed-api", type=int, default=1)
    parser.add_argument("--installed-schema", type=int)
    parser.add_argument("--delete-data", action="store_true")
    parser.add_argument(
        "--postgres-image",
        help="Exact previously verified PostgreSQL image ID for isolated restore",
    )
    parser.add_argument(
        "--public-key", type=Path, help="Independently trusted release public key"
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=Path("/var/lib/kyrion-install")
        if os.name != "nt"
        else Path(os.environ.get("ProgramData", "C:/ProgramData")) / "Kyrion",
    )
    args = parser.parse_args()
    if args.probe:
        print(json.dumps(inventory(args.target), indent=2, ensure_ascii=False))
        return 0
    if not sys.stdin.isatty():
        print(
            "E_INTERACTIVE: use a local terminal; --probe is available without prompts",
            file=sys.stderr,
        )
        return 2
    language = input("Sprache / language [de/en]: ").strip().lower()
    language = language if language in {"de", "en"} else "en"
    messages = json.loads(
        (ROOT / "locales" / (language + ".json")).read_text(encoding="utf-8")
    )
    print(messages["intro"])
    if args.recommend_ai:
        try:
            if args.model_catalog is not None and args.trust_store is None:
                raise ValueError("E_MODEL_TRUST_REQUIRED")
            catalog = load_catalog(
                args.model_catalog.read_bytes() if args.model_catalog else None,
                json.loads(args.trust_store.read_text(encoding="utf-8"))
                if args.trust_store
                else None,
                args.minimum_catalog_sequence,
            )
            guided_recommendation(inventory(args.target), messages, catalog)
            return 0
        except (OSError, ValueError, TypeError, KeyError):
            print("E_MODEL_RECOMMENDATION", file=sys.stderr)
            return 2
    if (
        args.backup
        or args.verify_backup
        or args.diagnostics
        or args.repair
        or args.uninstall
        or args.check_updates
    ):
        try:
            return run_maintenance(args, messages)
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
            code = str(error).split(":", 1)[0]
            print(
                code if re.fullmatch(r"[A-Z][A-Z_]{0,79}", code) else "E_MAINTENANCE",
                file=sys.stderr,
            )
            print(messages["failed"], file=sys.stderr)
            return 2
    report = inventory(args.target)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["candidateProvisioning"]:
        print(messages["unsupported"])
        return 2
    print(messages["modes"])
    mode = input("> ").strip().lower()
    if mode not in {"fresh", "resume"}:
        print(messages["maintenanceUnavailable"])
        return 2
    if mode == "fresh" and args.target.exists():
        print(messages["existing"])
        return 2
    if mode == "resume" and not (args.target / "install-state.json").is_file():
        print(messages["noResume"])
        return 2
    if args.public_key is None:
        print(messages["trustRequired"])
        return 2
    hostname = input(messages["hostname"] + ": ").strip()
    address = input(messages["address"] + ": ").strip()
    try:
        validate_inputs(args.target, hostname, address)
        reviewed = authenticated_review(args.bundle, args.public_key)
        manifest = reviewed.manifest
        image_plan(manifest)
        digest = reviewed.manifest_sha256
        if manifest["architecture"] != "linux/" + report["architecture"]:
            raise ValueError("E_ARCH: release does not match this target")
        print(messages["review"])
        print(
            json.dumps(
                {
                    "release": manifest["release"],
                    "architecture": manifest["architecture"],
                    "artifactBytes": sum(
                        item["bytes"] for item in manifest["artifacts"]
                    ),
                    "privateStagingBytes": sum(
                        item["bytes"] for item in manifest["artifacts"]
                    ),
                    "target": str(args.target),
                    "url": "https://" + hostname,
                    "httpsBind": address + ":443",
                    "mode": mode,
                },
                indent=2,
            )
        )
        if input(messages["approve"] + " [INSTALL]: ").strip() != "INSTALL":
            print(messages["cancelled"])
            return 0
        print(messages["working"])
        state = provision(
            args.target, args.bundle, args.public_key, hostname, address, digest
        )
        print(messages["servicesHealthy"])
        print("https://" + hostname)
        print(messages["certificate"] + ": " + str(args.target / "data/tls/cert.pem"))
        print(messages["handoff"])
        print(
            messages["bootstrap"] + ": " + str(args.target / "secrets/bootstrap.secret")
        )
        with installation_lock(args.target):
            installation = Installation(
                args.target, manifest, digest, hostname, address
            )
            guided_setup(installation, messages)
            state = installation.state
        print(messages["pending"])
        print(
            json.dumps(
                {
                    "installationId": state["installationId"],
                    "stage": state["stage"],
                    "ownerSetup": state["ownerSetup"],
                    "backup": state["backup"],
                    "updates": state["updates"],
                    "centralIdentity": state.get("centralIdentity", "not-verified"),
                    "hardwareSelection": state.get("hardwareSelection", []),
                },
                indent=2,
            )
        )
        return 0
    except KeyboardInterrupt:
        print(messages["interrupted"], file=sys.stderr)
        return 130
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        # Error details from untrusted files, TLS or command output aren't logs.
        code = str(error).split(":", 1)[0]
        print(
            (code if re.fullmatch(r"[A-Z][A-Z_]{0,79}", code) else "E_INSTALL")
            + ": "
            + messages["failed"],
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
