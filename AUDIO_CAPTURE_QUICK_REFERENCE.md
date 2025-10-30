# WhisperFlow-Cloud: Audio Capture Quick Reference

## One-Sentence Summary
**whisperflow-cloud captures microphone input only and transcribes it to text via OpenAI Whisper API in real-time.**

---

## What Can It Capture?

✅ **Microphone Input**
- Voice from your computer's microphone
- Headset microphone
- Any audio going INTO the computer (input device)

---

## What Can't It Capture?

❌ **System Audio / Desktop Audio / Application Audio**
- What's playing on your speakers
- YouTube videos, music, movies
- Spotify, Discord, other apps
- System notifications
- Screen recording audio

**Why?** PyAudio library only supports INPUT devices (microphones), not OUTPUT/monitor devices (system audio).

---

## Key Components

| Component | Purpose | Location |
|-----------|---------|----------|
| **fast_server.py** | WebSocket server on port 8181 | `/whisperflow/` |
| **streaming.py** | Real-time transcription engine | `/whisperflow/` |
| **dictation_gui.py** | GUI client (recommended) | Root directory |
| **universal_dictation_client.py** | Hotkey-based client | Root directory |
| **list_audio_devices.py** | Device diagnostic tool | Root directory |

---

## How It Works

```
Microphone → PyAudio → WebSocket → Server → OpenAI Whisper API → Transcription Result
            (16kHz)    (binary)              (streaming)
```

---

## Audio Configuration

**PyAudio Settings:**
- Sample Rate: 16,000 Hz
- Format: PCM int16 (16-bit signed integer)
- Channels: 1 (mono)
- Chunk Size: 1024-4096 bytes

**Environment Variable:**
```bash
WHISPERFLOW_INPUT_DEVICE=0  # Audio device index (0=default microphone)
```

---

## Quick Start

### 1. GUI Client (Easiest - No Hotkeys)
```bash
python dictation_gui.py
```
- Click "GRABAR" to start
- Click "DETENER" to stop
- Text auto-pastes to clipboard

### 2. Hotkey Client
```bash
python universal_dictation_client.py
```
- Press Ctrl+Space to start
- Press Ctrl+Space again to stop

### 3. Check Audio Devices
```bash
python list_audio_devices.py
```
Shows all audio devices and identifies microphone

### 4. Test Microphone
```bash
python test_microphone.py
```
Records 5 seconds and saves as WAV file

---

## Audio Device Architecture

```
Device 0: pulse (PulseAudio)
  ├─ Input: ✅ Microphone
  └─ Output: (ignored by whisperflow)

Device 1: alsa_output...monitor
  └─ ⚠️ Loopback/Monitor (NOT used by whisperflow)
     (Could capture system audio IF configured, but NOT done)
```

**Key Point:** whisperflow-cloud uses `input_device_index=0` which is the microphone, not loopback.

---

## File Structure

```
whisperflow-cloud/
├── whisperflow/              ← Server code
│   ├── fast_server.py        ← WebSocket server
│   ├── streaming.py          ← Transcription engine
│   ├── transcriber_openai.py ← OpenAI API
│   └── audio/microphone.py   ← Audio capture utility
├── dictation_gui.py          ← GUI client
├── universal_dictation_client.py ← Hotkey client
├── list_audio_devices.py     ← Device lister
├── test_microphone.py        ← Microphone tester
├── .env                      ← Config (OPENAI_API_KEY, etc.)
├── Dockerfile                ← Container setup
└── docker-compose.yml        ← Container orchestration
```

---

## Configuration Files

### .env (Environment Variables)
```bash
OPENAI_API_KEY=sk-proj-...    # Your OpenAI API key
TRANSCRIPTION_MODE=openai     # Always use OpenAI
PORT=8181                     # Server port
WHISPERFLOW_INPUT_DEVICE=0    # Audio device (0=microphone)
```

### Dockerfile
Installs:
- PortAudio (`portaudio19-dev`) - audio library
- FFmpeg - audio processing
- Python packages (PyAudio, OpenAI, etc.)

### docker-compose.yml
- Port: 8181:8181
- NO audio device mounting (runs serverside only)
- Environment variables passed from .env

---

## Python Dependencies

```
PyAudio==0.2.14          # Microphone capture
openai==1.12.0           # Whisper API
websockets==12.0         # Real-time communication
fastapi==0.108.0         # Web server
pynput==1.7.6            # Hotkey capture
pyperclip==1.8.2         # Clipboard access
```

---

## Data Flow

1. **Capture** (dictation_gui.py/universal_dictation_client.py)
   - Opens microphone via PyAudio
   - Reads 1024-byte chunks at 16kHz
   - Sends as binary via WebSocket

2. **Receive** (fast_server.py)
   - Listens on ws://localhost:8181/ws
   - Queues audio chunks

3. **Process** (streaming.py)
   - Accumulates chunks in "window"
   - Detects segment boundaries (pauses)
   - Sends to OpenAI Whisper API

4. **Transcribe** (transcriber_openai.py)
   - Converts PCM to audio format
   - Calls OpenAI API
   - Returns partial/final transcriptions

5. **Deliver** (back to client)
   - JSON response with transcription
   - Client copies to clipboard

---

## Why System Audio Isn't Supported

1. **PyAudio Limitation**
   - Only works with INPUT devices
   - Cannot tap into system audio output
   - Requires loopback device configuration (not implemented)

2. **Platform Barriers**
   - **WSL2:** System audio doesn't route to Linux
   - **Linux:** ALSA doesn't expose system audio monitoring
   - **macOS:** Requires CoreAudio API (not implemented)
   - **Windows:** Requires WASAPI loopback (not implemented)

3. **By Design**
   - Project is for **voice dictation** (microphone input)
   - System audio capture is a **different use case**
   - Would require different APIs and platform-specific code

---

## To Enable System Audio Capture (NOT IMPLEMENTED)

Would require:
1. Add platform-specific audio APIs (CoreAudio, WASAPI, ALSA)
2. Configure PulseAudio monitor sources (Linux)
3. Handle Windows loopback device setup
4. Modify PyAudio wrapper to support monitor devices
5. Update client code for device selection
6. Docker image changes for loopback configuration

**Not in current roadmap** - project focuses on voice dictation.

---

## Troubleshooting

**"PyAudio: No default input device"**
- Check: `python list_audio_devices.py`
- Verify microphone connected
- Try: `export WHISPERFLOW_INPUT_DEVICE=1` (different device)

**"Connection refused (localhost:8181)"**
- Start server: `uvicorn whisperflow.fast_server:app --port 8181`
- Check port: `lsof -i :8181`

**Hotkey doesn't work (WSL2)**
- Use GUI client instead: `python dictation_gui.py`
- Hotkeys require X11 access in WSL2

**Silent audio recording**
- Check microphone level in system settings
- Test: `python test_microphone.py`
- Verify device: `python list_audio_devices.py`

---

## Summary Table

| Feature | Status | Details |
|---------|--------|---------|
| Microphone Input | ✅ Yes | Via PyAudio, 16kHz PCM |
| System Audio | ❌ No | Would need loopback config |
| Desktop Audio | ❌ No | PyAudio limitation |
| App Audio | ❌ No | Not supported |
| Real-time | ✅ Yes | WebSocket streaming |
| Hotkeys | ✅ Yes | Ctrl+Space (pynput) |
| GUI | ✅ Yes | Tkinter (dictation_gui.py) |
| Docker | ✅ Yes | Server containerized |

---

**For detailed analysis, see:** `/mnt/d/Dev/whisperflow-cloud/AUDIO_CAPTURE_ANALYSIS.md`
