from unittest.mock import Mock

import pytest

from kyrion_gateway_agent import bluetooth


def completed(stdout: str = "", returncode: int = 0) -> Mock:
    return Mock(stdout=stdout, stderr="", returncode=returncode)


def test_known_lights_exposes_only_supported_melk_devices(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bluetooth, "_run", Mock(return_value=completed(
        "Device C7:7C:08:10:37:EA MELK-OA20\nDevice AA:BB:CC:DD:EE:FF Headphones\n"
    )))

    assert bluetooth.known_melk_lights() == [{
        "address": "C7:7C:08:10:37:EA", "name": "MELK-OA20", "model": "OA20",
        "supported": True, "on": None, "brightness": None, "hue": None,
        "saturation": None,
    }]


def test_power_uses_fixed_nine_byte_packet(monkeypatch: pytest.MonkeyPatch) -> None:
    run = Mock(side_effect=[
        completed("Name: MELK-OA20\nConnected: yes\n"), completed(),
    ])
    monkeypatch.setattr(bluetooth, "_run", run)

    bluetooth.set_power("C7:7C:08:10:37:EA", False)

    assert run.call_args_list[1].args[0][-14:] == [
        "9", "126", "4", "4", "0", "0", "0", "255", "0", "239",
        "1", "type", "s", "command",
    ]


def test_colour_selects_rgb_and_writes_expected_channels(monkeypatch: pytest.MonkeyPatch) -> None:
    run = Mock(return_value=completed("Name: MELK-OA20\nConnected: yes\n"))
    monkeypatch.setattr(bluetooth, "_run", run)

    bluetooth.set_colour("C7:7C:08:10:37:EA", 180, 100)

    assert run.call_count == 4
    assert run.call_args_list[3].args[0][-14:-5] == [
        "9", "126", "7", "5", "3", "0", "255", "255", "16",
    ]


@pytest.mark.parametrize("address", ["", "C7:7C:08:10:37:EA;reboot", "AA:BB"])
def test_invalid_address_never_reaches_subprocess(
    monkeypatch: pytest.MonkeyPatch, address: str,
) -> None:
    run = Mock()
    monkeypatch.setattr(bluetooth, "_run", run)

    with pytest.raises(bluetooth.BluetoothLightError):
        bluetooth.set_power(address, True)

    run.assert_not_called()
