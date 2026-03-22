#!/usr/bin/env python3
"""
WhisperFlow Cloud Client — Windows Native
Dual mode: Microphone + System Audio (WASAPI Loopback)
Connects via WSS to Cloud Run server.
"""

import asyncio
import audioop
import json
import os
import queue
import struct
import threading
import time
import tkinter as tk
from tkinter import ttk
from typing import Optional

import pyperclip
import websockets

# Try PyAudioWPatch first (WASAPI loopback support), fall back to PyAudio
try:
    import pyaudiowpatch as pyaudio
    HAS_WASAPI_LOOPBACK = True
except ImportError:
    import pyaudio
    HAS_WASAPI_LOOPBACK = False

# --- Configuration ---
DEFAULT_SERVER = os.getenv(
    "WHISPERFLOW_SERVER",
    "wss://whisperflow-server-518312107738.us-central1.run.app/ws",
)
AUTH_TOKEN = os.getenv("WHISPERFLOW_AUTH_TOKEN", "")
TARGET_SAMPLE_RATE = 16000  # OpenAI expects 16kHz mono PCM16


class AudioSource:
    """Manages audio capture from microphone or system audio."""

    def __init__(self, pa: pyaudio.PyAudio, mode: str = "mic"):
        self.pa = pa
        self.mode = mode  # "mic" or "system"
        self.stream = None
        self.device_info = None
        self.source_rate = TARGET_SAMPLE_RATE
        self.channels = 1

    def open(self):
        if self.mode == "system":
            return self._open_system()
        return self._open_mic()

    def _open_mic(self):
        """Open default microphone at 16kHz mono."""
        self.source_rate = TARGET_SAMPLE_RATE
        self.channels = 1
        self.stream = self.pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=TARGET_SAMPLE_RATE,
            input=True,
            frames_per_buffer=4096,
        )
        return True

    def _open_system(self):
        """Open WASAPI loopback (system audio) via PyAudioWPatch."""
        if not HAS_WASAPI_LOOPBACK:
            raise RuntimeError(
                "PyAudioWPatch not installed. Run: pip install PyAudioWPatch"
            )

        self.device_info = self.pa.get_default_wasapi_loopback()
        self.source_rate = int(self.device_info["defaultSampleRate"])
        self.channels = self.device_info["maxInputChannels"]

        self.stream = self.pa.open(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.source_rate,
            input=True,
            input_device_index=self.device_info["index"],
            frames_per_buffer=4096,
        )
        return True

    def read_chunk(self) -> bytes:
        """Read a chunk and return 16kHz mono PCM16 bytes."""
        raw = self.stream.read(4096, exception_on_overflow=False)

        # Convert stereo to mono if needed
        if self.channels > 1:
            raw = audioop.tomono(raw, 2, 1, 1)

        # Resample if source rate differs from 16kHz
        if self.source_rate != TARGET_SAMPLE_RATE:
            raw, _ = audioop.ratecv(
                raw, 2, 1, self.source_rate, TARGET_SAMPLE_RATE, None
            )

        return raw

    def close(self):
        if self.stream:
            try:
                if self.stream.is_active():
                    self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
            self.stream = None


class WhisperFlowClient:
    """GUI client for WhisperFlow Cloud with dual audio mode."""

    def __init__(self):
        self.server_url = DEFAULT_SERVER
        if AUTH_TOKEN:
            sep = "&" if "?" in self.server_url else "?"
            self.server_url = f"{self.server_url}{sep}token={AUTH_TOKEN}"

        self.is_recording = False
        self.is_connected = False
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.audio_mode = "mic"  # "mic" or "system"

        self.pa = pyaudio.PyAudio()
        self.audio_source: Optional[AudioSource] = None
        self.loop = None

        self._build_gui()

    def _build_gui(self):
        self.root = tk.Tk()
        self.root.title("WhisperFlow Cloud")
        self.root.geometry("420x380")
        self.root.resizable(False, False)

        style = ttk.Style()
        style.theme_use("clam")

        main = ttk.Frame(self.root, padding="20")
        main.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main, text="WhisperFlow Cloud", font=("Arial", 16, "bold")).pack(
            pady=(0, 10)
        )

        # Audio mode selector
        mode_frame = ttk.LabelFrame(main, text="Audio Source", padding="10")
        mode_frame.pack(fill=tk.X, pady=(0, 10))

        self.mode_var = tk.StringVar(value="mic")
        ttk.Radiobutton(
            mode_frame, text="Microphone", variable=self.mode_var, value="mic"
        ).pack(side=tk.LEFT, padx=10)

        system_label = "System Audio (WASAPI)" if HAS_WASAPI_LOOPBACK else "System Audio (not available)"
        system_rb = ttk.Radiobutton(
            mode_frame,
            text=system_label,
            variable=self.mode_var,
            value="system",
        )
        system_rb.pack(side=tk.LEFT, padx=10)
        if not HAS_WASAPI_LOOPBACK:
            system_rb.configure(state=tk.DISABLED)

        # Status
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

        # Transcription
        self.text_label = ttk.Label(
            main, text="", font=("Arial", 9), foreground="#555", wraplength=380
        )
        self.text_label.pack(pady=5)

        # Server info
        host = self.server_url.split("//")[1].split("/")[0] if "//" in self.server_url else "local"
        ttk.Label(
            main,
            text=f"Server: {host}",
            font=("Arial", 8),
            foreground="#999",
        ).pack(side=tk.BOTTOM, pady=5)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _toggle_recording(self):
        if self.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        # Reconnect if needed
        if not self.websocket or self.websocket.closed:
            self.text_label.config(text="Reconnecting...")
            self.record_btn.config(state=tk.DISABLED)
            asyncio.run_coroutine_threadsafe(self._connect(), self.loop)
            self.root.after(1500, self._start_recording)
            return

        self.audio_mode = self.mode_var.get()
        self.audio_source = AudioSource(self.pa, self.audio_mode)

        try:
            self.audio_source.open()
        except Exception as e:
            self.text_label.config(text=f"Audio error: {str(e)[:80]}")
            return

        self.is_recording = True
        self.record_btn.config(text="STOP", bg="#27ae60", activebackground="#229954")
        src = "System Audio" if self.audio_mode == "system" else "Microphone"
        self.rec_label.config(text=f"RECORDING ({src})...")
        self.text_label.config(text="Speak now..." if self.audio_mode == "mic" else "Play audio...")

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
        """Capture audio and send to server."""
        chunks_sent = 0
        bytes_sent = 0
        t0 = time.time()

        try:
            while self.is_recording and self.audio_source and self.audio_source.stream:
                chunk = self.audio_source.read_chunk()
                bytes_sent += len(chunk)
                chunks_sent += 1

                if self.websocket and not self.websocket.closed:
                    asyncio.run_coroutine_threadsafe(
                        self.websocket.send(chunk), self.loop
                    )
                else:
                    break

                if chunks_sent % 20 == 0:
                    elapsed = time.time() - t0
                    print(
                        f"Audio: {chunks_sent} chunks ({bytes_sent / 1024:.0f} KB) in {elapsed:.1f}s"
                    )

        except Exception as e:
            err = str(e)
            if "-9999" in err or "Unanticipated host error" in err:
                pass  # Normal on stream close (WSL2/Windows)
            else:
                print(f"Capture error: {e}")
                self.root.after(
                    0, lambda: self.text_label.config(text=f"Error: {err[:60]}")
                )

        elapsed = time.time() - t0
        print(f"Capture done: {chunks_sent} chunks ({bytes_sent / 1024:.0f} KB) in {elapsed:.1f}s")

    def _insert_text(self, text: str):
        """Copy text to clipboard."""
        try:
            pyperclip.copy(text)
            display = text[:120] + "..." if len(text) > 120 else text
            self.text_label.config(text=f"Copied: {display}")
            self.rec_label.config(text="Press Ctrl+V to paste")
            self.record_btn.config(state=tk.NORMAL)
        except Exception as e:
            self.text_label.config(text=f"Error: {str(e)[:60]}")
            self.record_btn.config(state=tk.NORMAL)

    async def _connect(self):
        try:
            self.websocket = await websockets.connect(
                self.server_url,
                ping_interval=20,
                ping_timeout=10,
            )
            self.is_connected = True
            self.root.after(0, lambda: self.status_label.config(text="Connected to Cloud"))
            self.root.after(0, lambda: self.record_btn.config(state=tk.NORMAL))
            await self._listen()
        except Exception as e:
            self.is_connected = False
            self.root.after(
                0, lambda: self.status_label.config(text=f"Error: {str(e)[:50]}")
            )

    async def _listen(self):
        try:
            async for msg in self.websocket:
                data = json.loads(msg)
                if not data["is_partial"]:
                    text = data["data"]["text"].strip()
                    if text:
                        print(f"Transcribed: {text}")
                        self.root.after(0, lambda t=text: self._insert_text(t))
                else:
                    partial = data["data"]["text"].strip()
                    if partial:
                        self.root.after(
                            0,
                            lambda t=partial: self.text_label.config(
                                text=f"... {t[:100]}"
                            ),
                        )
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            self.is_connected = False
            self.root.after(
                0, lambda: self.status_label.config(text=f"Disconnected: {str(e)[:40]}")
            )
            self.root.after(0, lambda: self.record_btn.config(state=tk.DISABLED))

    def _on_close(self):
        self.is_recording = False
        if self.audio_source:
            self.audio_source.close()
        self.pa.terminate()
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


def main():
    print("WhisperFlow Cloud Client starting...")
    if HAS_WASAPI_LOOPBACK:
        print("PyAudioWPatch detected - System Audio capture available")
    else:
        print("PyAudioWPatch not found - Microphone only (pip install PyAudioWPatch)")
    client = WhisperFlowClient()
    client.run()


if __name__ == "__main__":
    main()
