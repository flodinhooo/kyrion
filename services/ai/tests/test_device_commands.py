import pytest

from kyrion_ai.contracts import DeviceCommandProposalRequest
from kyrion_ai.device_commands import propose_device_command

_DEVICES = [
    {
        "id": "device-1",
        "provider": "nanoleaf",
        "deviceClass": "light",
        "displayName": "Panels",
        "roomName": "Schlafzimmer",
        "capabilities": [{"id": "power.set"}, {"id": "light.setBrightness"}],
        "availability": "unknown",
        "observedAt": None,
    }
]


def request(message: str, locale: str = "de") -> DeviceCommandProposalRequest:
    return DeviceCommandProposalRequest(message=message, locale=locale, devices=_DEVICES)


@pytest.mark.parametrize(
    ("message", "room", "brightness"),
    [
        ("Stelle die Nanoleafs im Schlafzimmer auf 20%", "Schlafzimmer", 20),
        ("Setz die Nanoleaf in der Lounge auf 35 Prozent.", "Lounge", 35),
    ],
)
def test_proposes_german_brightness(message: str, room: str, brightness: int) -> None:
    proposal = propose_device_command(request(message))

    assert proposal is not None
    assert proposal.capability == "light.setBrightness"
    assert proposal.selector.room_name == room
    assert proposal.arguments.brightness == brightness


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Schalte die Nanoleafs im Wohnzimmer an.", True),
        ("Schalte die Nanoleafs im Wohnzimmer aus.", False),
    ],
)
def test_proposes_german_power(message: str, expected: bool) -> None:
    proposal = propose_device_command(request(message))

    assert proposal is not None
    assert proposal.capability == "power.set"
    assert proposal.selector.room_name == "Wohnzimmer"
    assert proposal.arguments.on is expected


def test_proposes_real_whispered_german_room_power_phrase() -> None:
    proposal = propose_device_command(request("Macht das Licht im Büro an, bitte."))

    assert proposal is not None
    assert proposal.capability == "power.set"
    assert proposal.selector.room_name == "Büro"
    assert proposal.selector.provider == "light"
    assert proposal.arguments.on is True


def test_light_category_does_not_require_a_nanoleaf_device() -> None:
    hue_only = DeviceCommandProposalRequest(
        message="Mach die Lichter im Gang aus.",
        locale="de",
        devices=[{**_DEVICES[0], "provider": "zigbee", "roomName": "Gang"}],
    )

    proposal = propose_device_command(hue_only)

    assert proposal is not None
    assert proposal.selector.provider == "light"
    assert proposal.selector.room_name == "Gang"
    assert proposal.arguments.on is False


def test_proposes_german_multi_room_light_power() -> None:
    multi_room = DeviceCommandProposalRequest(
        message="Hey Velora, schalte bitte das Licht im Schlafzimmer und im Flur aus.",
        locale="de",
        devices=[
            _DEVICES[0],
            {**_DEVICES[0], "id": "device-2", "provider": "zigbee", "roomName": "Flur"},
        ],
    )

    proposal = propose_device_command(multi_room)

    assert proposal is not None
    assert proposal.selector.provider == "light"
    assert proposal.selector.room_name is None
    assert proposal.selector.room_names == ["Schlafzimmer", "Flur"]
    assert proposal.arguments.on is False


def test_proposes_real_asr_multi_room_light_power_variation() -> None:
    asr_variation = DeviceCommandProposalRequest(
        message="Schalte bitte das Licht im Flur und den Schlafzimmer raus.",
        locale="de",
        devices=[
            _DEVICES[0],
            {**_DEVICES[0], "id": "device-2", "provider": "zigbee", "roomName": "Gang"},
        ],
    )

    proposal = propose_device_command(asr_variation)

    assert proposal is not None
    assert proposal.selector.room_names == ["Flur", "Schlafzimmer"]
    assert proposal.arguments.on is False


def test_proposes_real_asr_schaut_dir_multi_room_variation() -> None:
    asr_variation = DeviceCommandProposalRequest(
        message="Schaut dir das Licht im Flur und im Schlafzimmer aus, bitte.",
        locale="de",
        devices=[
            _DEVICES[0],
            {**_DEVICES[0], "id": "device-2", "provider": "zigbee", "roomName": "Gang"},
        ],
    )

    proposal = propose_device_command(asr_variation)

    assert proposal is not None
    assert proposal.selector.room_names == ["Flur", "Schlafzimmer"]
    assert proposal.arguments.on is False


def test_proposes_english_multi_room_light_power() -> None:
    multi_room = DeviceCommandProposalRequest(
        message="Turn the lights in the bedroom and in the hallway off.",
        locale="en",
        devices=[
            _DEVICES[0],
            {**_DEVICES[0], "id": "device-2", "provider": "zigbee", "roomName": "hallway"},
        ],
    )

    proposal = propose_device_command(multi_room)

    assert proposal is not None
    assert proposal.selector.room_names == ["bedroom", "hallway"]
    assert proposal.arguments.on is False


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Schalte die Lichter an.", True),
        ("Schalte die Lichter aus, bitte.", False),
        ("Schalte alle Lichter aus.", False),
        ("Mach alle Lichter an.", True),
        ("Schau dir die Lichter raus.", False),
    ],
)
def test_proposes_global_german_light_power(message: str, expected: bool) -> None:
    proposal = propose_device_command(request(message))

    assert proposal is not None
    assert proposal.selector.provider == "light"
    assert proposal.selector.room_name is None
    assert proposal.selector.device_id is None
    assert proposal.arguments.on is expected


def test_resolves_unique_german_room_alias_to_catalog_name() -> None:
    aliased = DeviceCommandProposalRequest(
        message="Schalte die Nanoleafs im Gamingraum aus bitte",
        locale="de",
        devices=[{**_DEVICES[0], "roomName": "Gamingroom"}],
    )

    proposal = propose_device_command(aliased)

    assert proposal is not None
    assert proposal.selector.room_name == "Gamingroom"
    assert proposal.arguments.on is False


def test_applies_explicit_room_correction_to_previous_command() -> None:
    corrected = DeviceCommandProposalRequest(
        message="Ich meine im Gamingroom",
        locale="de",
        devices=[{**_DEVICES[0], "roomName": "Gamingroom"}],
        priorMessages=[
            {
                "role": "user",
                "content": "Schalte die Nanoleafs im Gamingraum aus bitte",
            },
            {
                "role": "assistant",
                "content": "Ich finde dort keine Nanoleafs.",
            },
        ],
    )

    proposal = propose_device_command(corrected)

    assert proposal is not None
    assert proposal.selector.room_name == "Gamingroom"
    assert proposal.arguments.on is False


def test_proposes_english_brightness() -> None:
    proposal = propose_device_command(
        request("Set the Nanoleafs in the bedroom to 20 percent.", "en")
    )

    assert proposal is not None
    assert proposal.selector.room_name == "bedroom"
    assert proposal.arguments.brightness == 20


def test_proposes_brightness_for_one_exact_device_name() -> None:
    proposal = propose_device_command(request("Stelle Panels auf 20%"))

    assert proposal is not None
    assert proposal.selector.device_id == "device-1"
    assert proposal.selector.room_name is None
    assert proposal.arguments.brightness == 20


def test_proposes_power_for_one_exact_device_name() -> None:
    proposal = propose_device_command(request("Schalte Panels aus"))

    assert proposal is not None
    assert proposal.selector.device_id == "device-1"
    assert proposal.arguments.on is False


def test_rejects_partial_or_ambiguous_device_names() -> None:
    assert propose_device_command(request("Stelle Panel auf 20%")) is None
    ambiguous = DeviceCommandProposalRequest(
        message="Stelle Panels auf 20%",
        locale="de",
        devices=[_DEVICES[0], {**_DEVICES[0], "id": "device-2"}],
    )

    assert propose_device_command(ambiguous) is None


@pytest.mark.parametrize(
    "message",
    [
        "Wie geht es dir?",
        "Stelle die Nanoleafs im Schlafzimmer auf 120%",
        "Stelle das Licht irgendwo auf 20%",
        "Wie stellt man die Nanoleafs im Schlafzimmer auf 20%?",
        "Stelle die Nanoleafs links im Schlafzimmer auf 20%",
    ],
)
def test_rejects_out_of_scope_or_invalid_requests(message: str) -> None:
    assert propose_device_command(
        request(message)
    ) is None


def test_does_not_propose_an_unavailable_runtime_capability() -> None:
    unavailable = DeviceCommandProposalRequest(
        message="Stelle die Nanoleafs im Schlafzimmer auf 20%",
        locale="de",
        devices=[{**_DEVICES[0], "capabilities": [{"id": "power.set"}]}],
    )

    assert propose_device_command(unavailable) is None
