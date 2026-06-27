"""Unit tests for the Windows FFmpeg/DirectShow audio selection path."""

import io
import importlib
import sys
import types


def import_client(monkeypatch):
    monkeypatch.setitem(sys.modules, "customtkinter", types.SimpleNamespace())
    monkeypatch.setitem(sys.modules, "pyperclip", types.SimpleNamespace())
    monkeypatch.setitem(sys.modules, "websockets", types.SimpleNamespace())
    sys.modules.pop("whisperflow_client", None)
    return importlib.import_module("whisperflow_client")


def make_engine(client):
    engine = client.AudioEngine.__new__(client.AudioEngine)
    engine.active = False
    engine._process = None
    engine._protocol = "framed"
    engine._devices = []
    engine._ffmpeg_audio_devices = []
    engine._has_system_audio = False
    return engine


def test_ffmpeg_device_discovery_parses_directshow_alternative_names(monkeypatch):
    client = import_client(monkeypatch)
    engine = make_engine(client)
    dshow_output = """
[dshow @ 000001] DirectShow audio devices
[dshow @ 000001]  "Microphone Array (Realtek(R) Audio)"
[dshow @ 000001]     Alternative name "@device_cm_{mic}\\wave_{mic}"
[dshow @ 000001]  "CABLE Output (VB-Audio Virtual Cable)"
[dshow @ 000001]     Alternative name "@device_cm_{cable}\\wave_{cable}"
[dshow @ 000001] DirectShow video devices
[dshow @ 000001]  "Integrated Camera"
"""

    monkeypatch.setattr(client.shutil, "which", lambda _: "ffmpeg")
    monkeypatch.setattr(
        client.sp,
        "run",
        lambda *args, **kwargs: types.SimpleNamespace(stdout="", stderr=dshow_output),
    )

    engine._discover_ffmpeg_devices()

    assert engine._ffmpeg_audio_devices == [
        {
            "name": "Microphone Array (Realtek(R) Audio)",
            "alt": "@device_cm_{mic}\\wave_{mic}",
        },
        {
            "name": "CABLE Output (VB-Audio Virtual Cable)",
            "alt": "@device_cm_{cable}\\wave_{cable}",
        },
    ]
    assert engine.has_system_audio is True


def test_ffmpeg_device_discovery_parses_inline_audio_tag_format(monkeypatch):
    """ffmpeg >=7/8 lists devices inline as "(audio)"/"(video)"/"(none)" with no
    section headers; the parser must still capture audio devices AND their
    alternative names (capturing by friendly name alone fails on these builds)."""
    client = import_client(monkeypatch)
    engine = make_engine(client)
    dshow_output = (
        '[in#0 @ 0x1] "Iriun Webcam" (video)\n'
        '[in#0 @ 0x1]   Alternative name "@device_pnp_cam"\n'
        '[in#0 @ 0x1] "OBS Virtual Camera" (none)\n'
        '[in#0 @ 0x1]   Alternative name "@device_sw_obs"\n'
        '[in#0 @ 0x1] "Mezcla estéreo (Realtek(R) Audio)" (audio)\n'
        '[in#0 @ 0x1]   Alternative name "@device_cm_{GUID}\\wave_{stereo}"\n'
        '[in#0 @ 0x1] "CABLE Output (VB-Audio Virtual Cable)" (audio)\n'
        '[in#0 @ 0x1]   Alternative name "@device_cm_{GUID}\\wave_{cable}"\n'
    )

    monkeypatch.setattr(client.shutil, "which", lambda _: "ffmpeg")
    monkeypatch.setattr(
        client.sp,
        "run",
        lambda *args, **kwargs: types.SimpleNamespace(stdout="", stderr=dshow_output),
    )

    engine._discover_ffmpeg_devices()

    assert engine._ffmpeg_audio_devices == [
        {
            "name": "Mezcla estéreo (Realtek(R) Audio)",
            "alt": "@device_cm_{GUID}\\wave_{stereo}",
        },
        {
            "name": "CABLE Output (VB-Audio Virtual Cable)",
            "alt": "@device_cm_{GUID}\\wave_{cable}",
        },
    ]
    assert engine.has_system_audio is True


def test_ffmpeg_system_candidates_prefer_virtual_alt_name_and_honor_override(
    monkeypatch,
):
    client = import_client(monkeypatch)
    engine = make_engine(client)
    engine._ffmpeg_audio_devices = [
        {
            "name": "Microphone Array (Realtek(R) Audio)",
            "alt": "@device_cm_{mic}\\wave_{mic}",
        },
        {
            "name": "Stereo Mix (Realtek(R) Audio)",
            "alt": "@device_cm_{stereo}\\wave_{stereo}",
        },
        {
            "name": "CABLE Output (VB-Audio Virtual Cable)",
            "alt": "@device_cm_{cable}\\wave_{cable}",
        },
    ]

    monkeypatch.delenv("WHISPERFLOW_SYSTEM_DEVICE", raising=False)
    candidates = engine._ffmpeg_system_candidates()

    assert candidates[0][0] == "auto:alt"
    assert candidates[0][1]["name"] == "CABLE Output (VB-Audio Virtual Cable)"
    assert candidates[0][2] == "@device_cm_{cable}\\wave_{cable}"
    assert all(
        "Microphone Array" not in candidate[1]["name"] for candidate in candidates
    )

    monkeypatch.setenv("WHISPERFLOW_SYSTEM_DEVICE", "@device_cm_{stereo}")
    candidates = engine._ffmpeg_system_candidates()

    assert candidates[0][0] == "override:alt"
    assert candidates[0][1]["name"] == "Stereo Mix (Realtek(R) Audio)"
    assert candidates[0][2] == "@device_cm_{stereo}\\wave_{stereo}"


def test_start_system_capture_tries_alt_name_then_pin_fallback(monkeypatch):
    client = import_client(monkeypatch)
    engine = make_engine(client)
    engine._ffmpeg_audio_devices = [
        {
            "name": "CABLE Output (VB-Audio Virtual Cable)",
            "alt": "@device_cm_{cable}\\wave_{cable}",
        },
    ]
    calls = []

    class FakeProcess:
        def __init__(self, returncode):
            self.returncode = returncode
            self.stdout = io.BytesIO(b"\0" * client.AudioEngine.CHUNK_BYTES)
            self.stderr = io.BytesIO(b"Could not open audio device")
            self.pid = 12345

        def poll(self):
            return self.returncode

    def fake_popen(cmd, stdout=None, stderr=None):
        calls.append(cmd)
        return FakeProcess(1 if len(calls) == 1 else None)

    class FakeThread:
        def __init__(self, target, daemon):
            self.target = target
            self.daemon = daemon

        def start(self):
            return None

    monkeypatch.delenv("WHISPERFLOW_SYSTEM_DEVICE", raising=False)
    monkeypatch.setattr(client.shutil, "which", lambda _: "ffmpeg")
    monkeypatch.setattr(client.sp, "Popen", fake_popen)
    monkeypatch.setattr(client.time, "sleep", lambda _: None)
    monkeypatch.setattr(client.threading, "Thread", FakeThread)

    engine._start_system_capture()

    assert engine.active is True
    assert (
        calls[0][calls[0].index("-i") + 1] == "audio=@device_cm_{cable}\\wave_{cable}"
    )
    assert "-audio_pin_name" not in calls[0]
    assert calls[1][calls[1].index("-audio_pin_name") + 1] == "Capture"
    assert (
        calls[1][calls[1].index("-i") + 1] == "audio=@device_cm_{cable}\\wave_{cable}"
    )
