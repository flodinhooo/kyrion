#!/usr/bin/env python3
"""Local guided installer entrypoint. Public website has no setup state."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from build_identity import read_build
from bundle import authenticated_review
from error_guidance import guidance
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


def maintenance_result(args, messages: dict[str, str]) -> int:
    try:
        return run_maintenance(args, messages)
    except KeyboardInterrupt:
        print(messages["maintenancePaused"], file=sys.stderr)
        return 130
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        code = str(error).split(":", 1)[0]
        advice = guidance(code, messages)
        if advice:
            print(advice, file=sys.stderr)
        if code in {"E_IDENTITY_CANCELLED", "E_SPACE_CANCELLED"}:
            return 3
        print(
            code if re.fullmatch(r"[A-Z][A-Z_]{0,79}", code) else "E_MAINTENANCE",
            file=sys.stderr,
        )
        print(messages["failed"], file=sys.stderr)
        return 2


def main() -> int:
    if sys.version_info < (3, 12):
        print("E_PYTHON: Python 3.12 or newer is required", file=sys.stderr)
        return 2
    try:
        build = read_build()
    except (OSError, ValueError):
        print("E_INSTALLER_BUILD", file=sys.stderr)
        return 2
    parser = argparse.ArgumentParser(description="Kyrion local guided installer")
    parser.add_argument("--version", action="version", version=build["version"])
    parser.add_argument(
        "--probe", action="store_true", help="Read-only target inventory, no install"
    )
    parser.add_argument("--bundle", type=Path, default=ROOT / "release")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--verify-bundle", action="store_true")
    actions.add_argument(
        "--windows-service",
        choices=("core", "web", "caddy", "postgres-init"),
        help=argparse.SUPPRESS,
    )
    actions.add_argument("--recommend-ai", action="store_true")
    actions.add_argument("--backup", type=Path)
    actions.add_argument("--verify-backup", type=Path)
    actions.add_argument("--restore", type=Path)
    actions.add_argument("--retire-for-restore", type=Path)
    parser.add_argument("--restore-target-id")
    parser.add_argument("--transfer-receipt", type=Path)
    parser.add_argument("--restore-hostname")
    parser.add_argument("--restore-address")
    actions.add_argument("--diagnostics", type=Path)
    actions.add_argument("--repair", action="store_true")
    actions.add_argument("--uninstall", action="store_true")
    actions.add_argument("--check-updates", action="store_true")
    actions.add_argument(
        "--updates",
        choices=("configure", "status", "disable", "rotate-trust", "download"),
    )
    parser.add_argument("--trust-rotation", type=Path)
    actions.add_argument(
        "--background-update-check", action="store_true", help=argparse.SUPPRESS
    )
    actions.add_argument("--refresh-model-catalog", action="store_true")
    actions.add_argument("--continue-setup", action="store_true")
    actions.add_argument("--extend-bootstrap", action="store_true")
    actions.add_argument(
        "--home-assistant", choices=("configure", "status", "disconnect")
    )
    actions.add_argument(
        "--owner-recovery", choices=("provision", "open", "complete", "rotate")
    )
    parser.add_argument("--recovery-space", help="Existing local Space UUID")
    parser.add_argument("--feed")
    parser.add_argument(
        "--identity-issuer", default="https://auth.kyrion.ch/realms/kyrion"
    )
    parser.add_argument("--identity-client-id", default="kyrion-local")
    parser.add_argument("--trust-store", type=Path)
    parser.add_argument(
        "--model-catalog",
        type=Path,
        help="Signed model-catalog envelope; requires --trust-store",
    )
    parser.add_argument("--minimum-catalog-sequence", type=int, default=0)
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
    args.installer_version = build["version"]
    if args.background_update_check:
        from update_worker import run as background_check

        try:
            return background_check(args.target)
        except (OSError, ValueError, TypeError, KeyError):
            print("E_UPDATE_CHECK", file=sys.stderr)
            return 2
    if args.verify_bundle:
        if args.public_key is None:
            print("E_SIGNATURE_TRUST_REQUIRED", file=sys.stderr)
            return 2
        try:
            if os.name == "nt":
                from native_bundle import authenticated_review as verify_release
            else:
                verify_release = authenticated_review
            checked = verify_release(args.bundle, args.public_key)
            print(
                json.dumps(
                    {
                        "release": checked.manifest["release"],
                        "architecture": checked.manifest["architecture"],
                        "signatureVerified": True,
                        "manifestSha256": checked.manifest_sha256,
                        "runtimeActivated": False,
                    }
                )
            )
            return 0
        except (OSError, ValueError, KeyError, TypeError):
            print("E_BUNDLE_VERIFICATION", file=sys.stderr)
            return 2
    if args.windows_service:
        from native_runtime import serve

        try:
            return serve(args.target, args.windows_service)
        except (OSError, ValueError, KeyError, TypeError):
            return 2
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
            if (
                args.model_catalog is None
                and (args.target / "install-state.json").is_file()
            ):
                from model_cache import cached_catalog
                from models import validate_catalog
                from recovery import load_installation

                with installation_lock(args.target):
                    catalog = cached_catalog(load_installation(args.target))
                validate_catalog(catalog, args.minimum_catalog_sequence)
            else:
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
        or args.restore
        or args.retire_for_restore
        or args.diagnostics
        or args.repair
        or args.uninstall
        or args.check_updates
        or args.updates
        or args.refresh_model_catalog
        or args.continue_setup
        or args.extend_bootstrap
        or args.owner_recovery
        or args.home_assistant
    ):
        return maintenance_result(args, messages)
    report = inventory(args.target)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    native_windows = report["system"] == "Windows" and report["architecture"] == "amd64"
    if not report["candidateProvisioning"] and not native_windows:
        print(messages["unsupported"])
        return 2
    print(messages["modes"])
    mode = input("> ").strip().lower()
    if mode == "restore":
        args.restore = Path(input(messages["restoreBackupPath"] + ": ").strip())
        receipt = input(messages["restoreReceiptPath"] + ": ").strip()
        args.transfer_receipt = Path(receipt) if receipt else None
        return maintenance_result(args, messages)
    if mode == "repair":
        args.repair = True
        return maintenance_result(args, messages)
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
        from identity_settings import validate_identity

        identity = validate_identity(
            {
                "issuer": args.identity_issuer,
                "clientId": args.identity_client_id,
                "allowLoopbackHttp": False,
            }
        )
        if native_windows:
            from native_bundle import authenticated_review as native_review
            from native_runtime import preflight, provision_native

            preflight(args.target, hostname, address, fresh=mode == "fresh")
            reviewed = native_review(args.bundle, args.public_key)
        else:
            validate_inputs(args.target, hostname, address)
            reviewed = authenticated_review(args.bundle, args.public_key)
        manifest = reviewed.manifest
        if native_windows and manifest["schemaVersion"] != 3:
            raise ValueError("E_NATIVE_SERVICE_HOST_REQUIRED")
        if not native_windows:
            image_plan(manifest)
        digest = reviewed.manifest_sha256
        if (
            manifest["architecture"]
            != ("windows/" if native_windows else "linux/") + report["architecture"]
        ):
            raise ValueError("E_ARCH: release does not match this target")
        artifacts = [manifest["artifact"]] if native_windows else manifest["artifacts"]
        if native_windows:
            print(messages["windowsServicesReview"])
        print(messages["review"])
        print(
            json.dumps(
                {
                    "release": manifest["release"],
                    "architecture": manifest["architecture"],
                    "artifactBytes": sum(item["bytes"] for item in artifacts),
                    "privateStagingBytes": sum(item["bytes"] for item in artifacts),
                    "expandedBytes": sum(item["bytes"] for item in manifest["files"])
                    if native_windows
                    else None,
                    "target": str(args.target),
                    "url": "https://" + hostname,
                    "httpsBind": address + ":443",
                    "mode": mode,
                },
                indent=2,
            )
        )
        print(messages["identityReview"])
        print(json.dumps(identity, ensure_ascii=True))
        if input(messages["approve"] + " [INSTALL]: ").strip() != "INSTALL":
            print(messages["cancelled"])
            return 0
        print(messages["working"])
        selected_provision = provision_native if native_windows else provision
        state = selected_provision(
            args.target,
            args.bundle,
            args.public_key,
            hostname,
            address,
            digest,
            identity=identity,
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
        advice = guidance(code, messages)
        if advice:
            print(advice, file=sys.stderr)
        if code in {"E_IDENTITY_CANCELLED", "E_SPACE_CANCELLED"}:
            return 3
        help_key = (
            "nativeErrorElevation"
            if code == "E_NATIVE_ELEVATION"
            else "nativeErrorPort"
            if code.startswith("E_NATIVE_PORT_")
            else "nativeErrorVersion"
            if code == "E_NATIVE_WINDOWS_VERSION"
            else "nativeErrorServiceHost"
            if code == "E_NATIVE_SERVICE_HOST_REQUIRED"
            else "nativeErrorOwnership"
            if code in {"E_SERVICE_FOREIGN", "E_NATIVE_OWNER", "E_TASK_ANCESTOR"}
            else None
        )
        if help_key:
            print(messages[help_key], file=sys.stderr)
        print(
            (code if re.fullmatch(r"[A-Z][A-Z_]{0,79}", code) else "E_INSTALL")
            + ": "
            + messages["failed"],
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
