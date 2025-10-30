# WhisperFlow-Cloud Audio Capture Analysis

## Executive Summary

**whisperflow-cloud** is a real-time speech-to-text transcription system using OpenAI's Whisper API. The project currently captures audio from **microphone input only** - it does NOT support system audio (desktop audio), application audio, or speaker output capture.

---

## 1. AUDIO SOURCES CURRENTLY SUPPORTED

### ✅ Supported Audio Source
- **Microphone Input Only**
  - Local computer microphone
  - Via PyAudio library
  - Sample rate: 16,000 Hz (OpenAI standard)
  - Format: PCM int16, mono channel
  - Chunk size: 1024-4096 bytes per buffer

### ❌ NOT Supported
- System audio (what's playing on the speaker)
- Desktop audio (screen recordings, system sounds)
- Application audio (audio from specific applications)
- Speaker output/loopback audio
- Virtual audio devices (monitor devices)

---

## 2. MAIN COMPONENTS & ARCHITECTURE

### Core Server Component (`/whisperflow/`)

#### **fast_server.py** - FastAPI WebSocket Server
- Listens on port 8181
- Accepts binary audio chunks via WebSocket
- Routes to OpenAI Whisper API (`whisperflow/transcriber_openai.py`)
- Returns transcription results (partial + final)
- Environment: Docker container

#### **streaming.py** - Streaming Engine
- Manages transcription session state
- Implements tumbling window approach
- Processes incoming audio chunks
- Detects segment boundaries (speech pauses)
- Returns partial and complete transcriptions

#### **transcriber_openai.py** - OpenAI Integration
- Wraps OpenAI Whisper API
- Converts PCM audio chunks to audio format
- Sends to OpenAI for transcription
- Handles language detection and specification

#### **audio/microphone.py** - Audio Capture Utility
- Basic async microphone capture
- Uses PyAudio library
- Records 1024-byte chunks at 16kHz
- Provides `capture_audio()` and `play_audio()` async functions

### Client Components

#### **dictation_gui.py** - GUI Client (Recommended for WSL2)
- Tkinter-based GUI interface
- Button-based recording control (no hotkey issues in WSL2)
- **Audio Device Selection via Environment Variable:**
  ```python
  self.input_device_index = int(os.getenv("WHISPERFLOW_INPUT_DEVICE", "0"))
  ```
- Default: device 0 (usually PulseAudio/"pulse")
- Alternative: set `WHISPERFLOW_INPUT_DEVICE=1` for different device
- Connects to WebSocket server
- Sends raw PCM audio chunks
- Displays partial/final transcriptions
- Auto-inserts text to clipboard (Ctrl+V paste)

#### **universal_dictation_client.py** - Hotkey Client
- Hotkey-based recording (Ctrl+Space to start/stop)
- For native Linux/Windows environments
- Uses pynput for global hotkey capture
- Device auto-detection (uses default device)
- Console-based output

#### **list_audio_devices.py** - Audio Device Diagnostic Tool
- Lists all available audio devices
- Shows device capabilities (input/output channels)
- Identifies default input/output devices
- Flags loopback/monitor devices
- **Critical Output:** Shows which devices are:
  - Microphone (real input)
  - Loopback (audio output being monitored - not suitable for voice)

### Testing & Diagnostics

#### **test_microphone.py** - Microphone Functionality Test
- Records 5 seconds of audio
- Saves as WAV file
- Validates microphone access
- Tests PyAudio configuration

#### **test_hotkey.py** - Hotkey Verification
- Tests if Ctrl+Space hotkey works
- Validates pynput keyboard access

---

## 3. HOW AUDIO CAPTURE WORKS

### Architecture Flow

```
┌─────────────────────┐
│   Microphone        │
│  (Hardware Device)  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────────┐
│   PyAudio (Python wrapper)          │
│   - Opens audio stream              │
│   - Reads chunks: 1024-4096 bytes   │
│   - 16kHz sample rate, mono, int16  │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│   Client Application                │
│   - dictation_gui.py (GUI)          │
│   - universal_dictation_client.py   │
│     (Hotkey-based)                  │
└──────────┬──────────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│   WebSocket Connection               │
│   ws://localhost:8181/ws             │
│   (Sends binary audio frames)        │
└──────────┬───────────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│   FastAPI Server (fast_server.py)   │
│   - Receives audio chunks            │
│   - Queues for transcription         │
│   - Manages streaming session        │
└──────────┬───────────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│   Streaming Engine (streaming.py)   │
│   - Accumulates chunks (window)      │
│   - Detects segment boundaries       │
│   - Manages session state            │
└──────────┬───────────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│   OpenAI Whisper API                 │
│   - Transcribes audio                │
│   - Returns text results             │
│   - Language: Spanish (default)      │
└──────────┬───────────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│   Client (Receives Results)          │
│   - Partial transcriptions           │
│   - Final transcriptions             │
│   - Copies to clipboard              │
└──────────────────────────────────────┘
```

### Key Technical Details

#### PyAudio Configuration
```python
# From whisperflow/audio/microphone.py and clients
stream = audio.open(
    format=pyaudio.paInt16,      # 16-bit signed integer
    channels=1,                  # Mono (single channel)
    rate=16000,                  # 16 kHz (OpenAI standard)
    input=True,                  # Input stream (microphone)
    input_device_index=0,        # Device index (0=default/pulse)
    frames_per_buffer=1024,      # Chunk size: 1024-4096 bytes
)
```

#### Audio Data Flow
1. **Capture**: PyAudio reads chunks from microphone
2. **Format**: PCM int16, 16kHz mono
3. **Transmission**: Sent as binary frames via WebSocket
4. **Processing**: Accumulated in queue until natural pause detected
5. **Transcription**: Sent to OpenAI Whisper API
6. **Result**: Returned as JSON with partial/final text

#### Device Selection Mechanism
```python
# From dictation_gui.py
self.input_device_index = int(os.getenv("WHISPERFLOW_INPUT_DEVICE", "0"))
```
- **Default (0)**: PulseAudio/"pulse" - the actual microphone
- **Alternative devices**: Can be set via environment variable
- **Note**: Device 1 or higher might be loopback/monitor (doesn't work for voice)

### Streaming Protocol

#### WebSocket Message Format
```json
{
  "is_partial": true,
  "data": {
    "text": "partial transcription here"
  },
  "time": 175.47
}
```

```json
{
  "is_partial": false,
  "data": {
    "text": "final complete transcription"
  },
  "time": 205.14
}
```

#### Windowing Strategy
- Uses "tumbling window" approach (NOT sliding window)
- Accumulates audio until natural speech boundary detected
- Detects boundaries via: speech pauses, repeated text, timeout cycles
- Segments close when same text produced twice in a row

---

## 4. SYSTEM AUDIO CAPTURE - WHY IT'S NOT SUPPORTED

### Technical Barriers

#### PyAudio Limitation
- PyAudio only accesses physical audio devices through PortAudio
- Cannot intercept system audio stream directly
- Requires loopback device (virtual audio) - **not implemented**

#### Platform-Specific Issues

**WSL2 (Windows Subsystem for Linux):**
- PulseAudio server at `/mnt/wslg/PulseServer`
- Only microphone input accessible via PulseAudio
- System audio NOT passed through to WSL environment
- Would require Windows Host to capture system audio

**Linux (Native):**
- ALSA (Advanced Linux Sound Architecture) doesn't provide system audio monitoring
- Would require PulseAudio monitor device (pactl list)
- Not configured in current codebase

**macOS/Windows:**
- Would require CoreAudio (macOS) or WASAPI (Windows) APIs
- Not implemented in project

#### Audio Device Architecture
```
Device 0: PulseAudio ("pulse")        ← Microphone (INPUT)
Device 1: PulseAudio Monitor          ← System audio loopback (OUTPUT)
                                         [NOT USED in whisperflow-cloud]
```

The code explicitly uses `input_device_index` which selects INPUT devices. Monitor/loopback devices are OUTPUT-based and won't work for speech input.

---

## 5. ARCHITECTURE & CONFIGURATION FILES

### Project Structure
```
whisperflow-cloud/
├── whisperflow/
│   ├── audio/
│   │   └── microphone.py           ← Microphone capture utility
│   ├── fast_server.py               ← WebSocket server
│   ├── streaming.py                 ← Streaming engine
│   ├── transcriber_openai.py        ← OpenAI API wrapper
│   └── models/                      ← Whisper models directory
├── dictation_gui.py                 ← GUI client (RECOMMENDED)
├── universal_dictation_client.py    ← Hotkey client
├── list_audio_devices.py            ← Device diagnostic tool
├── test_microphone.py               ← Microphone test
├── Dockerfile                       ← Container setup
├── docker-compose.yml               ← Container orchestration
├── requirements.txt                 ← Python dependencies
└── .env                            ← Environment configuration
```

### Key Configuration Files

#### `.env` - Environment Variables
```bash
OPENAI_API_KEY=sk-proj-...          # Required: OpenAI API key
TRANSCRIPTION_MODE=openai           # Server transcription mode
LOCAL_MODEL=small                   # Fallback model (unused)
PORT=8181                           # Server port
WHISPERFLOW_INPUT_DEVICE=0          # Client: audio device index
```

#### `Dockerfile` - Container Setup
```dockerfile
RUN apt-get install -y \
    build-essential  \
    ffmpeg          \
    libsndfile1     \
    portaudio19-dev  # ← Audio library (PortAudio, NOT PulseAudio)
```

#### `docker-compose.yml` - Container Orchestration
- Port mapping: 8181:8181
- Volume: `./whisperflow/models:/app/whisperflow/models:ro`
- Environment variables: OPENAI_API_KEY, TRANSCRIPTION_MODE
- **Note:** NO audio device mounting (would require `--device /dev/snd:...`)

#### `requirements.txt` - Dependencies
```
PyAudio==0.2.14          # Microphone input
openai==1.12.0           # Whisper API
websockets==12.0         # WebSocket protocol
fastapi==0.108.0         # Server framework
pynput==1.7.6            # Hotkey capture
pyperclip==1.8.2         # Clipboard access
```

---

## 6. AUDIO DEVICE CAPABILITIES ANALYSIS

### Device Detection Output Example

```
Device 0: pulse (PulseAudio)
  Type: INPUT + OUTPUT
  Max Input Channels: 1
  Max Output Channels: 2
  Default Sample Rate: 48000 Hz
  Host API: PulseAudio

Device 1: alsa_output.pci-0000_00_1f.3.analog-stereo.monitor
  Type: INPUT (Monitor/Loopback)
  Max Input Channels: 2
  Max Output Channels: 0
  Host API: ALSA
  ⚠️  This is LOOPBACK - not suitable for microphone input
```

### Why Loopback Devices Don't Work for Voice

- **Monitor devices** capture OUTPUT stream (system audio)
- **Input devices** capture MIC stream (your voice)
- Code uses `input=True` (input stream), so only real microphone works
- Loopback would theoretically capture system audio but:
  - It's monitor-only (no real input configuration)
  - WSL2 doesn't expose system audio to PulseAudio anyway
  - Would require explicit configuration (not in codebase)

---

## 7. CURRENT AUDIO CAPTURE CAPABILITIES SUMMARY

### What CAN Be Captured
✅ Microphone input (local computer microphone)
✅ Voice from any microphone-connected device
✅ Headset microphone input
✅ Any audio going INTO the computer via microphone

### What CANNOT Be Captured
❌ System audio (speaker output)
❌ Video playback audio (YouTube, movies, etc.)
❌ Application audio (Spotify, Discord, etc.)
❌ System sounds (notifications, alerts)
❌ Audio from other applications
❌ Virtual desktop audio
❌ Screen recording audio

### Workaround for System Audio (NOT IMPLEMENTED)
If system audio capture was needed, the project would require:
1. **Linux**: Configure PulseAudio monitor source
2. **WSL2**: Use Windows host to capture system audio
3. **macOS**: Use CoreAudio with privacy permissions
4. **Windows**: Use WASAPI loopback device

This would require new code using:
- `pactl` (PulseAudio tools) for Linux
- Windows Audio Session API for Windows
- Different PyAudio configuration

---

## 8. CLIENT USAGE & CONFIGURATION

### GUI Client (dictation_gui.py) - RECOMMENDED
```bash
# Set specific audio device (optional)
export WHISPERFLOW_INPUT_DEVICE=0
python dictation_gui.py
```
- Click "GRABAR" button to start
- Speak into microphone
- Click "DETENER" to stop
- Text copied to clipboard automatically

### Hotkey Client (universal_dictation_client.py)
```bash
python universal_dictation_client.py
```
- Press Ctrl+Space to start recording
- Press Ctrl+Space again to stop
- Text inserted via clipboard paste (Ctrl+V)

### Audio Device Listing
```bash
python list_audio_devices.py
```
- Shows all available audio devices
- Identifies microphone (device with maxInputChannels > 0)
- Warns about loopback/monitor devices

### Microphone Test
```bash
python test_microphone.py
```
- Records 5 seconds of audio
- Saves as `test_microphone_recording.wav`
- Validates microphone access

---

## 9. CODE REFERENCES

### Key Audio Capture Code Locations

**microphone.py** - Basic capture:
```python
async def capture_audio(queue_chunks: queue.Queue, stop_event: asyncio.Event):
    audio = pyaudio.PyAudio()
    stream = audio.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,            # ← MICROPHONE ONLY
        frames_per_buffer=1024,
    )
    # ... read loop ...
```

**dictation_gui.py** - Device selection:
```python
self.input_device_index = int(os.getenv("WHISPERFLOW_INPUT_DEVICE", "0"))
self.stream = self.audio.open(
    format=pyaudio.paInt16,
    channels=1,
    rate=self.sample_rate,
    input=True,
    input_device_index=self.input_device_index,  # ← CONFIGURABLE
    frames_per_buffer=self.chunk_size,
)
```

**list_audio_devices.py** - Device enumeration:
```python
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    is_monitor = "monitor" in info['name'].lower() or "loopback" in info['name'].lower()
    # Flags loopback devices ⚠️
```

---

## 10. CONCLUSION

**whisperflow-cloud is a microphone-input-only speech-to-text system.** It:

1. **Captures**: Audio from your computer's microphone
2. **Processes**: Sends to OpenAI Whisper API for transcription
3. **Delivers**: Real-time transcription results to client

It does **NOT** capture system audio, desktop audio, or application audio because:
- PyAudio is designed for microphone input only
- Audio device architecture separates input (mic) from output (system audio)
- Platform-specific barriers (WSL2, Linux, etc.)
- No loopback/monitor device configuration implemented
- Would require different APIs and platform-specific code

**For voice dictation use cases** (which is the project's purpose), microphone-only capture is the correct and intended design. System audio capture would be a different use case entirely.

