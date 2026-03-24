#!/usr/bin/env python3
"""
WhisperFlow Cloud Client v3.0 — Enterprise-Grade Windows Native

Audio engine: isolated `sounddevice` subprocess.
The GUI process never imports audio libraries directly, which avoids
the Windows 11 COM/PortAudio conflicts seen in tkinter-based clients.

Dual mode: Microphone + System Audio (when a loopback device exists)
Transport: WSS to Cloud Run with token auth
"""

import asyncio
import json
import logging
import os
import struct
import sys
import threading
import time
import subprocess as sp

import customtkinter as ctk
tk = ctk
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


# =============================================================================
# Audio Engine — Isolated subprocess (python -c + sounddevice)
# =============================================================================

# Audio capture subprocess script. Runs in its own python -c process
# with zero COM conflicts because the parent process never imports audio libs.
_AUDIO_SUBPROCESS = r'''
import os, sys, struct, json, sounddevice as sd, numpy as np

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
        if not _is_system(name):
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
        return None

    needle = override.lower()
    for payload in payloads:
        if needle in payload["name"].lower():
            return payload

    sys.stderr.write(f"AUDIO_WARN: override device name not found: {override}\n")
    return None


def _probe_device(payload):
    try:
        probe_frames = min(int(payload["rate"] * 0.1), 4800)
        audio = sd.rec(
            probe_frames,
            samplerate=payload["rate"],
            channels=1,
            dtype="int16",
            device=payload["index"],
        )
        sd.wait()
        if audio is None or len(audio) == 0:
            raise RuntimeError("empty probe capture")
        return True, None
    except Exception as exc:
        return False, str(exc)


def _choose_device(mode):
    payloads = [
        _device_payload(index, device)
        for index, device in enumerate(sd.query_devices())
        if device["max_input_channels"] > 0
    ]

    env_name = "WHISPERFLOW_SYSTEM_DEVICE" if mode == "system" else "WHISPERFLOW_INPUT_DEVICE"
    override = _pick_override(payloads, os.getenv(env_name, ""))

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
        candidates.append(("override", override))
    for _, payload in ranked:
        if override is not None and payload["index"] == override["index"]:
            continue
        candidates.append(("auto", payload))

    failures = []
    for source, payload in candidates:
        ok, error = _probe_device(payload)
        if ok:
            sys.stderr.write(
                f"AUDIO_DEVICE: {source} -> [{payload['index']}] {payload['name']} ({payload['api']} {payload['rate']}Hz)\n"
            )
            return payload
        failures.append(f"[{payload['index']}] {payload['name']}: {error}")
        sys.stderr.write(
            f"AUDIO_WARN: rejected [{payload['index']}] {payload['name']}: {error}\n"
        )

    raise RuntimeError("No working input device found: " + " | ".join(failures[:5]))


cmd = sys.argv[1]  # "list", "mic", or "system"

if cmd == "list":
    devices = sd.query_devices()
    result = {"default_input": sd.default.device[0], "devices": []}
    for i, d in enumerate(devices):
        if d["max_input_channels"] > 0:
            result["devices"].append(_device_payload(i, d))
    print(json.dumps(result))
    sys.exit(0)

chosen = _choose_device(cmd)
device = chosen["index"]
rate = chosen["rate"]
channels = 1
chunk_frames = max(4096, int(rate * 0.1))
target = 16000

try:
    # CRITICAL: Use sd.rec() not sd.InputStream().
    # sd.InputStream fails on Windows 11 due to PortAudio COM conflict.
    # sd.rec() is the ONLY sounddevice API verified working on this system.
    sys.stderr.write(
        f"AUDIO_FORMAT: device={device} rate={rate} channels={channels} frames={chunk_frames}\n"
    )
    while True:
        data = sd.rec(chunk_frames, samplerate=rate, channels=channels,
                      dtype="int16", device=device)
        sd.wait()

        audio = data.astype(np.float32)
        if channels > 1:
            audio = audio.mean(axis=1)
        else:
            audio = audio.flatten()

        if rate != target:
            ratio = target / rate
            n = int(len(audio) * ratio)
            idx = np.arange(n) / ratio
            audio = audio[np.clip(idx.astype(int), 0, len(audio) - 1)]

        pcm = np.clip(audio, -32768, 32767).astype(np.int16).tobytes()
        sys.stdout.buffer.write(struct.pack("<I", len(pcm)))
        sys.stdout.buffer.write(pcm)
        sys.stdout.buffer.flush()
except KeyboardInterrupt:
    pass
except Exception as e:
    sys.stderr.write(f"AUDIO_ERROR: {e}\n")
    sys.stderr.flush()
    sys.exit(1)
'''

class AudioEngine:
    """Process-isolated audio capture — parent never imports audio libraries.

    Architecture (solves COM apartment model conflict on Windows 11):
      Parent process: tkinter GUI + WebSocket (zero audio imports)
      Child process:  python -c with sounddevice (proven working via MME)

    This works because python -c with sounddevice is the ONLY method
    verified to reliably capture audio on this Windows 11 system.
    """

    CHUNK_BYTES = SAMPLE_RATE * 2  # 1 second of 16kHz mono PCM16

    def __init__(self):
        self.active = False
        self._process = None
        self._devices = []
        self._has_system_audio = False
        self._discover()

    def _discover(self):
        """Enumerate devices via sounddevice in a subprocess."""
        log.info("--- Audio Devices ---")
        try:
            result = sp.run(
                [sys.executable, "-c", _AUDIO_SUBPROCESS, "list"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                for d in data["devices"]:
                    name_lower = d["name"].lower()
                    is_system = "mezcla" in name_lower or "stereo mix" in name_lower
                    is_virtual = any(kw in name_lower for kw in ["cable", "virtual", "vb-audio"])
                    if is_system:
                        self._has_system_audio = True
                        label = "SYSTEM"
                    elif is_virtual:
                        label = "VIRTUAL"
                    else:
                        label = "MIC"
                    self._devices.append(d)
                    log.info(f"  {label}: [{d['index']}] {d['name']} ({d['api']} {d['rate']}Hz)")
            else:
                log.error(f"Device discovery failed: {result.stderr[:200]}")
        except Exception as e:
            log.error(f"Device discovery error: {e}")
        log.info("--- End Devices ---")

    @property
    def has_system_audio(self) -> bool:
        return self._has_system_audio

    def open_microphone(self):
        self._start_capture("mic")

    def open_loopback(self):
        self._start_capture("system")

    def _start_capture(self, mode: str):
        """Launch audio capture subprocess."""
        log.info(f"Starting audio capture ({mode})...")

        self._process = sp.Popen(
            [sys.executable, "-c", _AUDIO_SUBPROCESS, mode],
            stdout=sp.PIPE,
            stderr=sp.PIPE,
        )

        # Wait briefly to catch immediate startup failures before a background
        # stderr reader drains the diagnostic message.
        import time as _time
        _time.sleep(1.0)
        if self._process.poll() is not None:
            err = self._process.stderr.read().decode(errors="replace").strip()
            raise RuntimeError(f"Audio subprocess failed: {err[:200]}")

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
        if not self.active or not self._process:
            return b""
        if self._process.poll() is not None:
            log.error("Audio subprocess died")
            self.active = False
            return b""
        try:
            header = self._process.stdout.read(4)
            if not header or len(header) < 4:
                self.active = False
                return b""
            length = struct.unpack("<I", header)[0]
            data = self._process.stdout.read(length)
            if len(data) < length:
                self.active = False
                return b""
            return data
        except Exception as e:
            log.error(f"Pipe error: {e}")
            self.active = False
            return b""

    def close(self):
        self.active = False
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=3)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None
            log.info("Audio subprocess terminated")


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
        ctk.CTkLabel(hdr, text="v3.0", font=("Segoe UI", 9),
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

    # --- Recording ---

    def _toggle_recording(self):
        if self.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        if not _ws_is_open(self.websocket):
            self._set_textbox("Reconnecting...")
            self.record_btn.configure(state="disabled")
            asyncio.run_coroutine_threadsafe(self._connect(), self.loop)
            self.root.after(1500, self._start_recording)
            return

        mode_text = self.mode_var.get()
        mode = "system" if mode_text == "System Audio" else "mic"
        self.is_recording = True
        self.record_btn.configure(text="STOP", fg_color=self.GREEN, hover_color="#0c8a54")
        self.rec_label.configure(text=f"RECORDING ({mode_text})", text_color=self.RED)
        self.hint_label.configure(text="Press Space to stop")
        self._set_textbox("Play audio..." if mode == "system" else "Speak now...", self.TEXT)
        self.mode_sel.configure(state="disabled")
        self._start_timer()
        self._start_pulse()

        threading.Thread(target=self._capture_worker, args=(mode,), daemon=True).start()

    def _capture_worker(self, mode):
        chunks_sent = 0
        bytes_sent = 0
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
                if _ws_is_open(self.websocket):
                    asyncio.run_coroutine_threadsafe(self.websocket.send(chunk), self.loop)
                else:
                    log.warning("WebSocket closed during capture")
                    break
                if chunks_sent % 10 == 0:
                    elapsed = time.time() - t0
                    log.info(f"Streaming: {chunks_sent} chunks ({bytes_sent / 1024:.0f} KB) in {elapsed:.1f}s")

        except Exception as e:
            log.error(f"Capture error: {e}")
            err_msg = str(e)[:100]
            self.root.after(0, lambda m=err_msg: self._set_textbox(f"Audio error: {m}", self.RED))
            self.root.after(0, lambda: self.rec_label.configure(text=""))
            self.root.after(0, lambda: self.record_btn.configure(text="RECORD", fg_color=self.RED, state="normal"))
            self.root.after(0, lambda: self.mode_sel.configure(state="normal"))
            self.root.after(0, lambda: self.hint_label.configure(text="Press Space to record"))
            self.root.after(0, self._stop_animations)
        finally:
            self.engine.close()

        elapsed = time.time() - t0
        log.info(f"Capture complete: {chunks_sent} chunks ({bytes_sent / 1024:.0f} KB) in {elapsed:.1f}s")

    def _stop_recording(self):
        self.is_recording = False
        self._stop_animations()
        self.record_btn.configure(text="RECORD", fg_color=self.RED, hover_color="#c0392b", state="disabled")
        self.rec_label.configure(text="Processing...", text_color=self.YELLOW)
        self.hint_label.configure(text="")
        self._set_textbox("Waiting for transcription...", self.DIM)

    # --- Transcription ---

    def _insert_text(self, text):
        try:
            pyperclip.copy(text)
            self._set_textbox(text, self.TEXT)
            self.rec_label.configure(text="Copied to clipboard!", text_color=self.GREEN)
            self.hint_label.configure(text="Ctrl+V to paste | Space to record again")
            self.timer_label.configure(text="")
            self.record_btn.configure(state="normal")
            self.mode_sel.configure(state="normal")
        except Exception as e:
            self._set_textbox(f"Clipboard error: {str(e)[:60]}", self.RED)
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
                text = data.get("data", {}).get("text", "").strip()
                if not text:
                    continue
                if data.get("is_partial"):
                    self.root.after(0, lambda t=text: self._set_textbox(f"... {t[:150]}", self.DIM))
                else:
                    log.info(f"Transcribed: {text[:80]}")
                    self.root.after(0, lambda t=text: self._insert_text(t))
        except websockets.exceptions.ConnectionClosed:
            log.info("Server closed connection")
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
    log.info("WhisperFlow Cloud Client v3.0 starting...")
    log.info("Audio engine: isolated sounddevice subprocess")
    client = WhisperFlowClient()
    client.run()


if __name__ == "__main__":
    main()
