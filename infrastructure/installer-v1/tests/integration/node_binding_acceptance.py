"""Actual Core/TLS and Windows private enrollment; no SCM or task-runtime claims."""

import contextlib
import hashlib
import io
import json
import secrets
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def exercise_node_binding(request, token, root, core_port):
    from node_entry import component

    component(require_linux=False)
    from kyrion_gateway_agent import client, windows_storage
    from kyrion_gateway_agent.health import platform_identity
    from node_entry import run
    from node_pairing import Pairing

    space = request("GET", "/v1/space", token=token)["id"]
    before = request("GET", "/v1/gateways", token=token)
    code = request(
        "POST",
        "/v1/gateways/enrollments",
        {"displayName": "Bound developer fixture"},
        token=token,
    )
    certificate = root / "core-cert.pem"
    digest = hashlib.sha256(certificate.read_bytes()).hexdigest()
    url = "https://127.0.0.1:" + str(core_port)
    identity = platform_identity()
    try:
        client.enroll(
            url,
            code["enrollmentToken"],
            identity,
            node_credential=secrets.token_urlsafe(32),
            expected_space_id=str(uuid.uuid4()),
            ca_certificate=str(certificate),
            ca_sha256=digest,
        )
    except client.CoreRequestError as error:
        if error.status != 401:
            raise ValueError("E_NODE_BINDING_FIXTURE_WRONG_SPACE") from error
    else:
        raise ValueError("E_NODE_BINDING_FIXTURE_WRONG_SPACE_ACCEPTED")
    if request("GET", "/v1/gateways", token=token) != before:
        raise ValueError("E_NODE_BINDING_FIXTURE_WRONG_SPACE_MUTATION")

    with windows_storage.temporary_directory() as private:
        config = private / "agent.json"
        packet = private / "pairing.json"
        windows_storage.publish(
            packet,
            json.dumps(
                Pairing(
                    url,
                    certificate.read_text(encoding="ascii"),
                    digest,
                    code["id"],
                    code["expiresAt"],
                    code["enrollmentToken"],
                    space,
                    str(uuid.uuid4()),
                ).document()
            ).encode("utf-8"),
        )
        args = SimpleNamespace(
            prepare_node=True,
            node_config=config,
            node_pairing=packet,
            node_url=None,
            node_token_file=None,
            node_certificate=None,
            node_run=False,
        )
        messages = json.loads(
            (Path(__file__).resolve().parents[2] / "locales/en.json").read_bytes()
        )
        original = client.enroll
        observed = []

        def lost_ack(*arguments, **options):
            result = original(*arguments, **options)
            observed.append(result.node_id)
            raise client.CoreRequestError("E_SYNTHETIC_LOST_ACK_AFTER_REAL_CORE_COMMIT")

        with patch.object(client, "enroll", side_effect=lost_ack):
            try:
                with (
                    patch("builtins.input", return_value="PAIR"),
                    contextlib.redirect_stdout(io.StringIO()),
                ):
                    run(args, messages)
            except client.CoreRequestError as error:
                if str(error) != "E_SYNTHETIC_LOST_ACK_AFTER_REAL_CORE_COMMIT":
                    raise
            else:
                raise ValueError("E_NODE_BINDING_FIXTURE_FAULT_NOT_REACHED")
        with (
            patch("builtins.input", return_value="PAIR"),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            run(args, messages)
        from kyrion_gateway_agent.config import AgentConfig

        result = AgentConfig.load(config)
        args.prepare_node = False
        args.node_pairing = None
        with (
            patch("builtins.input", return_value="HEARTBEAT"),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            run(args, messages)
        after = request("GET", "/v1/gateways", token=token)
        if (
            result.space_id != space
            or observed != [result.node_id]
            or len(after) != len(before) + 1
        ):
            raise ValueError("E_NODE_BINDING_FIXTURE_ACK_IDENTITY")
        if not any(row["id"] == result.node_id for row in after):
            raise ValueError("E_NODE_BINDING_FIXTURE_INVENTORY")
    return {
        "actualCoreTlsBoundEnrollment": True,
        "wrongSpaceClaimDoesNotConsumeCode": True,
        "lostAckSameNodeAndCredential": True,
        "actualWindowsPrivateAgentStorage": True,
        "actualWindowsInstallerPairingImportAndHeartbeat": True,
        "nativeTargetIdentity": identity,
        "scmAcceptance": False,
        "fault": "response discarded after actual Core commit",
    }
