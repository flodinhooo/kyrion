"""Reviewed device maintenance through the existing authenticated Core authority."""

from __future__ import annotations

import json
import uuid


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
            return
        choice = input(messages["devicesSelect"] + " [0]: ").strip()
        if choice in {"", "0"}:
            return
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
