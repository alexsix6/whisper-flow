#!/usr/bin/env python3
"""
WhisperFlow Cloud Client v3.1 — Enterprise-Grade Windows Native

Audio engine: isolated `sounddevice` subprocess.
The GUI process never imports audio libraries directly, which avoids
the Windows 11 COM/PortAudio conflicts seen in tkinter-based clients.

Dual mode: Microphone + System Audio (when a loopback device exists)
Transport: WSS to Cloud Run with token auth
"""

import asyncio
import array
import json
import logging
import math
import os
import struct
import sys
import tempfile
import threading
import time
import shutil
import re
import wave
import subprocess as sp

import customtkinter as ctk
import pyperclip
import websockets

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("whisperflow")

# --- Configuration ---
DEFAULT_SERVER = os.getenv(
    "WHISPERFLOW_SERVER",
    "wss://whisperflow-server-518312107738.us-central1.run.app/ws",
)
AUTH_TOKEN = os.getenv("WHISPERFLOW_AUTH_TOKEN", "")
SAMPLE_RATE = 16000  # OpenAI Whisper expects 16kHz
CHUNK_FRAMES = 8000  # 0.5 seconds at 16kHz


# =============================================================================
# WebSocket helpers (websockets v13–v15+)
# =============================================================================

def _ws_is_open(ws) -> bool:
    if ws is None:
        return False
    try:
        return ws.state.name == "OPEN"
    except AttributeError:
        pass
    try:
        return not ws.closed
    except AttributeError:
        return False


def _debug_wav_path(mode: str, force: bool = False):
    value = os.getenv("WHISPERFLOW_DEBUG_WAV", "").strip()
    if not value and not force:
        return None
    stamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"whisperflow_{mode}_{stamp}.wav"
    if not value:
        return os.path.abspath(filename)
    if value.lower() in {"1", "true", "yes", "on"}:
        return os.path.abspath(filename)
    if value.lower().endswith(".wav"):
        return os.path.abspath(value)
    return os.path.abspath(os.path.join(value, filename))


def _write_pcm16_wav(path: str, chunks: list[bytes], sample_rate: int = SAMPLE_RATE):
    if not path or not chunks:
        return
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with wave.open(path, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"".join(chunks))
    log.info(f"Debug WAV saved: {path}")


def _pcm16_level_values(data: bytes) -> tuple[float, int]:
    if not data:
        return 0.0, 0
    sample_count = len(data) // 2
    if sample_count <= 0:
        return 0.0, 0
    samples = array.array("h")
    samples.frombytes(data[: sample_count * 2])
    if sys.byteorder != "little":
        samples.byteswap()
    total = 0
    peak = 0
    for sample in samples:
        value = abs(int(sample))
        total += int(sample) * int(sample)
        if value > peak:
            peak = value
    return math.sqrt(total / sample_count), peak


def _pcm16_has_signal(data: bytes, rms_threshold: float = 12.0, peak_threshold: int = 120) -> bool:
    rms, peak = _pcm16_level_values(data)
    return rms >= rms_threshold or peak >= peak_threshold


# =============================================================================
# Audio Engine — Isolated subprocess (python -c + sounddevice)
# =============================================================================

# Audio capture subprocess script. Runs in its own python -c process
# with zero COM conflicts because the parent process never imports audio libs.
_AUDIO_SUBPROCESS = r'''
import os, sys, struct, json, time, queue, numpy as np

sd = None

SYSTEM_KEYWORDS = ("mezcla", "stereo mix", "loopback", "what u hear")
VIRTUAL_KEYWORDS = ("cable", "virtual", "vb-audio")
MAPPER_KEYWORDS = (
    "asignador de sonido microsoft",
    "microsoft sound mapper",
    "controlador primario de captura de sonido",
    "primary sound capture driver",
)


def _device_payload(index, device):
    api = sd.query_hostapis(device["hostapi"])["name"]
    return {
        "index": index,
        "name": device["name"],
        "api": api,
        "channels": int(device["max_input_channels"]),
        "rate": int(device["default_samplerate"]),
    }


def _name(value):
    return value.lower()


def _is_system(name):
    return any(keyword in name for keyword in SYSTEM_KEYWORDS)


def _is_virtual(name):
    return any(keyword in name for keyword in VIRTUAL_KEYWORDS)


def _is_mapper(name):
    return any(keyword in name for keyword in MAPPER_KEYWORDS)


def _score_device(payload, mode):
    name = _name(payload["name"])
    api = _name(payload["api"])

    if mode == "mic":
        if _is_system(name) or _is_virtual(name) or _is_mapper(name):
            return None
    else:
        if not (_is_system(name) or _is_virtual(name)):
            return None

    score = 0
    if "wasapi" in api:
        score += 400
    elif "wdm-ks" in api:
        score += 300
    elif "directsound" in api:
        score += 200
    elif "mme" in api:
        score += 100

    if mode == "mic":
        if "mic" in name or "micro" in name:
            score += 80
        if "array" in name or "webcam" in name or "iriun" in name:
            score -= 60
        if "headset" in name or "usb" in name or "cougar" in name:
            score += 30
    else:
        if _is_virtual(name):
            score += 140
        else:
            score += 120

    score += min(payload["channels"], 2) * 10
    score += min(payload["rate"], 48000) // 1000
    return score


def _pick_override(payloads, override):
    if not override:
        return None

    override = override.strip()
    if not override:
        return None

    if override.isdigit():
        target = int(override)
        for payload in payloads:
            if payload["index"] == target:
                return payload
        sys.stderr.write(f"AUDIO_WARN: override device index not found: {override}\n")
        sys.stderr.flush()
        return None

    needle = override.lower()
    for payload in payloads:
        if needle in payload["name"].lower():
            return payload

    sys.stderr.write(f"AUDIO_WARN: override device name not found: {override}\n")
    sys.stderr.flush()
    return None


def _candidate_devices(mode):
    payloads = [
        _device_payload(index, device)
        for index, device in enumerate(sd.query_devices())
        if device["max_input_channels"] > 0
    ]

    env_name = "WHISPERFLOW_SYSTEM_DEVICE" if mode == "system" else "WHISPERFLOW_INPUT_DEVICE"
    override_value = os.getenv(env_name, "")
    override = _pick_override(payloads, override_value)
    if override_value.strip() and override is None:
        raise RuntimeError(f"Override {env_name}={override_value!r} did not match an input device")

    ranked = []
    for payload in payloads:
        score = _score_device(payload, mode)
        if score is not None:
            ranked.append((score, payload))

    if not ranked and override is None:
        raise RuntimeError(f"No suitable {mode} input device found")

    ranked.sort(key=lambda item: (item[0], item[1]["channels"], item[1]["rate"]), reverse=True)
    candidates = []
    if override is not None:
        return [("override", override)]
    for _, payload in ranked:
        candidates.append(("auto", payload))
    return candidates


cmd = sys.argv[1]  # "list", "mic", "system", or "wasapi"

if cmd != "wasapi":
    import sounddevice as sd

if cmd == "list":
    devices = sd.query_devices()
    result = {"default_input": sd.default.device[0], "devices": []}
    for i, d in enumerate(devices):
        if d["max_input_channels"] > 0:
            result["devices"].append(_device_payload(i, d))
    print(json.dumps(result))
    sys.exit(0)

candidates = [] if cmd == "wasapi" else _candidate_devices(cmd)
chosen = None
chosen_source = None
probe_data = None
failures = []
target = 16000
is_system_mode = cmd in ("system", "wasapi")
chunk_duration = 2.0 if is_system_mode else 2.5
SILENCE_RMS_THRESHOLD = 12 if is_system_mode else 50
TARGET_RMS = 5000.0 if is_system_mode else 3500.0
MAX_GAIN = 12.0 if is_system_mode else 6.0
MIN_SIGNAL_PEAK = 120.0 if is_system_mode else 200.0


def resample(audio, src_rate, dst_rate):
    if src_rate == dst_rate:
        return audio.astype(np.float32)
    if audio.size == 0:
        return np.array([], dtype=np.float32)
    n = int(round(len(audio) * dst_rate / src_rate))
    if n <= 1:
        return np.array([], dtype=np.float32)
    src_idx = np.arange(len(audio), dtype=np.float32)
    dst_idx = np.linspace(0, len(audio) - 1, n, dtype=np.float32)
    return np.interp(dst_idx, src_idx, audio).astype(np.float32)


def rms_level(audio):
    if audio.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(audio, dtype=np.float64))))


def peak_level(audio):
    if audio.size == 0:
        return 0.0
    return float(np.max(np.abs(audio)))


def level_values(data):
    pcm = np.asarray(data, dtype=np.int16).reshape(-1).astype(np.float32)
    return rms_level(pcm), peak_level(pcm)


def log_level(label, data):
    rms, peak = level_values(data)
    sys.stderr.write(f"AUDIO_LEVEL: {label} rms={rms:.1f} peak={peak:.0f}\n")
    sys.stderr.flush()


def is_silence(audio):
    return rms_level(audio) < SILENCE_RMS_THRESHOLD and peak_level(audio) < MIN_SIGNAL_PEAK


def normalize_audio(audio):
    rms = rms_level(audio)
    peak = peak_level(audio)
    if rms <= 0.0 or peak <= 0.0:
        return audio
    gain = min(TARGET_RMS / rms, MAX_GAIN)
    gain = min(gain, 30000.0 / peak)
    if gain <= 1.0:
        return audio
    return audio * gain


def encode_chunk(data, src_rate):
    pcm = np.asarray(data, dtype=np.int16).reshape(-1).astype(np.float32)
    if pcm.size == 0 or is_silence(pcm):
        return None
    audio = resample(pcm, src_rate, target)
    if audio.size == 0:
        return None
    audio = normalize_audio(audio)
    if is_silence(audio):
        return None
    return np.clip(audio, -32768, 32767).astype(np.int16).tobytes()


def _wasapi_loopbacks(pa):
    if hasattr(pa, "get_loopback_device_info_generator"):
        return list(pa.get_loopback_device_info_generator())
    loopbacks = []
    for index in range(pa.get_device_count()):
        device = pa.get_device_info_by_index(index)
        if device.get("isLoopbackDevice"):
            loopbacks.append(device)
    return loopbacks


def _pick_wasapi_loopback(pa, pyaudio):
    override = os.getenv("WHISPERFLOW_OUTPUT_DEVICE", "").strip()
    loopbacks = _wasapi_loopbacks(pa)
    if override:
        if override.isdigit():
            target_index = int(override)
            for device in loopbacks:
                if int(device["index"]) == target_index:
                    return device
        needle = override.lower()
        for device in loopbacks:
            if needle in device["name"].lower():
                return device
        raise RuntimeError(f"WHISPERFLOW_OUTPUT_DEVICE={override!r} did not match a WASAPI loopback device")

    if hasattr(pa, "get_default_wasapi_loopback"):
        return pa.get_default_wasapi_loopback()

    wasapi = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
    default_output = pa.get_device_info_by_index(wasapi["defaultOutputDevice"])
    output_name = default_output["name"].lower()
    for device in loopbacks:
        device_name = device["name"].lower()
        if output_name in device_name or device_name in output_name:
            return device
    if loopbacks:
        return loopbacks[0]
    raise RuntimeError("No WASAPI loopback output device found")


def _wasapi_open_stream(pa, pyaudio, device, callback):
    device_index = int(device["index"])
    default_rate = int(float(device.get("defaultSampleRate") or 48000))
    channels = int(device.get("maxInputChannels") or 2)

    failures = []
    try:
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=default_rate,
            frames_per_buffer=512,
            input=True,
            input_device_index=device_index,
            stream_callback=callback,
        )
        return stream, default_rate, channels, 2.0, int(default_rate * 2.0)
    except Exception as exc:
        failures.append(f"rate={default_rate} ch={channels} callback: {exc}")
        sys.stderr.write(f"AUDIO_WARN: rejected WASAPI callback open rate={default_rate} ch={channels}: {exc}\n")
        sys.stderr.flush()

    raise RuntimeError("WASAPI loopback open failed: " + " | ".join(failures))


def run_wasapi_loopback():
    try:
        import pyaudiowpatch as pyaudio
    except Exception as exc:
        raise RuntimeError("pyaudiowpatch not installed; run: pip install pyaudiowpatch") from exc

    pa = pyaudio.PyAudio()
    stream = None
    try:
        device = _pick_wasapi_loopback(pa, pyaudio)
        device_index = int(device["index"])
        sys.stderr.write(
            f"AUDIO_DEVICE: wasapi-loopback candidate -> [{device_index}] {device['name']} "
            f"defaultRate={device.get('defaultSampleRate')} maxIn={device.get('maxInputChannels')} maxOut={device.get('maxOutputChannels')}\n"
        )
        sys.stderr.flush()
        callback_queue = queue.Queue()

        def callback(in_data, frame_count, time_info, status):
            callback_queue.put(in_data)
            return (None, pyaudio.paContinue)

        stream, rate, channels, chunk_duration, chunk_frames = _wasapi_open_stream(pa, pyaudio, device, callback)
        sys.stderr.write(
            f"AUDIO_DEVICE: wasapi-loopback -> [{device_index}] {device['name']} ({rate}Hz {channels}ch)\n"
        )
        sys.stderr.write(
            f"AUDIO_FORMAT: wasapi loopback rate={rate} ch={channels} chunk={chunk_duration}s ({chunk_frames} frames)\n"
        )
        sys.stderr.flush()

        chunk_count = 0
        sent_count = 0
        skipped_count = 0
        bytes_per_frame = channels * 2
        target_bytes = chunk_frames * bytes_per_frame
        while True:
            raw_parts = []
            total_bytes = 0
            while total_bytes < target_bytes:
                part = callback_queue.get(timeout=5)
                raw_parts.append(part)
                total_bytes += len(part)
            raw = b"".join(raw_parts)
            samples = np.frombuffer(raw, dtype=np.int16)
            if channels > 1:
                samples = samples.reshape(-1, channels).astype(np.float32).mean(axis=1).astype(np.int16)
            chunk_count += 1
            out = encode_chunk(samples, rate)
            if not out:
                skipped_count += 1
                if skipped_count <= 3 or skipped_count % 5 == 0:
                    log_level(f"wasapi chunk={chunk_count} skipped", samples)
                continue
            sent_count += 1
            if sent_count <= 3 or sent_count % 5 == 0:
                log_level(f"wasapi chunk={chunk_count} sent={sent_count} bytes={len(out)}", samples)
            sys.stdout.buffer.write(struct.pack("<I", len(out)))
            sys.stdout.buffer.write(out)
            sys.stdout.buffer.flush()
    finally:
        if stream is not None:
            stream.stop_stream()
            stream.close()
        pa.terminate()


if cmd == "wasapi":
    run_wasapi_loopback()
    sys.exit(0)


for source, payload in candidates:
    try:
        probe_frames = max(1024, int(payload["rate"] * 0.2))
        probe = sd.rec(
            probe_frames,
            samplerate=payload["rate"],
            channels=1,
            dtype="int16",
            device=payload["index"],
        )
        sd.wait()
        if probe is None or len(probe) == 0:
            raise RuntimeError("empty probe capture")
        chosen = payload
        chosen_source = source
        probe_data = probe
        break
    except Exception as exc:
        failures.append(f"[{payload['index']}] {payload['name']}: {exc}")
        sys.stderr.write(
            f"AUDIO_WARN: rejected [{payload['index']}] {payload['name']}: {exc}\n"
        )
        sys.stderr.flush()

if chosen is None:
    raise RuntimeError("No working input device found: " + " | ".join(failures[:5]))

device = chosen["index"]
rate = chosen["rate"]
channels = 1
chunk_frames = int(rate * chunk_duration)

try:
    sys.stderr.write(
        f"AUDIO_DEVICE: {chosen_source} -> [{chosen['index']}] {chosen['name']} ({chosen['api']} {chosen['rate']}Hz)\n"
    )
    sys.stderr.write(
        f"AUDIO_FORMAT: device={device} rate={rate} ch={channels} chunk={chunk_duration}s ({chunk_frames} frames)\n"
    )
    sys.stderr.flush()

    if is_system_mode:
        log_level("probe", probe_data)

    first_out = encode_chunk(probe_data, rate)
    if first_out:
        sys.stdout.buffer.write(struct.pack("<I", len(first_out)))
        sys.stdout.buffer.write(first_out)
        sys.stdout.buffer.flush()

    chunk_count = 0
    sent_count = 1 if first_out else 0
    skipped_count = 0
    while True:
        chunk_started = time.time()
        data = sd.rec(
            chunk_frames,
            samplerate=rate,
            channels=channels,
            dtype="int16",
            device=device,
        )
        sd.wait()
        chunk_count += 1
        out = encode_chunk(data, rate)
        if not out:
            skipped_count += 1
            if is_system_mode and (skipped_count <= 3 or skipped_count % 5 == 0):
                log_level(f"chunk={chunk_count} skipped", data)
            continue
        sent_count += 1
        if is_system_mode and (sent_count <= 3 or sent_count % 5 == 0):
            log_level(f"chunk={chunk_count} sent={sent_count} bytes={len(out)}", data)
        sys.stdout.buffer.write(struct.pack("<I", len(out)))
        sys.stdout.buffer.write(out)
        sys.stdout.buffer.flush()
        if is_system_mode:
            elapsed = time.time() - chunk_started
            if elapsed < chunk_duration:
                time.sleep(chunk_duration - elapsed)
except KeyboardInterrupt:
    pass
except Exception as e:
    sys.stderr.write(f"AUDIO_ERROR: {e}\n")
    sys.stderr.flush()
    sys.exit(1)
'''


class AudioEngine:
    """Split capture engine: sounddevice for mic, ffmpeg for system audio."""

    CHUNK_BYTES = SAMPLE_RATE * 2  # 1 second of 16kHz mono PCM16
    SYSTEM_KEYWORDS = ("mezcla", "stereo mix", "loopback", "what u hear")
    VIRTUAL_KEYWORDS = ("cable", "virtual", "vb-audio")
    COMMON_AUDIO_PIN_NAMES = ("Capture", "Audio Out", "Output", "Wave Out", "Render", "Stereo Mix")

    class _ExternalRawFileProcess:
        pid = "external"
        stderr = None

        def poll(self):
            return None

        def terminate(self):
            return None

        def wait(self, timeout=None):
            return 0

        def kill(self):
            return None

    def __init__(self):
        self.active = False
        self._process = None
        self._owns_process = True
        self._protocol = "framed"
        self._prefetched_chunks = []
        self._raw_path = None
        self._raw_file = None
        self._devices = []
        self._ffmpeg_audio_devices = []
        self._has_system_audio = False
        self._discover()

    def _is_system_name(self, name: str) -> bool:
        lowered = name.lower()
        return any(keyword in lowered for keyword in self.SYSTEM_KEYWORDS)

    def _is_virtual_name(self, name: str) -> bool:
        lowered = name.lower()
        return any(keyword in lowered for keyword in self.VIRTUAL_KEYWORDS)

    def _discover_sounddevice_devices(self):
        result = sp.run(
            [sys.executable, "-c", _AUDIO_SUBPROCESS, "list"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr[:200])
        data = json.loads(result.stdout)
        for device in data["devices"]:
            name_lower = device["name"].lower()
            is_system = self._is_system_name(name_lower)
            is_virtual = self._is_virtual_name(name_lower)
            if is_system:
                label = "SYSTEM"
            elif is_virtual:
                label = "VIRTUAL"
            else:
                label = "MIC"
            if is_system or is_virtual:
                self._has_system_audio = True
            self._devices.append(device)
            log.info(f"  {label}: [{device['index']}] {device['name']} ({device['api']} {device['rate']}Hz)")

    def _discover_ffmpeg_devices(self, timeout=10):
        ffmpeg_bin = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
        if not ffmpeg_bin:
            return []
        result = sp.run(
            [ffmpeg_bin, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
            capture_output=True,
            text=True,
            timeout=timeout,
            errors="replace",
        )
        output = "\n".join(part for part in (result.stdout, result.stderr) if part)
        discovered = []
        pending = None
        section = None  # old ffmpeg: "DirectShow audio/video devices" section headers
        for line in output.splitlines():
            lowered = line.lower()
            if "directshow audio devices" in lowered:
                section, pending = "audio", None
                continue
            if "directshow video devices" in lowered:
                section, pending = "video", None
                continue
            match = re.search(r'"([^"]+)"', line)
            if not match:
                continue
            value = match.group(1).strip()
            if not value:
                continue
            # Alternative name line (both formats) -> attach to the current device.
            if "alternative name" in lowered:
                if pending is not None:
                    pending["alt"] = value
                continue
            # Device line. ffmpeg >=7/8 tags each device inline as "(audio)" /
            # "(video)" / "(none)" and emits no section headers; older ffmpeg has
            # no inline tag and relies on the section header above. Without the
            # alternative name, dshow capture by friendly name fails on these
            # builds ("Could not find output pin"), so capturing the alt is what
            # actually makes System Audio work.
            stripped = lowered.rstrip()
            if stripped.endswith("(audio)"):
                is_audio = True
            elif stripped.endswith("(video)") or stripped.endswith("(none)"):
                is_audio = False
            else:
                is_audio = section == "audio"
            if not is_audio:
                pending = None
                continue
            pending = {"name": value, "alt": None}
            discovered.append(pending)
        self._ffmpeg_audio_devices = discovered
        if discovered:
            self._has_system_audio = True
            for item in discovered:
                if item.get("alt"):
                    log.info(f"  FFMPEG: {item['name']} | alt={item['alt']}")
                else:
                    log.info(f"  FFMPEG: {item['name']}")
        else:
            snippet = " | ".join(output.splitlines()[:8])
            log.warning(f"FFmpeg device discovery returned no audio devices: {snippet[:400]}")
        return discovered

    def _discover(self):
        """Enumerate devices via sounddevice plus ffmpeg dshow names."""
        log.info("--- Audio Devices ---")
        try:
            self._discover_sounddevice_devices()
        except Exception as exc:
            log.error(f"Device discovery error: {exc}")
        try:
            self._discover_ffmpeg_devices()
        except Exception as exc:
            log.warning(f"FFmpeg device discovery error: {exc}")
        log.info("--- End Devices ---")

    @property
    def has_system_audio(self) -> bool:
        return self._has_system_audio

    def open_microphone(self):
        self._start_capture("mic")

    def open_loopback(self):
        self._start_capture("system")

    def _start_capture(self, mode: str):
        if mode == "system":
            self._start_system_capture()
        else:
            self._start_microphone_capture()

    def _start_microphone_capture(self):
        self._start_sounddevice_capture("mic")

    def _start_sounddevice_capture(self, mode):
        log.info(f"Starting audio capture ({mode}) via sounddevice...")
        self._protocol = "framed"
        self._process = sp.Popen(
            [sys.executable, "-c", _AUDIO_SUBPROCESS, mode],
            stdout=sp.PIPE,
            stderr=sp.PIPE,
        )
        self._finalize_process_startup()

    def _start_system_sounddevice_capture(self, reason):
        log.warning(f"AUDIO_WARN: using sounddevice system fallback ({reason})")
        self._start_sounddevice_capture("system")

    def _start_system_wasapi_capture(self, reason):
        log.warning(
            "AUDIO_WARN: WASAPI loopback is experimental/non-productive on this validated Windows setup; "
            "use WHISPERFLOW_SYSTEM_BACKEND=cable for production System Audio validation"
        )
        log.info(f"Starting audio capture (system) via WASAPI loopback ({reason})...")
        self._protocol = "framed"
        self._process = sp.Popen(
            [sys.executable, "-c", _AUDIO_SUBPROCESS, "wasapi"],
            stdout=sp.PIPE,
            stderr=sp.PIPE,
        )
        self._finalize_process_startup()

    def _is_vb_cable_ffmpeg_device(self, item):
        lowered = item["name"].lower()
        return (
            "cable output" in lowered
            and "vb-audio virtual cable" in lowered
            and "point" not in lowered
        )

    def _pick_ffmpeg_cable_device(self):
        explicit = os.getenv("WHISPERFLOW_CABLE_DSHOW_SPEC", "").strip()
        if explicit:
            lowered = explicit.lower()
            if "point" in lowered:
                raise RuntimeError(
                    "WHISPERFLOW_CABLE_DSHOW_SPEC must target CABLE Output (VB-Audio Virtual Cable), not VB-Audio Point"
                )
            spec = explicit if lowered.startswith("audio=") else f"audio={explicit}"
            target = spec[6:] if spec.lower().startswith("audio=") else spec
            return {
                "name": "CABLE Output (VB-Audio Virtual Cable)",
                "alt": target,
                "spec": spec,
                "source": "WHISPERFLOW_CABLE_DSHOW_SPEC",
            }
        matches = [
            item
            for item in self._ffmpeg_audio_devices
            if self._is_vb_cable_ffmpeg_device(item)
        ]
        if not matches:
            raise RuntimeError("CABLE Output (VB-Audio Virtual Cable) not found in FFmpeg dshow devices")
        matches.sort(key=lambda item: 0 if item.get("alt") else 1)
        return matches[0]

    def _ensure_ffmpeg_cable_device(self):
        if os.getenv("WHISPERFLOW_CABLE_DSHOW_SPEC", "").strip():
            return
        if any(self._is_vb_cable_ffmpeg_device(item) for item in self._ffmpeg_audio_devices):
            return
        log.warning("AUDIO_WARN: CABLE Output missing from cached FFmpeg discovery; retrying dshow discovery")
        try:
            self._discover_ffmpeg_devices(timeout=30)
        except Exception as exc:
            log.warning(f"AUDIO_WARN: FFmpeg dshow rediscovery failed: {exc}")

    def _cable_runtime_paths(self):
        directory = os.path.join(tempfile.gettempdir(), "whisperflow-cable")
        os.makedirs(directory, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        stem = f"capture-{os.getpid()}-{stamp}"
        return os.path.join(directory, stem + ".raw"), os.path.join(directory, stem + ".err")

    def _powershell_double_quote(self, value):
        return '"' + str(value).replace("`", "``").replace('"', '`"') + '"'

    def _build_cable_powershell_command(self, ffmpeg_bin, spec, raw_path, err_path):
        powershell_bin = shutil.which("powershell.exe") or shutil.which("powershell") or "powershell.exe"
        ffmpeg_command = os.getenv("WHISPERFLOW_FFMPEG_COMMAND", "ffmpeg").strip() or "ffmpeg"
        quoted_spec = self._powershell_double_quote(spec)
        quoted_raw = self._powershell_double_quote(raw_path)
        quoted_err = self._powershell_double_quote(err_path)
        script = (
            f"{ffmpeg_command} -y -hide_banner -nostdin -loglevel warning "
            f"-f dshow -i {quoted_spec} -ac 1 -ar {SAMPLE_RATE} -f s16le {quoted_raw} "
            f"2>{quoted_err}"
        )
        return [
            powershell_bin,
            "-NoProfile",
            "-Command",
            script,
        ], script

    def _start_cable_ffmpeg_process(self, ffmpeg_bin, spec, raw_path, err_path):
        cmd, _ = self._build_cable_powershell_command(ffmpeg_bin, spec, raw_path, err_path)
        return sp.Popen(cmd, stdout=sp.DEVNULL, stderr=sp.DEVNULL)

    def _read_cable_error(self, err_path):
        messages = []
        if err_path and os.path.exists(err_path):
            try:
                with open(err_path, "r", encoding="utf-8", errors="replace") as handle:
                    messages.append(handle.read())
            except OSError:
                pass
        process = self._process
        if process and process.stderr and process.poll() is not None:
            try:
                messages.append(process.stderr.read().decode(errors="replace"))
            except Exception:
                pass
        return "\n".join(part.strip() for part in messages if part and part.strip())

    def _wait_for_raw_bytes(self, raw_path, byte_count, process=None, timeout=8.0, start_offset=0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if os.path.getsize(raw_path) - start_offset >= byte_count:
                    return True
            except OSError:
                pass
            if process is not None and process.poll() is not None:
                return False
            time.sleep(0.1)
        return False

    def _start_system_cable_capture(self, reason):
        log.info(f"Starting audio capture (system) via VB-Cable dshow ({reason})...")
        external_raw = os.getenv("WHISPERFLOW_CABLE_RAW_FILE", "").strip()
        if external_raw:
            self._start_system_cable_file_capture(external_raw, "WHISPERFLOW_CABLE_RAW_FILE")
            return
        ffmpeg_bin = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
        if not ffmpeg_bin:
            raise RuntimeError("ffmpeg not found in PATH")
        self._ensure_ffmpeg_cable_device()
        item = self._pick_ffmpeg_cable_device()
        target_name = item.get("alt") or item["name"]
        clean_target = target_name.replace(chr(34), "")
        spec = item.get("spec") or f"audio={clean_target}"
        raw_path, err_path = self._cable_runtime_paths()
        process = self._start_cable_ffmpeg_process(ffmpeg_bin, spec, raw_path, err_path)
        self._process = process

        probe_bytes = self.CHUNK_BYTES * 2
        if not self._wait_for_raw_bytes(raw_path, probe_bytes, process):
            err = self._read_cable_error(err_path)
            self.close()
            raise RuntimeError(f"CABLE Output dshow open/probe failed: {err[:600]}")

        try:
            raw_file = open(raw_path, "rb")
            probe = raw_file.read(probe_bytes)
        except OSError as exc:
            self.close()
            raise RuntimeError(f"CABLE Output dshow probe file failed: {exc}") from exc
        if len(probe) < probe_bytes:
            raw_file.close()
            err = self._read_cable_error(err_path)
            self.close()
            raise RuntimeError(f"CABLE Output dshow probe failed: {err[:600]}")

        rms, peak = _pcm16_level_values(probe)
        log.warning(f"[audio] AUDIO_LEVEL: cable signal-probe rms={rms:.1f} peak={peak}")
        if not _pcm16_has_signal(probe):
            raw_file.close()
            self.close()
            raise RuntimeError(
                "CABLE Output is silent; route Windows output to CABLE Input "
                "(VB-Audio Virtual Cable) and play audio before recording"
            )

        self._protocol = "file"
        self._process = process
        self._raw_path = raw_path
        self._raw_file = raw_file
        self._prefetched_chunks = [
            probe[index : index + self.CHUNK_BYTES]
            for index in range(0, len(probe), self.CHUNK_BYTES)
            if len(probe[index : index + self.CHUNK_BYTES]) == self.CHUNK_BYTES
        ]
        self.active = True
        if target_name == item["name"]:
            log.info(f"AUDIO_DEVICE: cable -> {item['name']} spec={spec} (ffmpeg dshow)")
        else:
            log.info(f"AUDIO_DEVICE: cable -> {item['name']} using alt={target_name} spec={spec} (ffmpeg dshow)")
        log.warning("[audio] AUDIO_FORMAT: ffmpeg dshow raw-file 16000Hz mono")
        log.info(f"Audio subprocess running (PID {self._process.pid})")

    def _start_system_cable_file_capture(self, raw_path, reason):
        raw_path = os.path.abspath(raw_path)
        log.info(f"Starting audio capture (system) via external VB-Cable raw file ({reason})...")
        probe_bytes = self.CHUNK_BYTES * 2
        start_offset = os.path.getsize(raw_path) if os.path.exists(raw_path) else 0
        if not self._wait_for_raw_bytes(raw_path, probe_bytes, None, timeout=10.0, start_offset=start_offset):
            raise RuntimeError(
                "External CABLE raw file did not receive audio; start the FFmpeg CABLE Output writer "
                f"before recording: {raw_path}"
            )

        try:
            raw_file = open(raw_path, "rb")
            raw_file.seek(start_offset)
            probe = raw_file.read(probe_bytes)
        except OSError as exc:
            raise RuntimeError(f"External CABLE raw file failed: {exc}") from exc
        if len(probe) < probe_bytes:
            raw_file.close()
            raise RuntimeError(f"External CABLE raw file probe was incomplete: {raw_path}")

        rms, peak = _pcm16_level_values(probe)
        log.warning(f"[audio] AUDIO_LEVEL: cable signal-probe rms={rms:.1f} peak={peak}")
        if not _pcm16_has_signal(probe):
            raw_file.close()
            raise RuntimeError(
                "CABLE Output is silent; route Windows output to CABLE Input "
                "(VB-Audio Virtual Cable) and play audio before recording"
            )

        self._protocol = "file"
        self._process = self._ExternalRawFileProcess()
        self._owns_process = False
        self._raw_path = raw_path
        self._raw_file = raw_file
        self._prefetched_chunks = [
            probe[index : index + self.CHUNK_BYTES]
            for index in range(0, len(probe), self.CHUNK_BYTES)
            if len(probe[index : index + self.CHUNK_BYTES]) == self.CHUNK_BYTES
        ]
        self.active = True
        log.info(f"AUDIO_DEVICE: cable-file -> CABLE Output (VB-Audio Virtual Cable) raw_file={raw_path}")
        log.warning("[audio] AUDIO_FORMAT: external ffmpeg dshow raw-file 16000Hz mono")
        log.info("Audio subprocess running (PID external)")

    def _pick_override_sounddevice_device(self, override):
        override = (override or "").strip()
        if not override:
            return None
        if override.isdigit():
            target = int(override)
            for device in self._devices:
                if device["index"] == target:
                    return device
            return None
        needle = override.lower()
        for device in self._devices:
            if needle in device["name"].lower():
                return device
        return None

    def _pick_override_ffmpeg_device(self, override):
        override = (override or "").strip()
        if not override:
            return None
        if override.isdigit():
            sounddevice_match = self._pick_override_sounddevice_device(override)
            if sounddevice_match is None:
                log.warning(f"AUDIO_WARN: override device index not found: {override}")
                return None
            override = sounddevice_match["name"]
        needle = override.lower()
        for item in self._ffmpeg_audio_devices:
            if needle in item["name"].lower() or needle in (item.get("alt") or "").lower():
                return item
        log.warning(f"AUDIO_WARN: override device name not found: {override}")
        return None

    def _score_ffmpeg_system_device(self, item):
        lowered = item["name"].lower()
        if not (self._is_system_name(lowered) or self._is_virtual_name(lowered)):
            return None
        score = 0
        if self._is_virtual_name(lowered):
            if "vb-audio virtual cable" in lowered:
                score += 600
            else:
                score += 520
        else:
            score += 400
        if "stereo mix" in lowered or "mezcla" in lowered:
            score += 80
        if "point" in lowered:
            score -= 50
        if item.get("alt"):
            score += 15
        return score

    def _ffmpeg_system_candidates(self):
        override = self._pick_override_ffmpeg_device(os.getenv("WHISPERFLOW_SYSTEM_DEVICE", ""))
        ranked = []
        for item in self._ffmpeg_audio_devices:
            score = self._score_ffmpeg_system_device(item)
            if score is not None:
                ranked.append((score, item))
        ranked.sort(key=lambda pair: pair[0], reverse=True)

        candidates = []
        seen = set()

        def add_candidate(source, item, target):
            key = (item["name"], target)
            if key in seen:
                return
            seen.add(key)
            candidates.append((source, item, target))

        def add_device(source, item):
            if item.get("alt"):
                add_candidate(source + ":alt", item, item["alt"])
            add_candidate(source, item, item["name"])

        if override is not None:
            add_device("override", override)
        for _, item in ranked:
            if override is not None and item["name"] == override["name"]:
                continue
            add_device("auto", item)
        return candidates

    def _start_system_capture(self):
        log.info("Starting audio capture (system)...")
        backend = os.getenv("WHISPERFLOW_SYSTEM_BACKEND", "auto").strip().lower()
        if backend not in ("auto", "ffmpeg", "sounddevice", "wasapi", "cable"):
            log.warning(f"AUDIO_WARN: unknown WHISPERFLOW_SYSTEM_BACKEND={backend}; using auto")
            backend = "auto"
        if backend in ("auto", "ffmpeg"):
            log.warning(
                "AUDIO_WARN: DirectShow/auto System Audio is experimental after WF-P3.1 NO-GO; "
                "use WHISPERFLOW_SYSTEM_BACKEND=cable for production validation"
            )
        if backend == "cable":
            self._start_system_cable_capture("WHISPERFLOW_SYSTEM_BACKEND=cable")
            return
        if backend == "wasapi":
            self._start_system_wasapi_capture("WHISPERFLOW_SYSTEM_BACKEND=wasapi")
            return
        if backend == "sounddevice":
            self._start_system_sounddevice_capture("WHISPERFLOW_SYSTEM_BACKEND=sounddevice")
            return

        ffmpeg_bin = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
        if not ffmpeg_bin:
            if backend == "auto":
                self._start_system_sounddevice_capture("ffmpeg not found in PATH")
                return
            raise RuntimeError("ffmpeg not found in PATH")
        if not self._ffmpeg_audio_devices:
            if backend == "auto":
                self._start_system_sounddevice_capture("ffmpeg dshow returned no audio devices")
                return
            raise RuntimeError("ffmpeg dshow returned no audio devices")

        failures = []
        for source, item, target_name in self._ffmpeg_system_candidates():
            clean_target = target_name.replace(chr(34), "")
            spec = f"audio={clean_target}"
            label = item["name"] if target_name == item["name"] else f"{item['name']} via {target_name}"
            attempts = [(None, spec)]
            for pin_name in self.COMMON_AUDIO_PIN_NAMES:
                attempts.append((pin_name, spec))
            for pin_name, current_spec in attempts:
                cmd = [
                    ffmpeg_bin,
                    "-hide_banner",
                    "-nostdin",
                    "-loglevel",
                    "warning",
                    "-f",
                    "dshow",
                ]
                if pin_name is not None:
                    cmd.extend(["-audio_pin_name", pin_name])
                cmd.extend([
                    "-i",
                    current_spec,
                    "-ac",
                    "1",
                    "-ar",
                    str(SAMPLE_RATE),
                    "-f",
                    "s16le",
                    "pipe:1",
                ])
                try:
                    process = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE)
                    time.sleep(1.2)
                    if process.poll() is not None:
                        err = process.stderr.read().decode(errors="replace").strip()
                        pin_suffix = f" pin={pin_name}" if pin_name is not None else ""
                        failures.append(f"{label}{pin_suffix}: {err[:160]}")
                        log.warning(f"AUDIO_WARN: rejected {label} spec={current_spec}{pin_suffix}: {err[:160]}")
                        continue

                    self._protocol = "raw"
                    self._process = process
                    threading.Thread(target=self._read_stderr, daemon=True).start()
                    self.active = True
                    if target_name == item["name"]:
                        log.info(f"AUDIO_DEVICE: {source} -> {item['name']} spec={current_spec} pin={pin_name or 'default'} (ffmpeg dshow)")
                    else:
                        log.info(f"AUDIO_DEVICE: {source} -> {item['name']} using alt={target_name} spec={current_spec} pin={pin_name or 'default'} (ffmpeg dshow)")
                    log.warning("[audio] AUDIO_FORMAT: ffmpeg dshow raw 16000Hz mono")
                    log.info(f"Audio subprocess running (PID {self._process.pid})")
                    return
                except Exception as exc:
                    pin_suffix = f" pin={pin_name}" if pin_name is not None else ""
                    failures.append(f"{label}{pin_suffix}: {exc}")
                    log.warning(f"AUDIO_WARN: rejected {label} spec={current_spec}{pin_suffix}: {exc}")

        ffmpeg_error = "System audio backend failed: " + " | ".join(failures[:4])
        if backend == "auto":
            try:
                self._start_system_sounddevice_capture("ffmpeg dshow could not open a capture pin")
                return
            except Exception as exc:
                raise RuntimeError(f"{ffmpeg_error} | sounddevice fallback failed: {exc}") from exc
        raise RuntimeError(ffmpeg_error)

    def _finalize_process_startup(self):
        time.sleep(1.0)
        if self._process.poll() is not None:
            err = self._process.stderr.read().decode(errors="replace").strip()
            raise RuntimeError(f"Audio subprocess failed: {err[:2000]}")
        threading.Thread(target=self._read_stderr, daemon=True).start()
        self.active = True
        log.info(f"Audio subprocess running (PID {self._process.pid})")

    def _read_stderr(self):
        try:
            for line in self._process.stderr:
                msg = line.decode(errors="replace").strip()
                if not msg:
                    continue
                if msg.startswith("AUDIO_DEVICE:"):
                    log.info(msg)
                elif msg.startswith("AUDIO_WARN:"):
                    log.warning(msg)
                else:
                    log.warning(f"[audio] {msg}")
        except Exception:
            pass

    def read_chunk(self) -> bytes:
        """Read one PCM16 chunk from subprocess pipe."""
        process = self._process
        if not self.active or not process:
            return b""
        process_ended = process.poll() is not None
        try:
            if self._protocol == "raw":
                if self._prefetched_chunks:
                    return self._prefetched_chunks.pop(0)
                if process_ended:
                    log.error("Audio subprocess died")
                    self.active = False
                    return b""
                data = process.stdout.read(self.CHUNK_BYTES)
                if not data or len(data) < self.CHUNK_BYTES:
                    self.active = False
                    return b""
                return data

            if self._protocol == "file":
                if self._prefetched_chunks:
                    return self._prefetched_chunks.pop(0)
                raw_file = self._raw_file
                raw_path = self._raw_path
                if raw_file is None or raw_path is None:
                    self.active = False
                    return b""
                while self.active:
                    try:
                        available = os.path.getsize(raw_path) - raw_file.tell()
                    except OSError:
                        available = 0
                    if available >= self.CHUNK_BYTES:
                        data = raw_file.read(self.CHUNK_BYTES)
                        if len(data) == self.CHUNK_BYTES:
                            return data
                    if process.poll() is not None:
                        self.active = False
                        return b""
                    time.sleep(0.05)
                return b""

            if process_ended:
                log.error("Audio subprocess died")
                self.active = False
                return b""
            header = process.stdout.read(4)
            if not header or len(header) < 4:
                self.active = False
                return b""
            length = struct.unpack("<I", header)[0]
            data = process.stdout.read(length)
            if len(data) < length:
                self.active = False
                return b""
            return data
        except Exception as exc:
            log.error(f"Pipe error: {exc}")
            self.active = False
            return b""

    def close(self):
        self.active = False
        self._prefetched_chunks = []
        raw_file = self._raw_file
        self._raw_file = None
        self._raw_path = None
        if raw_file:
            try:
                raw_file.close()
            except Exception:
                pass
        process = self._process
        owns_process = self._owns_process
        self._process = None
        self._owns_process = True
        if process and owns_process:
            try:
                if os.name == "nt" and getattr(process, "pid", None):
                    sp.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        stdout=sp.DEVNULL,
                        stderr=sp.DEVNULL,
                        timeout=3,
                    )
                    process.wait(timeout=3)
                else:
                    process.terminate()
                    process.wait(timeout=3)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
            log.info("Audio subprocess terminated")
        elif process:
            log.info("External audio file detached")


# =============================================================================
# WhisperFlow Cloud Client GUI
# =============================================================================

class WhisperFlowClient:
    """Enterprise-grade GUI client — modern dark UI v2 with animations."""

    RED = "#e94560"
    GREEN = "#0ead69"
    ACCENT = "#0f3460"
    MUTED = "#4a5568"
    CARD = "#16213e"
    YELLOW = "#f39c12"
    DIM = "#7f8c8d"
    TEXT = "#eaeaea"

    def __init__(self):
        self.server_url = DEFAULT_SERVER
        if AUTH_TOKEN:
            sep = "&" if "?" in self.server_url else "?"
            self.server_url = f"{self.server_url}{sep}token={AUTH_TOKEN}"

        self.is_recording = False
        self.is_connected = False
        self.websocket = None
        self.loop = None
        self._rec_start = 0
        self._timer_id = None
        self._pulse_id = None
        self._pulse_on = True
        self._stop_timeout_id = None
        self._awaiting_stop_ack = False
        self._session_segments = []
        self.engine = AudioEngine()
        self._build_gui()

    def _build_gui(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("WhisperFlow Cloud")
        self.root.geometry("500x600")
        self.root.resizable(False, False)

        main = ctk.CTkFrame(self.root, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=28, pady=24)

        # -- Header with version --
        hdr = ctk.CTkFrame(main, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(hdr, text="WhisperFlow",
                     font=("Segoe UI", 28, "bold")).pack(side="left")
        ctk.CTkLabel(hdr, text="CLOUD", font=("Segoe UI", 11, "bold"),
                     text_color=self.RED, anchor="s"
                     ).pack(side="left", padx=(6, 0), pady=(14, 0))
        ctk.CTkLabel(hdr, text="v3.1", font=("Segoe UI", 9),
                     text_color=self.MUTED, anchor="se"
                     ).pack(side="right", pady=(18, 0))

        # -- Status badge --
        sf = ctk.CTkFrame(main, fg_color=self.CARD, corner_radius=8, height=36)
        sf.pack(fill="x", pady=(0, 16))
        self.status_dot = ctk.CTkLabel(sf, text="", width=10, height=10,
                                       fg_color=self.YELLOW, corner_radius=5)
        self.status_dot.pack(side="left", padx=(12, 8), pady=8)
        self.status_label = ctk.CTkLabel(sf, text="Connecting...",
                                         font=("Segoe UI", 12), text_color=self.DIM)
        self.status_label.pack(side="left", pady=8)

        # -- Audio source --
        ctk.CTkLabel(main, text="AUDIO SOURCE", font=("Segoe UI", 10, "bold"),
                     text_color=self.MUTED).pack(anchor="w", pady=(0, 6))
        modes = (["Microphone", "System Audio"]
                 if self.engine.has_system_audio else ["Microphone"])
        self.mode_var = ctk.StringVar(value="Microphone")
        self.mode_sel = ctk.CTkSegmentedButton(
            main, values=modes, variable=self.mode_var,
            font=("Segoe UI", 13), corner_radius=8, height=38,
            selected_color=self.ACCENT, selected_hover_color="#1a4a7a")
        self.mode_sel.pack(fill="x", pady=(0, 20))

        # -- Record button --
        self.record_btn = ctk.CTkButton(
            main, text="RECORD", font=("Segoe UI", 20, "bold"),
            height=60, corner_radius=14,
            fg_color=self.RED, hover_color="#c0392b",
            command=self._toggle_recording, state="disabled")
        self.record_btn.pack(fill="x", pady=(0, 6))

        # Shortcut hint
        self.hint_label = ctk.CTkLabel(main, text="Press Space to record",
                                        font=("Segoe UI", 10), text_color=self.MUTED)
        self.hint_label.pack(pady=(0, 10))
        self.root.bind("<space>", lambda e: self._on_space())

        # -- Recording row: dot + label + timer --
        rec_row = ctk.CTkFrame(main, fg_color="transparent")
        rec_row.pack(fill="x", pady=(0, 8))
        self.rec_dot = ctk.CTkLabel(rec_row, text="", width=12, height=12,
                                     fg_color="transparent", corner_radius=6)
        self.rec_dot.pack(side="left", padx=(0, 8))
        self.rec_label = ctk.CTkLabel(rec_row, text="",
                                      font=("Segoe UI", 14, "bold"), text_color=self.RED)
        self.rec_label.pack(side="left")
        self.timer_label = ctk.CTkLabel(rec_row, text="",
                                        font=("Consolas", 14), text_color=self.DIM)
        self.timer_label.pack(side="right")

        # -- Transcription textbox --
        ctk.CTkLabel(main, text="TRANSCRIPTION", font=("Segoe UI", 10, "bold"),
                     text_color=self.MUTED).pack(anchor="w", pady=(0, 4))
        self.text_box = ctk.CTkTextbox(
            main, height=100, corner_radius=10,
            fg_color=self.CARD, text_color=self.DIM,
            font=("Segoe UI", 12), wrap="word",
            state="disabled", border_width=1, border_color="#2a3a5e")
        self.text_box.pack(fill="x", pady=(0, 12))
        self._set_textbox("Ready to transcribe")

        # -- Footer --
        host = self.server_url.split("//")[1].split("/")[0] if "//" in self.server_url else "local"
        ctk.CTkLabel(main, text=f"Server: {host}",
                     font=("Segoe UI", 9), text_color=self.MUTED
                     ).pack(side="bottom", pady=(4, 0))

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # --- UI helpers ---

    def _set_status(self, text, color=None):
        self.status_label.configure(text=text)
        self.status_dot.configure(fg_color=color or self.YELLOW)

    def _set_textbox(self, text, color=None):
        self.text_box.configure(state="normal", text_color=color or self.DIM)
        self.text_box.delete("1.0", "end")
        self.text_box.insert("1.0", text)
        self.text_box.configure(state="disabled")

    def _render_session_text(self):
        if self._session_segments:
            self._set_textbox("\n\n".join(self._session_segments), self.TEXT)
        else:
            self._set_textbox("Ready to transcribe", self.DIM)

    def _reset_session(self):
        self._session_segments = []
        self._render_session_text()

    def _on_space(self):
        if str(self.record_btn.cget("state")) == "normal":
            self._toggle_recording()

    def _start_timer(self):
        self._rec_start = time.time()
        self._update_timer()

    def _update_timer(self):
        if not self.is_recording:
            return
        elapsed = int(time.time() - self._rec_start)
        m, s = divmod(elapsed, 60)
        self.timer_label.configure(text=f"{m:02d}:{s:02d}")
        self._timer_id = self.root.after(1000, self._update_timer)

    def _start_pulse(self):
        self._pulse_on = True
        self._do_pulse()

    def _do_pulse(self):
        if not self.is_recording:
            self.rec_dot.configure(fg_color="transparent")
            return
        self.rec_dot.configure(fg_color=self.RED if self._pulse_on else "transparent")
        self._pulse_on = not self._pulse_on
        self._pulse_id = self.root.after(500, self._do_pulse)

    def _stop_animations(self):
        for tid in (self._timer_id, self._pulse_id):
            if tid:
                self.root.after_cancel(tid)
        self._timer_id = self._pulse_id = None
        self.rec_dot.configure(fg_color="transparent")

    def _cancel_stop_timeout(self):
        if self._stop_timeout_id:
            self.root.after_cancel(self._stop_timeout_id)
            self._stop_timeout_id = None

    def _finish_processing(self, label_text, label_color, hint_text=None):
        self._awaiting_stop_ack = False
        self._cancel_stop_timeout()
        self.rec_label.configure(text=label_text, text_color=label_color)
        self.hint_label.configure(
            text=hint_text or ("Ctrl+V to paste | Space to record again" if self._session_segments else "Press Space to record")
        )
        self.timer_label.configure(text="")
        self.record_btn.configure(state="normal")
        self.mode_sel.configure(state="normal")

    def _handle_session_stopped(self):
        if not self._awaiting_stop_ack:
            return
        if self._session_segments:
            self._finish_processing("Copied to clipboard!", self.GREEN)
        else:
            self._finish_processing("No valid transcription received", self.YELLOW)

    def _on_stop_timeout(self):
        if not self._awaiting_stop_ack:
            return
        log.warning("Finalization timeout: server did not confirm stop")
        self._finish_processing("Finalization timeout", self.YELLOW, "Server did not confirm stop; ready to record again")

    def _send_control(self, payload):
        if not _ws_is_open(self.websocket):
            return False
        future = asyncio.run_coroutine_threadsafe(self.websocket.send(json.dumps(payload)), self.loop)
        try:
            future.result(timeout=10)
            log.info(f"Sent control frame: {payload.get('type')}")
            return True
        except Exception as exc:
            log.warning(f"WebSocket control send failed: {exc}")
            return False

    def _send_audio_chunk(self, chunk):
        if not _ws_is_open(self.websocket):
            log.warning("WebSocket closed during capture")
            return False
        future = asyncio.run_coroutine_threadsafe(self.websocket.send(chunk), self.loop)
        try:
            future.result(timeout=10)
            return True
        except Exception as exc:
            log.warning(f"WebSocket audio send failed: {exc}")
            return False

    # --- Recording ---

    def _toggle_recording(self):
        if self.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        if not _ws_is_open(self.websocket):
            self.hint_label.configure(text="Reconnecting...")
            self.record_btn.configure(state="disabled")
            asyncio.run_coroutine_threadsafe(self._connect(), self.loop)
            self.root.after(1500, self._start_recording)
            return

        mode_text = self.mode_var.get()
        mode = "system" if mode_text == "System Audio" else "mic"
        self._cancel_stop_timeout()
        self._awaiting_stop_ack = False
        self._reset_session()
        self.is_recording = True
        self.record_btn.configure(text="STOP", fg_color=self.GREEN, hover_color="#0c8a54")
        self.rec_label.configure(text=f"RECORDING ({mode_text})", text_color=self.RED)
        self.hint_label.configure(text="Play audio..." if mode == "system" else "Speak now...")
        self.mode_sel.configure(state="disabled")
        self._start_timer()
        self._start_pulse()

        threading.Thread(target=self._capture_worker, args=(mode,), daemon=True).start()

    def _capture_worker(self, mode):
        chunks_sent = 0
        bytes_sent = 0
        cable_backend = mode == "system" and os.getenv("WHISPERFLOW_SYSTEM_BACKEND", "").strip().lower() == "cable"
        debug_wav = _debug_wav_path("system_cable" if cable_backend else mode, force=cable_backend)
        debug_chunks = [] if debug_wav else None
        t0 = time.time()

        try:
            if mode == "system":
                self.engine.open_loopback()
            else:
                self.engine.open_microphone()

            while self.is_recording and self.engine.active:
                chunk = self.engine.read_chunk()
                if not chunk:
                    break
                bytes_sent += len(chunk)
                chunks_sent += 1
                if debug_chunks is not None:
                    debug_chunks.append(chunk)
                if not self._send_audio_chunk(chunk):
                    break
                if chunks_sent % 10 == 0:
                    elapsed = time.time() - t0
                    log.info(f"Streaming: {chunks_sent} chunks ({bytes_sent / 1024:.0f} KB) in {elapsed:.1f}s")

        except Exception as e:
            log.error(f"Capture error: {e}")
            self.is_recording = False
            self._awaiting_stop_ack = False
            self.root.after(0, self._cancel_stop_timeout)
            err_msg = str(e)[:100]
            self.root.after(0, lambda m=err_msg: self.rec_label.configure(text=f"Audio error: {m}", text_color=self.RED))
            self.root.after(0, lambda: self.record_btn.configure(text="RECORD", fg_color=self.RED, state="normal"))
            self.root.after(0, lambda: self.mode_sel.configure(state="normal"))
            self.root.after(0, lambda: self.hint_label.configure(text="Press Space to record"))
            self.root.after(0, self._stop_animations)
        finally:
            self.engine.close()
            if debug_chunks is not None:
                _write_pcm16_wav(debug_wav, debug_chunks)

        elapsed = time.time() - t0
        log.info(f"Capture complete: {chunks_sent} chunks ({bytes_sent / 1024:.0f} KB) in {elapsed:.1f}s")
        if self._awaiting_stop_ack and _ws_is_open(self.websocket):
            self._send_control({"type": "stop"})

    def _stop_recording(self):
        self.is_recording = False
        self._awaiting_stop_ack = True
        self.engine.close()
        self._cancel_stop_timeout()
        self._stop_timeout_id = self.root.after(60000, self._on_stop_timeout)
        self._stop_animations()
        self.record_btn.configure(text="RECORD", fg_color=self.RED, hover_color="#c0392b", state="disabled")
        self.rec_label.configure(text="Processing...", text_color=self.YELLOW)
        self.hint_label.configure(text="Finalizing transcription...")

    # --- Transcription ---

    # Known Whisper hallucinations on silence/near-silence
    HALLUCINATIONS = {
        "subtítulos realizados por la comunidad de amara.org",
        "subtitulos realizados por la comunidad de amara.org",
        "thanks for watching",
        "thank you for watching",
        "gracias por ver",
        "suscríbete",
        "you",
    }

    def _is_hallucination(self, text: str) -> bool:
        return text.strip().lower().rstrip(".!") in self.HALLUCINATIONS

    def _append_text(self, text):
        """Append a final transcription segment to the session buffer."""
        normalized = " ".join(text.split()).strip()
        if not normalized:
            return
        if self._session_segments and self._session_segments[-1] == normalized:
            return
        self._session_segments.append(normalized)
        self._render_session_text()

    def _insert_text(self, text):
        """Handle a final (non-partial) transcription segment."""
        if self._is_hallucination(text):
            log.info(f"Filtered hallucination: {text}")
            return

        self._append_text(text)
        full_text = "\n\n".join(self._session_segments).strip()

        try:
            pyperclip.copy(full_text)
            if self.is_recording:
                mode_text = self.mode_var.get()
                self.rec_label.configure(text=f"RECORDING ({mode_text})", text_color=self.RED)
                self.hint_label.configure(text="Press Space to stop")
            elif not self._awaiting_stop_ack:
                self._finish_processing("Copied to clipboard!", self.GREEN)
        except Exception as e:
            self.rec_label.configure(text=f"Clipboard error: {str(e)[:40]}", text_color=self.RED)
            if not self.is_recording and not self._awaiting_stop_ack:
                self.record_btn.configure(state="normal")
                self.mode_sel.configure(state="normal")

    # --- WebSocket ---

    async def _connect(self):
        try:
            self.websocket = await websockets.connect(
                self.server_url, ping_interval=20, ping_timeout=10, open_timeout=30)
            self.is_connected = True
            log.info("Connected to server")
            self.root.after(0, lambda: self._set_status("Connected to Cloud", self.GREEN))
            self.root.after(0, lambda: self.record_btn.configure(state="normal"))
            await self._listen()
        except Exception as e:
            self.is_connected = False
            err_msg = str(e)[:50]
            log.error(f"Connection failed: {e}")
            self.root.after(0, lambda m=err_msg: self._set_status(f"Error: {m}", self.RED))

    async def _listen(self):
        try:
            async for msg in self.websocket:
                data = json.loads(msg)
                if data.get("type") == "session_started":
                    continue
                if data.get("type") == "session_stopped":
                    log.info("Received session_stopped")
                    self.root.after(0, self._handle_session_stopped)
                    continue
                text = data.get("data", {}).get("text", "").strip()
                if not text:
                    continue
                if data.get("is_partial"):
                    self.root.after(
                        0, lambda t=text: self.hint_label.configure(text=f"... {t[:80]}")
                    )
                else:
                    log.info(f"Transcribed: {text[:80]}")
                    self.root.after(0, lambda t=text: self._insert_text(t))
        except websockets.exceptions.ConnectionClosed:
            self.is_connected = False
            log.info("Server closed connection")
            self.root.after(0, lambda: self._set_status("Disconnected", self.RED))
            if self._awaiting_stop_ack:
                self.root.after(0, lambda: self._finish_processing("Connection closed before final confirmation", self.YELLOW))
            else:
                self.root.after(0, lambda: self.record_btn.configure(state="disabled"))
        except Exception as e:
            self.is_connected = False
            err_msg = str(e)[:40]
            log.error(f"Listen error: {e}")
            self.root.after(0, lambda m=err_msg: self._set_status(f"Disconnected: {m}", self.RED))
            self.root.after(0, lambda: self.record_btn.configure(state="disabled"))

    # --- Lifecycle ---

    def _on_close(self):
        log.info("Shutting down...")
        self.is_recording = False
        self._stop_animations()
        self.engine.close()
        if self.websocket:
            asyncio.run_coroutine_threadsafe(self.websocket.close(), self.loop)
        self.root.destroy()

    def run(self):
        def start_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self._connect())
            self.loop.run_forever()

        threading.Thread(target=start_loop, daemon=True).start()
        self.root.mainloop()


# =============================================================================
# Entry Point
# =============================================================================

def main():
    log.info("WhisperFlow Cloud Client v3.1 starting...")
    log.info("Audio engine: isolated sounddevice subprocess")
    client = WhisperFlowClient()
    client.run()


if __name__ == "__main__":
    main()
