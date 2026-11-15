"""Reviewed device maintenance through the existing authenticated Core authority."""

from __future__ import annotations

import json
import uuid


def offer_device_setup(client, messages: dict[str, str], user: dict) -> None:
    """Resume the existing device authority inside onboarding, not a new registry."""
    installation = client.installation
    print(messages["deviceSetupScope"])
    choice = input(messages["deviceSetupChoice"] + " [SINGLE/DEVICES/LATER]: ").strip()
    if choice not in {"SINGLE", "DEVICES", "LATER"}:
        raise ValueError("E_DEVICE_SETUP_SELECTION")
    progress = {"formatVersion": 1, "choice": choice, "phase": "deferred"}
    if choice == "LATER":
        installation.state["deviceSetup"] = progress
        installation.save()
        return
    permissions = user.get("permissions")
    if (
        not isinstance(permissions, list)
        or not all(isinstance(value, str) for value in permissions)
        or "gateways:read" not in permissions
    ):
        print(messages["deviceSetupPermission"])
        installation.state["deviceSetup"] = {**progress, "phase": "permission-required"}
        installation.save()
        return
    # This is progress only. Core remains the authoritative source of device
    # membership, live availability and task grants. A reviewed choice is never
    # represented as successful remote installation or service activation.
    installation.state["deviceSetup"] = {**progress, "phase": "in-progress"}
    installation.save()
    if choice == "DEVICES":
        guided_devices(client, messages)
    nodes = managed_devices(client)
    if choice == "SINGLE" and any(node.get("revokedAt") is None for node in nodes):
        print(messages["deviceSetupExisting"])
    print(messages["deviceSetupReviewed"])
    print(
        json.dumps(
            {
                "pairedDevices": sum(node.get("revokedAt") is None for node in nodes),
                "remoteInstallationPerformed": False,
            }
        )
    )
    installation.state["deviceSetup"] = {**progress, "phase": "reviewed"}
    installation.save()


def managed_devices(client) -> list[dict]:
    response = client.request("GET", "/v1/gateways/management")
    if not isinstance(response, list) or len(response) > 1000:
        raise ValueError("E_DEVICE_RESPONSE")
    for node in response:
        if not isinstance(node, dict):
            raise TypeError("E_DEVICE_RESPONSE")
        for field in ("id", "revision"):
            if (
                not isinstance(node.get(field), str)
                or str(uuid.UUID(node[field])) != node[field]
            ):
                raise ValueError("E_DEVICE_RESPONSE")
        if not isinstance(node.get("displayName"), str) or node.get(
            "expectedAvailability"
        ) not in {"unknown", "always_on", "intermittent"}:
            raise ValueError("E_DEVICE_RESPONSE")
    return response


def guided_devices(client, messages: dict[str, str]) -> None:
    """No local registry, remote shell, optimistic success or implicit device action."""
    print(messages["devicesScope"])
    while True:
        nodes = managed_devices(client)
        for index, node in enumerate(nodes, 1):
            # JSON escaping also prevents terminal escape/control injection.
            print(
                str(index) + ": " + json.dumps(node, ensure_ascii=True, sort_keys=True)
            )
        if not nodes:
            print(messages["devicesEmpty"])
        choice = input(messages["devicesSelect"] + " [PAIR/0]: ").strip()
        if choice in {"", "0"}:
            return
        if choice == "PAIR":
            from node_pairing import guided_export

            guided_export(client, messages)
            continue
        if (
            not choice.isascii()
            or not choice.isdigit()
            or not 1 <= int(choice) <= len(nodes)
        ):
            raise ValueError("E_DEVICE_SELECTION")
        node = nodes[int(choice) - 1]
        if node.get("revokedAt") is not None:
            print(messages["devicesRevoked"])
            continue
        action = input(
            messages["devicesAction"] + " [EDIT/TASKS/REMOVE/CANCEL]: "
        ).strip()
        route = "/v1/gateways/" + node["id"]
        if action == "EDIT":
            name = input(messages["devicesName"] + ": ").strip()
            availability = input(
                messages["devicesAvailability"] + " [unknown/always_on/intermittent]: "
            ).strip()
            if (
                not name
                or len(name) > 120
                or any(ord(char) < 32 or 127 <= ord(char) < 160 for char in name)
            ):
                raise ValueError("E_DEVICE_NAME")
            if availability not in {"unknown", "always_on", "intermittent"}:
                raise ValueError("E_DEVICE_AVAILABILITY")
            print(
                json.dumps(
                    {"displayName": name, "expectedAvailability": availability},
                    ensure_ascii=True,
                )
            )
            if (
                input(messages["devicesSaveReview"] + " [SAVE/CANCEL]: ").strip()
                != "SAVE"
            ):
                continue
            client.request(
                "PUT",
                route + "/management",
                {
                    "revision": node["revision"],
                    "displayName": name,
                    "expectedAvailability": availability,
                },
            )
        elif action == "TASKS":
            print(messages["devicesTasksScope"])
            selection = input(
                messages["devicesTasksChoice"] + " [integration,voice/none]: "
            ).strip()
            tasks = (
                []
                if selection == "none"
                else [part.strip() for part in selection.split(",")]
            )
            if len(set(tasks)) != len(tasks) or any(
                task not in {"integration", "voice"} for task in tasks
            ):
                raise ValueError("E_DEVICE_TASKS")
            tasks.sort()
            print(json.dumps({"allowedTasks": tasks}, ensure_ascii=True))
            if (
                input(messages["devicesTasksReview"] + " [APPLY/CANCEL]: ").strip()
                != "APPLY"
            ):
                continue
            client.request(
                "PUT",
                route + "/tasks",
                {"revision": node["revision"], "allowedTasks": tasks},
            )
        elif action == "REMOVE":
            if (
                input(messages["devicesRemoveReview"] + " [REMOVE/CANCEL]: ").strip()
                != "REMOVE"
            ):
                continue
            client.request("DELETE", route, {"revision": node["revision"]})
        else:
            continue
        # Re-read authoritative state. A failed request never produces success.
        print(messages["devicesReadBack"])
