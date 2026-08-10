from pathlib import Path
from threading import Event

from kyrion_voice_satellite.audio import FRAME_BYTES
from kyrion_voice_satellite.config import SatelliteConfig
from kyrion_voice_satellite.core_client import CoreVoiceClient
from kyrion_voice_satellite.pcm_uplink import PcmUplinkClient, PcmUplinkError

config = SatelliteConfig.load(Path("/home/flodinho/.config/kyrion/voice-satellite.json"))
assert config.core_url and config.satellite_id and config.credential_file
sessions = CoreVoiceClient(config.core_url, config.satellite_id, config.credential_file)
session = sessions.open_session()

wrong_credential = Path("/tmp/kyrion-phase31-wrong-token")
wrong_credential.write_text("invalid-phase31-token", encoding="utf-8")
try:
    wrong = PcmUplinkClient(config.core_url, config.satellite_id, wrong_credential)
    try:
        wrong.stream(session.id, "10000000-0000-0000-0000-000000000001", [])
        raise RuntimeError("Authentication rejection was not enforced")
    except PcmUplinkError as error:
        print(f"auth=pass ({error})")

    client = PcmUplinkClient(config.core_url, config.satellite_id, config.credential_file)
    cancelled = Event()
    cancelled.set()
    result = client.stream(
        session.id,
        "20000000-0000-0000-0000-000000000002",
        [bytes(FRAME_BYTES)],
        cancelled=cancelled,
    )
    print(f"cancel=pass status={result.status} frames={result.frames_received}")

    def disconnected_frames():
        yield bytes(FRAME_BYTES)
        raise OSError("intentional phase31 disconnect")

    try:
        client.stream(
            session.id,
            "30000000-0000-0000-0000-000000000003",
            disconnected_frames(),
        )
        raise RuntimeError("Disconnect was not observed")
    except PcmUplinkError as error:
        print(f"disconnect=pass ({error})")

    result = client.stream(
        session.id,
        "40000000-0000-0000-0000-000000000004",
        [bytes(FRAME_BYTES), bytes(FRAME_BYTES)],
    )
    print(f"reconnect=pass status={result.status} frames={result.frames_received}")
finally:
    wrong_credential.unlink(missing_ok=True)
    sessions.close_session(session.id, "explicit")
