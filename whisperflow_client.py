#!/usr/bin/env python3
"""
WhisperFlow Cloud Client v2.0 — Enterprise-Grade Windows Native
Dual mode: Microphone + System Audio (Stereo Mix / WASAPI Loopback)
Audio engine: sounddevice (PortAudio CFFI) with fallback chain
Connects via WSS to Cloud Run server with token auth.
"""

import asyncio
import json
import logging
import os
import threading
import time
import tkinter as tk
from tkinter import ttk

import numpy as np
import pyperclip
import sounddevice as sd
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
TARGET_SAMPLE_RATE = 16000  # OpenAI Whisper expects 16kHz mono PCM16
BLOCK_SIZE = 4096  # Samples per read block


# =============================================================================
# WebSocket helpers (compatible with websockets v13–v15+)
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
# Audio Device Discovery
# =============================================================================

class AudioDeviceManager:
    """Discovers and categorises available audio devices."""

    SYSTEM_AUDIO_KEYWORDS = ["stereo mix", "mezcla estéreo", "loopback", "what u hear"]
    MIC_EXCLUDE_KEYWORDS = ["loopback", "mezcla", "stereo mix", "cable", "virtual"]

    def __init__(self):
        self.devices = sd.query_devices()
        self._log_devices()

    def _log_devices(self):
        log.info("--- Audio Devices ---")
        for i, d in enumerate(self.devices):
            if d["max_input_channels"] > 0:
                api = sd.query_hostapis(d["hostapi"])["name"]
                log.info(
                    f"  [{i}] {d['name']} ({api}) "
                    f"ch={d['max_input_channels']} rate={int(d['default_samplerate'])}"
                )
        log.info("--- End Devices ---")

    def find_microphone(self) -> dict:
        """Find the best microphone: prefer WASAPI, fallback to default."""
        # Strategy 1: WASAPI mic (lowest latency, best quality)
        wasapi_mics = self._find_by_api("WASAPI", is_loopback=False)
        if wasapi_mics:
            chosen = wasapi_mics[0]
            log.info(f"Mic selected (WASAPI): [{chosen['index']}] {chosen['name']}")
            return chosen

        # Strategy 2: System default input
        default_idx = sd.default.device[0]
        if default_idx is not None and default_idx >= 0:
            info = self.devices[default_idx]
            log.info(f"Mic selected (default): [{default_idx}] {info['name']}")
            return {**info, "index": default_idx}

        raise RuntimeError("No microphone found on this system")

    def find_system_audio(self) -> dict:
        """Find the best system audio capture device."""
        # Strategy 1: WASAPI Loopback (captures from active output)
        loopbacks = self._find_by_api("WASAPI", is_loopback=True)
        if loopbacks:
            chosen = loopbacks[0]
            log.info(f"System audio selected (Loopback): [{chosen['index']}] {chosen['name']}")
            return chosen

        # Strategy 2: Stereo Mix / Mezcla estéreo (any API)
        for i, d in enumerate(self.devices):
            name_lower = d["name"].lower()
            if d["max_input_channels"] > 0 and any(
                kw in name_lower for kw in self.SYSTEM_AUDIO_KEYWORDS
            ):
                log.info(f"System audio selected (Stereo Mix): [{i}] {d['name']}")
                return {**d, "index": i}

        raise RuntimeError(
            "No system audio device found. Enable 'Stereo Mix' in Windows Sound settings "
            "or connect an audio output device."
        )

    def _find_by_api(self, api_name: str, is_loopback: bool) -> list:
        """Find input devices filtered by host API and loopback status."""
        results = []
        for i, d in enumerate(self.devices):
            if d["max_input_channels"] <= 0:
                continue
            api = sd.query_hostapis(d["hostapi"])["name"]
            if api_name not in api:
                continue

            name_lower = d["name"].lower()
            has_loopback_keyword = any(
                kw in name_lower for kw in self.SYSTEM_AUDIO_KEYWORDS
            )

            if is_loopback and has_loopback_keyword:
                results.append({**d, "index": i})
            elif not is_loopback and not has_loopback_keyword:
                # Exclude virtual/cable devices for mic
                if not any(kw in name_lower for kw in self.MIC_EXCLUDE_KEYWORDS):
                    results.append({**d, "index": i})

        return results


# =============================================================================
# Audio Capture Engine (sounddevice-based)
# =============================================================================

class AudioSource:
    """Enterprise-grade audio capture with resampling pipeline."""

    def __init__(self, device_info: dict):
        self.device_index = device_info["index"]
        self.device_name = device_info["name"]
        self.source_rate = int(device_info["default_samplerate"])
        self.channels = int(device_info["max_input_channels"])
        self.stream = None

    def open(self):
        log.info(
            f"Opening: [{self.device_index}] {self.device_name} "
            f"@ {self.source_rate}Hz ch={self.channels}"
        )
        self.stream = sd.InputStream(
            samplerate=self.source_rate,
            channels=self.channels,
            dtype="int16",
            device=self.device_index,
            blocksize=BLOCK_SIZE,
        )
        self.stream.start()
        log.info("Audio stream opened OK")

    def read_chunk(self) -> bytes:
        """Read audio chunk → mono 16kHz PCM16 bytes (OpenAI-ready)."""
        data, overflowed = self.stream.read(BLOCK_SIZE)
        if overflowed:
            log.debug("Audio buffer overflow (non-critical)")

        # data shape: (BLOCK_SIZE, channels) as int16 numpy array
        audio = data.astype(np.float32)

        # Stereo → mono: average channels
        if self.channels > 1:
            audio = audio.mean(axis=1)
        else:
            audio = audio.flatten()

        # Resample if needed (e.g. 44100/48000 → 16000)
        if self.source_rate != TARGET_SAMPLE_RATE:
            ratio = TARGET_SAMPLE_RATE / self.source_rate
            new_length = int(len(audio) * ratio)
            indices = np.arange(new_length) / ratio
            idx_floor = np.clip(indices.astype(int), 0, len(audio) - 1)
            idx_ceil = np.clip(idx_floor + 1, 0, len(audio) - 1)
            frac = indices - idx_floor
            audio = audio[idx_floor] * (1 - frac) + audio[idx_ceil] * frac

        # Float32 → PCM16 bytes
        pcm16 = np.clip(audio, -32768, 32767).astype(np.int16)
        return pcm16.tobytes()

    def close(self):
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
            log.info("Audio stream closed")


# =============================================================================
# WhisperFlow Cloud Client GUI
# =============================================================================

class WhisperFlowClient:
    """Enterprise-grade GUI client for WhisperFlow Cloud."""

    def __init__(self):
        self.server_url = DEFAULT_SERVER
        if AUTH_TOKEN:
            sep = "&" if "?" in self.server_url else "?"
            self.server_url = f"{self.server_url}{sep}token={AUTH_TOKEN}"

        self.is_recording = False
        self.is_connected = False
        self.websocket = None
        self.audio_source = None
        self.loop = None

        # Discover audio devices at startup
        self.device_mgr = AudioDeviceManager()
        self.has_system_audio = False
        try:
            self.device_mgr.find_system_audio()
            self.has_system_audio = True
        except RuntimeError:
            log.warning("System audio capture not available")

        self._build_gui()

    def _build_gui(self):
        self.root = tk.Tk()
        self.root.title("WhisperFlow Cloud")
        self.root.geometry("440x400")
        self.root.resizable(False, False)

        style = ttk.Style()
        style.theme_use("clam")

        main = ttk.Frame(self.root, padding="20")
        main.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            main, text="WhisperFlow Cloud", font=("Arial", 16, "bold")
        ).pack(pady=(0, 10))

        # Audio source selector
        mode_frame = ttk.LabelFrame(main, text="Audio Source", padding="10")
        mode_frame.pack(fill=tk.X, pady=(0, 10))

        self.mode_var = tk.StringVar(value="mic")
        ttk.Radiobutton(
            mode_frame, text="Microphone", variable=self.mode_var, value="mic"
        ).pack(side=tk.LEFT, padx=10)

        sys_label = "System Audio" if self.has_system_audio else "System Audio (N/A)"
        sys_rb = ttk.Radiobutton(
            mode_frame, text=sys_label, variable=self.mode_var, value="system"
        )
        sys_rb.pack(side=tk.LEFT, padx=10)
        if not self.has_system_audio:
            sys_rb.configure(state=tk.DISABLED)

        # Connection status
        self.status_label = ttk.Label(main, text="Connecting...", font=("Arial", 10))
        self.status_label.pack(pady=5)

        # Record button
        self.record_btn = tk.Button(
            main,
            text="RECORD",
            font=("Arial", 14, "bold"),
            bg="#e74c3c",
            fg="white",
            activebackground="#c0392b",
            activeforeground="white",
            height=2,
            width=18,
            command=self._toggle_recording,
            state=tk.DISABLED,
        )
        self.record_btn.pack(pady=10)

        # Recording indicator
        self.rec_label = ttk.Label(
            main, text="", font=("Arial", 12, "bold"), foreground="#e74c3c"
        )
        self.rec_label.pack(pady=5)

        # Transcription display
        self.text_label = ttk.Label(
            main, text="", font=("Arial", 9), foreground="#555", wraplength=400
        )
        self.text_label.pack(pady=5)

        # Server info
        host = self.server_url.split("//")[1].split("/")[0] if "//" in self.server_url else "local"
        ttk.Label(
            main, text=f"Server: {host}", font=("Arial", 8), foreground="#999"
        ).pack(side=tk.BOTTOM, pady=5)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # --- Recording Controls ---

    def _toggle_recording(self):
        if self.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        if not _ws_is_open(self.websocket):
            self.text_label.config(text="Reconnecting...")
            self.record_btn.config(state=tk.DISABLED)
            asyncio.run_coroutine_threadsafe(self._connect(), self.loop)
            self.root.after(1500, self._start_recording)
            return

        mode = self.mode_var.get()
        try:
            if mode == "system":
                device_info = self.device_mgr.find_system_audio()
            else:
                device_info = self.device_mgr.find_microphone()

            self.audio_source = AudioSource(device_info)
            self.audio_source.open()
        except Exception as e:
            log.error(f"Failed to open audio: {e}")
            self.text_label.config(text=f"Audio error: {str(e)[:80]}")
            return

        self.is_recording = True
        self.record_btn.config(text="STOP", bg="#27ae60", activebackground="#229954")
        src = "System Audio" if mode == "system" else "Microphone"
        self.rec_label.config(text=f"RECORDING ({src})...")
        prompt = "Play audio..." if mode == "system" else "Speak now..."
        self.text_label.config(text=prompt)

        threading.Thread(target=self._capture_loop, daemon=True).start()

    def _stop_recording(self):
        self.is_recording = False
        if self.audio_source:
            self.audio_source.close()
            self.audio_source = None

        self.record_btn.config(
            text="RECORD", bg="#e74c3c", activebackground="#c0392b", state=tk.DISABLED
        )
        self.rec_label.config(text="Processing...")
        self.text_label.config(text="Waiting for transcription...")

    def _capture_loop(self):
        """Continuous audio capture → WebSocket send loop."""
        chunks_sent = 0
        bytes_sent = 0
        t0 = time.time()

        try:
            while self.is_recording and self.audio_source and self.audio_source.stream:
                chunk = self.audio_source.read_chunk()
                bytes_sent += len(chunk)
                chunks_sent += 1

                if _ws_is_open(self.websocket):
                    asyncio.run_coroutine_threadsafe(
                        self.websocket.send(chunk), self.loop
                    )
                else:
                    log.warning("WebSocket closed during capture")
                    break

                if chunks_sent % 20 == 0:
                    elapsed = time.time() - t0
                    log.info(
                        f"Streaming: {chunks_sent} chunks "
                        f"({bytes_sent / 1024:.0f} KB) in {elapsed:.1f}s"
                    )

        except sd.PortAudioError as e:
            log.warning(f"Audio stream ended: {e}")
        except Exception as e:
            log.error(f"Capture error: {e}")
            self.root.after(
                0, lambda: self.text_label.config(text=f"Error: {str(e)[:60]}")
            )

        elapsed = time.time() - t0
        log.info(
            f"Capture complete: {chunks_sent} chunks "
            f"({bytes_sent / 1024:.0f} KB) in {elapsed:.1f}s"
        )

    # --- Transcription Handling ---

    def _insert_text(self, text: str):
        """Copy transcribed text to clipboard."""
        try:
            pyperclip.copy(text)
            display = text[:120] + "..." if len(text) > 120 else text
            self.text_label.config(text=f"Copied: {display}")
            self.rec_label.config(text="Press Ctrl+V to paste")
            self.record_btn.config(state=tk.NORMAL)
        except Exception as e:
            self.text_label.config(text=f"Clipboard error: {str(e)[:60]}")
            self.record_btn.config(state=tk.NORMAL)

    # --- WebSocket Connection ---

    async def _connect(self):
        try:
            self.websocket = await websockets.connect(
                self.server_url,
                ping_interval=20,
                ping_timeout=10,
            )
            self.is_connected = True
            log.info("Connected to server")
            self.root.after(0, lambda: self.status_label.config(text="Connected to Cloud"))
            self.root.after(0, lambda: self.record_btn.config(state=tk.NORMAL))
            await self._listen()
        except Exception as e:
            self.is_connected = False
            log.error(f"Connection failed: {e}")
            self.root.after(
                0, lambda: self.status_label.config(text=f"Error: {str(e)[:50]}")
            )

    async def _listen(self):
        """Listen for transcription results from server."""
        try:
            async for msg in self.websocket:
                data = json.loads(msg)
                text = data.get("data", {}).get("text", "").strip()
                if not text:
                    continue

                if data.get("is_partial"):
                    self.root.after(
                        0,
                        lambda t=text: self.text_label.config(text=f"... {t[:100]}"),
                    )
                else:
                    log.info(f"Transcribed: {text[:80]}")
                    self.root.after(0, lambda t=text: self._insert_text(t))

        except websockets.exceptions.ConnectionClosed:
            log.info("Server closed connection")
        except Exception as e:
            self.is_connected = False
            log.error(f"Listen error: {e}")
            self.root.after(
                0, lambda: self.status_label.config(text=f"Disconnected: {str(e)[:40]}")
            )
            self.root.after(0, lambda: self.record_btn.config(state=tk.DISABLED))

    # --- Lifecycle ---

    def _on_close(self):
        log.info("Shutting down...")
        self.is_recording = False
        if self.audio_source:
            self.audio_source.close()
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
    log.info("WhisperFlow Cloud Client v2.0 starting...")
    client = WhisperFlowClient()
    client.run()


if __name__ == "__main__":
    main()
