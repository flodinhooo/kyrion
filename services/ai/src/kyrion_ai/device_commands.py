import re

from kyrion_ai.contracts import (
    DeviceCommandArguments,
    DeviceCommandProposal,
    DeviceCommandProposalRequest,
    DeviceTargetSelector,
    RuntimeDevice,
)

_GERMAN_BRIGHTNESS = re.compile(
    r"^(?:(?:hey\s+)?velora[,\s]+)?(?:bitte\s+)?(?:stelle|stell|setze|setz|mach)\b.*?"
    r"\b(?P<kind>nanoleafs?|lichter?|lampen?)\b\s+(?:im|in)\s+(?P<room>.+?)\s+auf\s+(?P<value>\d{1,3})\s*"
    r"(?:%|prozent)(?:\s|[.!?]|$)",
    re.IGNORECASE,
)
_ENGLISH_BRIGHTNESS = re.compile(
    r"^(?:(?:hey\s+)?velora[,\s]+)?(?:please\s+)?(?:set|put)\b.*?\b(?P<kind>nanoleafs?|lights?|lamps?)\b\s+in\s+"
    r"(?:the\s+)?(?P<room>.+?)\s+(?:to|at)\s+(?P<value>\d{1,3})\s*"
    r"(?:%|percent)(?:\s|[.!?]|$)",
    re.IGNORECASE,
)
_GERMAN_POWER = re.compile(
    r"^(?:(?:hey\s+)?velora[,\s]+)?(?:bitte\s+)?"
    r"(?:schalte|schalt|schau(?:t)?\s+dir|mach|macht)\b.*?"
    r"\b(?P<kind>nanoleafs?|licht(?:er)?|lampen?)\b\s+(?:im|in)\s+(?P<room>.+?)\s+"
    r"(?P<state>an|ein|aus|raus)(?:\s*,?\s*bitte)?[.!?]*\s*$",
    re.IGNORECASE,
)
_GERMAN_GLOBAL_LIGHT_POWER = re.compile(
    r"^(?:(?:hey\s+)?velora[,\s]+)?(?:bitte\s+)?(?:schalte|schalt|mach|schau\s+dir)\s+"
    r"(?:(?:die|alle)\s+)?lichter?\s+(?P<state>an|ein|aus|raus)(?:\s*,?\s*bitte)?[.!?]*\s*$",
    re.IGNORECASE,
)
_ENGLISH_POWER = re.compile(
    r"^(?:(?:hey\s+)?velora[,\s]+)?(?:please\s+)?(?:turn|switch)\b.*?"
    r"\b(?P<kind>nanoleafs?|lights?|lamps?)\b\s+in\s+(?:the\s+)?(?P<room>.+?)\s+"
    r"(?P<state>on|off)(?:\s|[.!?]|$)",
    re.IGNORECASE,
)
_GERMAN_DEVICE_BRIGHTNESS = re.compile(
    r"^(?:(?:hey\s+)?velora[,\s]+)?(?:bitte\s+)?(?:stelle|stell|setze|setz|mach)\s+"
    r"(?P<target>.+?)\s+auf\s+(?P<value>\d{1,3})\s*(?:%|prozent)(?:\s|[.!?]|$)",
    re.IGNORECASE,
)
_ENGLISH_DEVICE_BRIGHTNESS = re.compile(
    r"^(?:(?:hey\s+)?velora[,\s]+)?(?:please\s+)?(?:set|put)\s+"
    r"(?P<target>.+?)\s+(?:to|at)\s+(?P<value>\d{1,3})\s*"
    r"(?:%|percent)(?:\s|[.!?]|$)",
    re.IGNORECASE,
)
_GERMAN_DEVICE_POWER = re.compile(
    r"^(?:(?:hey\s+)?velora[,\s]+)?(?:bitte\s+)?(?:schalte|schalt|mach)\s+"
    r"(?P<target>.+?)\s+(?P<state>an|ein|aus)(?:\s|[.!?]|$)",
    re.IGNORECASE,
)
_ENGLISH_DEVICE_POWER = re.compile(
    r"^(?:(?:hey\s+)?velora[,\s]+)?(?:please\s+)?(?:turn|switch)\s+"
    r"(?P<target>.+?)\s+(?P<state>on|off)(?:\s|[.!?]|$)",
    re.IGNORECASE,
)
_GERMAN_ROOM_CORRECTION = re.compile(
    r"^(?:nein[,\s]+)?(?:ich\s+meine|gemeint\s+war)\s+(?:im|in)\s+(?P<room>.+?)"
    r"(?:[.!?]|$)",
    re.IGNORECASE,
)
_ENGLISH_ROOM_CORRECTION = re.compile(
    r"^(?:no[,\s]+)?(?:i\s+mean|i\s+meant)\s+in\s+(?:the\s+)?(?P<room>.+?)"
    r"(?:[.!?]|$)",
    re.IGNORECASE,
)


def propose_device_command(
    request: DeviceCommandProposalRequest,
) -> DeviceCommandProposal | None:
    """Recognise the deliberately bounded first Nanoleaf command slice."""
    direct = _propose_direct(request)
    if direct is not None:
        return direct

    correction_pattern = (
        _GERMAN_ROOM_CORRECTION
        if request.locale == "de"
        else _ENGLISH_ROOM_CORRECTION
    )
    correction = correction_pattern.search(request.message)
    if correction is None:
        return None
    for message in reversed(request.prior_messages):
        if message.role != "user":
            continue
        prior = _propose_direct(request.model_copy(update={"message": message.content}))
        if prior is not None and prior.selector.room_name is not None:
            return DeviceCommandProposal(
                capability=prior.capability,
                selector=_room_selector(
                    request,
                    correction.group("room"),
                    prior.capability,
                ),
                arguments=prior.arguments,
            )
    return None


def _propose_direct(
    request: DeviceCommandProposalRequest,
) -> DeviceCommandProposal | None:
    brightness_pattern = (
        _GERMAN_BRIGHTNESS if request.locale == "de" else _ENGLISH_BRIGHTNESS
    )
    brightness_match = brightness_pattern.search(request.message)
    if brightness_match:
        value = int(brightness_match.group("value"))
        kind = brightness_match.group("kind").casefold()
        provider = "nanoleaf" if kind.startswith("nanoleaf") else "light"
        if value > 100:
            return None
        if not _supports(request, provider, "light.setBrightness"):
            return None
        return DeviceCommandProposal(
            capability="light.setBrightness",
            selector=_room_selector(
                request,
                brightness_match.group("room"),
                "light.setBrightness",
                provider,
            ),
            arguments=DeviceCommandArguments(brightness=value),
        )

    if request.locale == "de":
        global_light_match = _GERMAN_GLOBAL_LIGHT_POWER.search(request.message)
        if global_light_match and _supports(request, "light", "power.set"):
            state = global_light_match.group("state").lower()
            return DeviceCommandProposal(
                capability="power.set",
                selector=DeviceTargetSelector(provider="light"),
                arguments=DeviceCommandArguments(on=state in {"an", "ein"}),
            )

    power_pattern = _GERMAN_POWER if request.locale == "de" else _ENGLISH_POWER
    power_match = power_pattern.search(request.message)
    if power_match:
        state = power_match.group("state").lower()
        kind = power_match.group("kind").casefold()
        provider = "nanoleaf" if kind.startswith("nanoleaf") else "light"
        if not _supports(request, provider, "power.set"):
            return None
        return DeviceCommandProposal(
            capability="power.set",
            selector=_room_selector(
                request,
                power_match.group("room"),
                "power.set",
                provider,
                allow_multiple=True,
            ),
            arguments=DeviceCommandArguments(on=state in {"an", "ein", "on"}),
        )
    device_brightness_pattern = (
        _GERMAN_DEVICE_BRIGHTNESS
        if request.locale == "de"
        else _ENGLISH_DEVICE_BRIGHTNESS
    )
    device_brightness_match = device_brightness_pattern.search(request.message)
    if device_brightness_match:
        value = int(device_brightness_match.group("value"))
        device = _exact_device(
            request,
            device_brightness_match.group("target"),
            "light.setBrightness",
        )
        if value <= 100 and device is not None:
            return DeviceCommandProposal(
                capability="light.setBrightness",
                selector=DeviceTargetSelector(provider="light", deviceId=device.id),
                arguments=DeviceCommandArguments(brightness=value),
            )
    device_power_pattern = (
        _GERMAN_DEVICE_POWER if request.locale == "de" else _ENGLISH_DEVICE_POWER
    )
    device_power_match = device_power_pattern.search(request.message)
    if device_power_match:
        device = _exact_device(request, device_power_match.group("target"), "power.set")
        if device is not None:
            state = device_power_match.group("state").lower()
            return DeviceCommandProposal(
                capability="power.set",
                selector=DeviceTargetSelector(provider="light", deviceId=device.id),
                arguments=DeviceCommandArguments(on=state in {"an", "ein", "on"}),
            )
    return None


def _room_selector(
    request: DeviceCommandProposalRequest,
    room_name: str,
    capability: str,
    provider: str = "nanoleaf",
    allow_multiple: bool = False,
) -> DeviceTargetSelector:
    if allow_multiple:
        room_names = _split_room_names(request.locale, room_name)
        if len(room_names) > 1:
            return DeviceTargetSelector(
                roomNames=[
                    _normalise_room_name(request, name, capability, provider)
                    for name in room_names
                ],
                provider=provider,
            )
    return DeviceTargetSelector(
        roomName=_normalise_room_name(request, room_name, capability, provider),
        provider=provider,
    )


def _split_room_names(locale: str, room_names: str) -> list[str]:
    conjunction = (
        r"\s*(?:,|\bund\b)\s*(?:(?:im|in)\s+|(?:der|dem|den|das|die)\s+)?"
        if locale == "de"
        else r"\s*(?:,|\band\b)\s*(?:in\s+(?:the\s+)?)?"
    )
    return [name for name in re.split(conjunction, room_names, flags=re.IGNORECASE) if name.strip()]


def _normalise_room_name(
    request: DeviceCommandProposalRequest,
    room_name: str,
    capability: str,
    provider: str,
) -> str:
    normalised = room_name.strip(" .,!?").strip()
    normalised = re.sub(r"^(?:der|dem|den|das|die)\s+", "", normalised, flags=re.IGNORECASE)
    room_names = {
        device.room_name
        for device in request.devices
        if (provider == "light" and device.device_class == "light" or device.provider == provider)
        and device.room_name is not None
        and any(item.id == capability for item in device.capabilities)
    }
    exact = [room for room in room_names if room.casefold() == normalised.casefold()]
    if len(exact) == 1:
        normalised = exact[0]
    else:
        aliases = [
            room
            for room in room_names
            if _room_alias_key(room) == _room_alias_key(normalised)
        ]
        if len(aliases) == 1:
            normalised = aliases[0]
    return normalised


def _room_alias_key(room_name: str) -> str:
    return re.sub(r"(?:room|raum)$", "#room", room_name.casefold().replace(" ", ""))


def _supports(request: DeviceCommandProposalRequest, provider: str, capability: str) -> bool:
    return any(
        (provider == "light" and device.device_class == "light" or device.provider == provider)
        and any(item.id == capability for item in device.capabilities)
        for device in request.devices
    )


def _exact_device(
    request: DeviceCommandProposalRequest,
    target: str,
    capability: str,
) -> RuntimeDevice | None:
    normalised = target.strip(" .,!?").strip()
    normalised = re.sub(r"^(?:die|das|den|the)\s+", "", normalised, flags=re.IGNORECASE)
    matches = [
        device
        for device in request.devices
        if device.device_class == "light"
        and device.display_name.casefold() == normalised.casefold()
        and any(item.id == capability for item in device.capabilities)
    ]
    return matches[0] if len(matches) == 1 else None
