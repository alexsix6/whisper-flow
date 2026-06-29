"""Unit tests for the Windows FFmpeg/DirectShow audio selection path."""

import io
import importlib
import sys
import types
import ast
import wave


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
    engine._owns_process = True
    engine._protocol = "framed"
    engine._prefetched_chunks = []
    engine._raw_path = None
    engine._raw_file = None
    engine._devices = []
    engine._ffmpeg_audio_devices = []
    engine._has_system_audio = False
    return engine


class FakeWidget:
    def __init__(self):
        self.calls = []

    def configure(self, **kwargs):
        self.calls.append(kwargs)


class FakeRoot:
    def __init__(self):
        self.after_calls = []

    def after(self, delay, callback=None):
        self.after_calls.append((delay, callback))
        return f"after-{len(self.after_calls)}"

    def after_cancel(self, _):
        return None


def test_audio_subprocess_imports_modules_used_by_system_throttle(monkeypatch):
    client = import_client(monkeypatch)
    tree = ast.parse(client._AUDIO_SUBPROCESS)
    imported = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    assert "time" in imported


def test_audio_subprocess_logs_system_audio_levels(monkeypatch):
    client = import_client(monkeypatch)

    assert "AUDIO_LEVEL:" in client._AUDIO_SUBPROCESS
    assert "rms=" in client._AUDIO_SUBPROCESS
    assert "peak=" in client._AUDIO_SUBPROCESS


def test_audio_subprocess_treats_explicit_device_override_as_strict(monkeypatch):
    client = import_client(monkeypatch)

    assert "Override {env_name}={override_value!r} did not match an input device" in client._AUDIO_SUBPROCESS
    assert 'return [("override", override)]' in client._AUDIO_SUBPROCESS


def test_audio_subprocess_contains_wasapi_loopback_backend(monkeypatch):
    client = import_client(monkeypatch)

    assert "pyaudiowpatch" in client._AUDIO_SUBPROCESS
    assert "get_default_wasapi_loopback" in client._AUDIO_SUBPROCESS
    assert "_wasapi_open_stream" in client._AUDIO_SUBPROCESS
    assert "rejected WASAPI callback open" in client._AUDIO_SUBPROCESS
    assert 'if cmd != "wasapi":' in client._AUDIO_SUBPROCESS
    assert "stream_callback=callback" in client._AUDIO_SUBPROCESS
    assert "frames_per_buffer=512" in client._AUDIO_SUBPROCESS
    assert 'cmd == "wasapi"' in client._AUDIO_SUBPROCESS


def test_audio_engine_contains_cable_only_backend_and_signal_gate(monkeypatch):
    client = import_client(monkeypatch)

    assert '"list", "mic", "system", or "wasapi"' in client._AUDIO_SUBPROCESS
    assert '"cable", or "wasapi"' not in client._AUDIO_SUBPROCESS
    assert client.AudioEngine._is_vb_cable_ffmpeg_device(
        None, {"name": "CABLE Output (VB-Audio Virtual Cable)", "alt": "@device"}
    )
    assert not client.AudioEngine._is_vb_cable_ffmpeg_device(
        None, {"name": "CABLE Output (VB-Audio Point)", "alt": "@point"}
    )
    assert any(
        "CABLE Output is silent; route Windows output to CABLE Input" in str(value)
        for value in client.AudioEngine._start_system_cable_capture.__code__.co_consts
    )
    assert any(
        "ffmpeg dshow" in str(value)
        for value in client.AudioEngine._start_system_cable_capture.__code__.co_consts
    )


def test_cable_backend_launches_ffmpeg_through_powershell_raw_file(monkeypatch, tmp_path):
    client = import_client(monkeypatch)
    engine = make_engine(client)
    monkeypatch.setattr(client.shutil, "which", lambda _: "powershell.exe")

    raw_path = tmp_path / "capture.raw"
    err_path = tmp_path / "capture.err"
    cmd, script = engine._build_cable_powershell_command(
        r"C:\Tools\ffmpeg.exe",
        r"audio=@device_cm_{cable}\wave_{cable}",
        str(raw_path),
        str(err_path),
    )

    assert cmd == ["powershell.exe", "-NoProfile", "-Command", script]
    assert script.startswith("ffmpeg -y -hide_banner -nostdin -loglevel warning")
    assert '-f dshow -i "audio=@device_cm_{cable}\\wave_{cable}"' in script
    assert "-f s16le" in script
    assert f'"{raw_path}"' in script
    assert f'2>"{err_path}"' in script


def test_debug_wav_helpers_write_pcm16_file(monkeypatch, tmp_path):
    client = import_client(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WHISPERFLOW_DEBUG_WAV", "1")
    monkeypatch.setattr(client.time, "strftime", lambda _: "20260628-010203")

    path = client._debug_wav_path("system")
    client._write_pcm16_wav(path, [b"\x01\x00\x02\x00"], sample_rate=16000)

    assert path == str(tmp_path / "whisperflow_system_20260628-010203.wav")
    with wave.open(path, "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2
        assert wav_file.getframerate() == 16000
        assert wav_file.readframes(2) == b"\x01\x00\x02\x00"


def test_debug_wav_helper_can_force_cable_evidence_without_env(monkeypatch, tmp_path):
    client = import_client(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("WHISPERFLOW_DEBUG_WAV", raising=False)
    monkeypatch.setattr(client.time, "strftime", lambda _: "20260628-010203")

    path = client._debug_wav_path("system_cable", force=True)

    assert path == str(tmp_path / "whisperflow_system_cable_20260628-010203.wav")


def test_stop_recording_closes_audio_engine_to_unblock_silent_capture(monkeypatch):
    client = import_client(monkeypatch)
    app = client.WhisperFlowClient.__new__(client.WhisperFlowClient)

    class FakeEngine:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    app.is_recording = True
    app._awaiting_stop_ack = False
    app._stop_timeout_id = None
    app.engine = FakeEngine()
    app.root = FakeRoot()
    app.record_btn = FakeWidget()
    app.rec_label = FakeWidget()
    app.hint_label = FakeWidget()
    app.rec_dot = FakeWidget()
    app._timer_id = None
    app._pulse_id = None

    app._stop_recording()

    assert app.is_recording is False
    assert app._awaiting_stop_ack is True
    assert app.engine.closed is True
    assert app._stop_timeout_id == "after-1"
    assert app.root.after_calls[0][0] == 60000


def test_capture_error_resets_recording_state_without_waiting_for_stop_ack(monkeypatch):
    client = import_client(monkeypatch)
    app = client.WhisperFlowClient.__new__(client.WhisperFlowClient)

    class ImmediateRoot:
        def __init__(self):
            self.cancelled = []

        def after(self, delay, callback=None):
            if callback is not None:
                callback()
            return "after"

        def after_cancel(self, token):
            self.cancelled.append(token)

    class FailingEngine:
        active = False

        def open_loopback(self):
            raise RuntimeError("boom")

        def close(self):
            return None

    app.is_recording = True
    app._awaiting_stop_ack = True
    app._stop_timeout_id = "pending-timeout"
    app._timer_id = None
    app._pulse_id = None
    app.root = ImmediateRoot()
    app.engine = FailingEngine()
    app.rec_label = FakeWidget()
    app.record_btn = FakeWidget()
    app.mode_sel = FakeWidget()
    app.hint_label = FakeWidget()
    app.rec_dot = FakeWidget()

    app._capture_worker("system")

    assert app.is_recording is False
    assert app._awaiting_stop_ack is False
    assert app._stop_timeout_id is None
    assert app.root.cancelled == ["pending-timeout"]
    assert any(call.get("state") == "normal" for call in app.record_btn.calls)


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


def test_start_system_capture_can_force_sounddevice_backend(monkeypatch):
    client = import_client(monkeypatch)
    engine = make_engine(client)
    calls = []

    class FakeProcess:
        stdout = io.BytesIO()
        stderr = io.BytesIO()
        pid = 12345

        def poll(self):
            return None

    class FakeThread:
        def __init__(self, target, daemon):
            self.target = target
            self.daemon = daemon

        def start(self):
            return None

    def fake_popen(cmd, stdout=None, stderr=None):
        calls.append(cmd)
        return FakeProcess()

    monkeypatch.setenv("WHISPERFLOW_SYSTEM_BACKEND", "sounddevice")
    monkeypatch.setattr(client.sp, "Popen", fake_popen)
    monkeypatch.setattr(client.time, "sleep", lambda _: None)
    monkeypatch.setattr(client.threading, "Thread", FakeThread)

    engine._start_system_capture()

    assert engine.active is True
    assert engine._protocol == "framed"
    assert calls == [[client.sys.executable, "-c", client._AUDIO_SUBPROCESS, "system"]]


def test_start_system_capture_can_force_wasapi_backend(monkeypatch):
    client = import_client(monkeypatch)
    engine = make_engine(client)
    calls = []

    class FakeProcess:
        stdout = io.BytesIO()
        stderr = io.BytesIO()
        pid = 12345

        def poll(self):
            return None

    class FakeThread:
        def __init__(self, target, daemon):
            self.target = target
            self.daemon = daemon

        def start(self):
            return None

    def fake_popen(cmd, stdout=None, stderr=None):
        calls.append(cmd)
        return FakeProcess()

    monkeypatch.setenv("WHISPERFLOW_SYSTEM_BACKEND", "wasapi")
    monkeypatch.setattr(client.sp, "Popen", fake_popen)
    monkeypatch.setattr(client.time, "sleep", lambda _: None)
    monkeypatch.setattr(client.threading, "Thread", FakeThread)

    engine._start_system_capture()

    assert engine.active is True
    assert engine._protocol == "framed"
    assert calls == [[client.sys.executable, "-c", client._AUDIO_SUBPROCESS, "wasapi"]]


def test_start_system_capture_can_force_cable_backend(monkeypatch, tmp_path):
    client = import_client(monkeypatch)
    engine = make_engine(client)
    engine._ffmpeg_audio_devices = [
        {
            "name": "CABLE Output (VB-Audio Point)",
            "alt": "@device_cm_{point}\\wave_{point}",
        },
        {
            "name": "CABLE Output (VB-Audio Virtual Cable)",
            "alt": "@device_cm_{cable}\\wave_{cable}",
        },
    ]
    raw_path = tmp_path / "cable.raw"
    err_path = tmp_path / "cable.err"
    calls = []
    probe = (1000).to_bytes(2, "little", signed=True) * (client.SAMPLE_RATE * 2)

    class FakeProcess:
        def __init__(self):
            self.stderr = io.BytesIO()
            self.pid = 12345

        def poll(self):
            return None

        def terminate(self):
            return None

        def wait(self, timeout=None):
            return 0

    def fake_start(ffmpeg_bin, spec, raw_file, err_file):
        calls.append((ffmpeg_bin, spec, raw_file, err_file))
        assert raw_file == str(raw_path)
        assert err_file == str(err_path)
        raw_path.write_bytes(probe + (b"\x01\x00" * client.SAMPLE_RATE))
        return FakeProcess()

    monkeypatch.setenv("WHISPERFLOW_SYSTEM_BACKEND", "cable")
    monkeypatch.setattr(client.shutil, "which", lambda _: "ffmpeg")
    monkeypatch.setattr(engine, "_cable_runtime_paths", lambda: (str(raw_path), str(err_path)))
    monkeypatch.setattr(engine, "_start_cable_ffmpeg_process", fake_start)
    monkeypatch.setattr(client.time, "sleep", lambda _: None)

    engine._start_system_capture()

    assert engine.active is True
    assert engine._protocol == "file"
    assert calls == [
        (
            "ffmpeg",
            "audio=@device_cm_{cable}\\wave_{cable}",
            str(raw_path),
            str(err_path),
        )
    ]
    assert len(engine._prefetched_chunks) == 2
    assert engine.read_chunk() == probe[: client.AudioEngine.CHUNK_BYTES]
    engine.close()


def test_start_system_capture_cable_backend_retries_empty_ffmpeg_discovery(monkeypatch, tmp_path):
    client = import_client(monkeypatch)
    engine = make_engine(client)
    raw_path = tmp_path / "cable.raw"
    err_path = tmp_path / "cable.err"
    probe = (1000).to_bytes(2, "little", signed=True) * (client.SAMPLE_RATE * 2)
    rediscovery_timeouts = []
    calls = []

    class FakeProcess:
        stderr = io.BytesIO()
        pid = 12345

        def poll(self):
            return None

        def terminate(self):
            return None

        def wait(self, timeout=None):
            return 0

    def fake_discover(timeout=10):
        rediscovery_timeouts.append(timeout)
        engine._ffmpeg_audio_devices = [
            {
                "name": "CABLE Output (VB-Audio Virtual Cable)",
                "alt": "@device_cm_{cable}\\wave_{cable}",
            },
        ]
        return engine._ffmpeg_audio_devices

    def fake_start(ffmpeg_bin, spec, raw_file, err_file):
        calls.append(spec)
        raw_path.write_bytes(probe)
        return FakeProcess()

    monkeypatch.setenv("WHISPERFLOW_SYSTEM_BACKEND", "cable")
    monkeypatch.setattr(client.shutil, "which", lambda _: "ffmpeg")
    monkeypatch.setattr(engine, "_discover_ffmpeg_devices", fake_discover)
    monkeypatch.setattr(engine, "_cable_runtime_paths", lambda: (str(raw_path), str(err_path)))
    monkeypatch.setattr(engine, "_start_cable_ffmpeg_process", fake_start)
    monkeypatch.setattr(client.time, "sleep", lambda _: None)

    engine._start_system_capture()

    assert rediscovery_timeouts == [30]
    assert calls == ["audio=@device_cm_{cable}\\wave_{cable}"]
    assert engine.active is True
    engine.close()


def test_start_system_capture_cable_backend_can_use_explicit_dshow_spec(monkeypatch, tmp_path):
    client = import_client(monkeypatch)
    engine = make_engine(client)
    raw_path = tmp_path / "cable.raw"
    err_path = tmp_path / "cable.err"
    probe = (1000).to_bytes(2, "little", signed=True) * (client.SAMPLE_RATE * 2)
    calls = []

    class FakeProcess:
        stderr = io.BytesIO()
        pid = 12345

        def poll(self):
            return None

        def terminate(self):
            return None

        def wait(self, timeout=None):
            return 0

    def fail_discover(timeout=10):
        raise AssertionError("explicit cable spec should not rediscover")

    def fake_start(ffmpeg_bin, spec, raw_file, err_file):
        calls.append(spec)
        raw_path.write_bytes(probe)
        return FakeProcess()

    monkeypatch.setenv("WHISPERFLOW_SYSTEM_BACKEND", "cable")
    monkeypatch.setenv("WHISPERFLOW_CABLE_DSHOW_SPEC", "audio=@device_cm_{known}\\wave_{cable}")
    monkeypatch.setattr(client.shutil, "which", lambda _: "ffmpeg")
    monkeypatch.setattr(engine, "_discover_ffmpeg_devices", fail_discover)
    monkeypatch.setattr(engine, "_cable_runtime_paths", lambda: (str(raw_path), str(err_path)))
    monkeypatch.setattr(engine, "_start_cable_ffmpeg_process", fake_start)
    monkeypatch.setattr(client.time, "sleep", lambda _: None)

    engine._start_system_capture()

    assert calls == ["audio=@device_cm_{known}\\wave_{cable}"]
    assert engine.active is True
    engine.close()


def test_start_system_capture_cable_backend_can_tail_external_raw_file(monkeypatch, tmp_path):
    client = import_client(monkeypatch)
    engine = make_engine(client)
    raw_path = tmp_path / "external.raw"
    stale = b"\x00\x00" * client.SAMPLE_RATE
    probe = (1000).to_bytes(2, "little", signed=True) * (client.SAMPLE_RATE * 2)
    raw_path.write_bytes(stale)
    start_calls = []

    def fake_start(*args, **kwargs):
        start_calls.append((args, kwargs))
        raise AssertionError("external raw file mode should not launch ffmpeg")

    def fake_wait(path, byte_count, process=None, timeout=8.0, start_offset=0):
        assert path == str(raw_path)
        assert start_offset == len(stale)
        raw_path.write_bytes(stale + probe + (b"\x01\x00" * client.SAMPLE_RATE))
        return True

    monkeypatch.setenv("WHISPERFLOW_SYSTEM_BACKEND", "cable")
    monkeypatch.setenv("WHISPERFLOW_CABLE_RAW_FILE", str(raw_path))
    monkeypatch.setattr(engine, "_start_cable_ffmpeg_process", fake_start)
    monkeypatch.setattr(engine, "_wait_for_raw_bytes", fake_wait)
    monkeypatch.setattr(client.time, "sleep", lambda _: None)

    engine._start_system_capture()

    assert start_calls == []
    assert engine.active is True
    assert engine._protocol == "file"
    assert engine._owns_process is False
    assert engine.read_chunk() == probe[: client.AudioEngine.CHUNK_BYTES]
    engine.close()
    assert engine._process is None
    assert engine._owns_process is True


def test_start_system_capture_cable_external_raw_file_times_out_without_new_bytes(monkeypatch, tmp_path):
    client = import_client(monkeypatch)
    engine = make_engine(client)
    raw_path = tmp_path / "external.raw"
    raw_path.write_bytes(b"\x01\x00" * client.SAMPLE_RATE)

    monkeypatch.setenv("WHISPERFLOW_SYSTEM_BACKEND", "cable")
    monkeypatch.setenv("WHISPERFLOW_CABLE_RAW_FILE", str(raw_path))
    monkeypatch.setattr(engine, "_wait_for_raw_bytes", lambda *_, **__: False)
    monkeypatch.setattr(client.time, "sleep", lambda _: None)

    try:
        engine._start_system_capture()
    except RuntimeError as exc:
        assert "External CABLE raw file did not receive audio" in str(exc)
    else:
        raise AssertionError("external raw file mode should require fresh bytes")


def test_start_system_capture_cable_backend_fails_fast_on_silence(monkeypatch, tmp_path):
    client = import_client(monkeypatch)
    engine = make_engine(client)
    engine._ffmpeg_audio_devices = [
        {
            "name": "CABLE Output (VB-Audio Virtual Cable)",
            "alt": "@device_cm_{cable}\\wave_{cable}",
        },
    ]
    raw_path = tmp_path / "silent.raw"
    err_path = tmp_path / "silent.err"
    probe = b"\x00\x00" * (client.SAMPLE_RATE * 2)

    class FakeProcess:
        def __init__(self):
            self.stderr = io.BytesIO()
            self.pid = 12345
            self.terminated = False

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

    fake_process = FakeProcess()

    def fake_start(ffmpeg_bin, spec, raw_file, err_file):
        raw_path.write_bytes(probe)
        return fake_process

    monkeypatch.setenv("WHISPERFLOW_SYSTEM_BACKEND", "cable")
    monkeypatch.setattr(client.shutil, "which", lambda _: "ffmpeg")
    monkeypatch.setattr(engine, "_cable_runtime_paths", lambda: (str(raw_path), str(err_path)))
    monkeypatch.setattr(engine, "_start_cable_ffmpeg_process", fake_start)
    monkeypatch.setattr(client.time, "sleep", lambda _: None)

    try:
        engine._start_system_capture()
    except RuntimeError as exc:
        assert "CABLE Output is silent" in str(exc)
    else:
        raise AssertionError("silent CABLE Output should fail before streaming")

    assert fake_process.terminated is True
    assert engine.active is False


def test_start_system_capture_falls_back_to_sounddevice_after_ffmpeg_rejections(
    monkeypatch,
):
    client = import_client(monkeypatch)
    engine = make_engine(client)
    engine._ffmpeg_audio_devices = [
        {
            "name": "Mezcla estéreo (Realtek(R) Audio)",
            "alt": "@device_cm_{stereo}\\wave_{stereo}",
        },
    ]
    calls = []

    class FakeProcess:
        def __init__(self, returncode):
            self.returncode = returncode
            self.stdout = io.BytesIO()
            self.stderr = io.BytesIO(b"Could not find output pin")
            self.pid = 12345

        def poll(self):
            return self.returncode

    class FakeThread:
        def __init__(self, target, daemon):
            self.target = target
            self.daemon = daemon

        def start(self):
            return None

    def fake_popen(cmd, stdout=None, stderr=None):
        calls.append(cmd)
        if cmd[-1] == "system":
            return FakeProcess(None)
        return FakeProcess(1)

    monkeypatch.delenv("WHISPERFLOW_SYSTEM_BACKEND", raising=False)
    monkeypatch.setattr(client.shutil, "which", lambda _: "ffmpeg")
    monkeypatch.setattr(client.sp, "Popen", fake_popen)
    monkeypatch.setattr(client.time, "sleep", lambda _: None)
    monkeypatch.setattr(client.threading, "Thread", FakeThread)

    engine._start_system_capture()

    assert engine.active is True
    assert engine._protocol == "framed"
    attempts_per_target = len(client.AudioEngine.COMMON_AUDIO_PIN_NAMES) + 1
    assert len(calls) == (attempts_per_target * 2) + 1
    assert calls[-1] == [
        client.sys.executable,
        "-c",
        client._AUDIO_SUBPROCESS,
        "system",
    ]
