"""Task-scoped observation; OS values/providers are injected, no hardware access."""

from unittest.mock import patch

from kyrion_gateway_agent import health


def test_without_task_authority_no_integration_or_audio_provider_is_probed():
    with (
        patch.object(health, "_memory", return_value=(1024, 512)),
        patch.object(health, "_temperature", return_value=None),
        patch.object(health, "_throttled", return_value=False),
        patch.object(health, "_interface", return_value={"present": False, "connected": False}),
        patch.object(health, "_has_global_ipv6", return_value=False),
        patch.object(health, "_system_state", return_value="unknown"),
        patch.object(health, "_serial_adapters") as serial,
        patch.object(health, "_audio_endpoint") as audio,
        patch.object(health, "_zigbee_health") as zigbee,
        patch.object(health, "_bluetooth_devices") as bluetooth,
        patch.object(health, "_service_status") as services,
        patch.object(health, "_voice_service_status") as voice,
    ):
        observed = health.collect_health(include_integrations=False, include_voice=False)
    for provider in (serial, audio, zigbee, bluetooth, services, voice):
        provider.assert_not_called()
    assert observed["services"] == []
    assert observed["adapters"] == []
    assert observed["audio"] is None
    assert observed["zigbee"] is None
    assert observed["temperatureCelsius"] is None
