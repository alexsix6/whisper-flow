# PHASE CLOSE — `WF-P3.2` System Audio via VB-Cable controlled route

> TDC Result Contract. A phase is NOT closed by "it works" — only by this report with real evidence.

## Machine fields

```yaml
task_id: WF-P3.2
status: done
runtime: codex
closed_at: 2026-06-29T21:11:26Z
checkpoints: []          # no commit/push/deploy in this close
project: whisperflow-cloud
next_recommended: commit_review_or_push_gate
go_source: 'user GO already granted for WF-P3.1/WF-P3.2 smoke; user supplied real Windows evidence 2026-06-29'
reroll: 'external VB-Cable raw-file reader after Python-launched DirectShow failed on this Windows'
```

## Scope

- Files touched:
  - `whisperflow_client.py`
  - `tests/test_whisperflow_client_audio.py`
  - `docs/delivery/TASKS.yaml`
  - `docs/delivery/RUNBOOK.md`
  - `docs/delivery/close/WF-P3.2.md`
  - `docs/delivery/receipts.jsonl`
- Files intentionally NOT touched:
  - deploy/cloud config
  - server runtime
  - dirty pre-existing paths listed in `TASKS.yaml`

## Behavior

- `WHISPERFLOW_SYSTEM_BACKEND=cable` remains opt-in.
- The cable backend captures only `CABLE Output (VB-Audio Virtual Cable)`.
- Integrated DirectShow launch remains best-effort, but this Windows rejects Python-launched
  `ffmpeg`/PowerShell and `sounddevice` for CABLE Output.
- Production-usable path for this environment:
  1. run external/manual FFmpeg dshow writer against the exact CABLE Output alt-name;
  2. set `WHISPERFLOW_CABLE_RAW_FILE`;
  3. client tails fresh raw PCM bytes from that file;
  4. client runs RMS/peak gate before streaming;
  5. client writes debug WAV only after real signal and streams to the server.
- Capture errors now reset recording state without waiting for a server stop confirmation.

## Acceptance coverage

| Acceptance criterion | Evidence |
| --- | --- |
| Opt-in backend captures only CABLE Output, no silent fallback | `WHISPERFLOW_SYSTEM_BACKEND=cable`; log: `AUDIO_DEVICE: cable-file -> CABLE Output (VB-Audio Virtual Cable) raw_file=...`; no Stereo Mix / VB-Audio Point fallback |
| RMS/peak gate fails fast on silence | unit coverage for silent raw/file probe and existing RMS gate |
| Real signal writes debug WAV and streams | log: `AUDIO_LEVEL rms=2299.3 peak=18408`; `Debug WAV saved: D:\Dev\whisperflow-cloud\whisperflow_system_cable_20260629-160752.wav`; `Streaming: 65 chunks (2031 KB)` |
| Unit tests cover selection + RMS gate | `tests/test_whisperflow_client_audio.py` includes cable-only selection, explicit spec, external raw-file, silence, and UI recovery tests |
| WASAPI/dshow-auto marked experimental/non-productive | `TASKS.yaml` + `RUNBOOK.md` document WF-P3.1 NO-GO and WF-P3.2 reroll |
| Manual Windows evidence recorded | This close report includes the user-supplied real Windows log and transcription |

## Real Windows smoke evidence

### External FFmpeg writer

Command shape executed by the user:

```powershell
ffmpeg -y -f dshow -i "audio=@device_cm_{33D9A762-90C8-11D0-BD43-00A0C911CE86}\wave_{BE39C546-6082-4F29-A83C-B0FA7AA1B1B5}" -ac 1 -ar 16000 -f s16le D:\Dev\whisperflow-cloud\debug-wav\cable_live.raw
```

Relevant FFmpeg evidence:

```text
Input #0, dshow, from 'audio=@device_cm_{33D9A762-90C8-11D0-BD43-00A0C911CE86}\wave_{BE39C546-6082-4F29-A83C-B0FA7AA1B1B5}':
  Stream #0:0: Audio: pcm_s16le, 44100 Hz, stereo, s16, 1411 kb/s
Output #0, s16le, to 'D:\Dev\whisperflow-cloud\debug-wav\cable_live.raw':
  Stream #0:0: Audio: pcm_s16le, 16000 Hz, mono, s16, 256 kb/s
size=    5188KiB time=00:02:45.99 bitrate= 256.0kbits/s speed=   1x elapsed=0:02:46.01
Exiting normally, received signal 2.
```

### Client smoke

Relevant client log supplied by the user:

```text
16:07:52 [INFO] Starting audio capture (system) via external VB-Cable raw file (WHISPERFLOW_CABLE_RAW_FILE)...
16:07:57 [WARNING] [audio] AUDIO_LEVEL: cable signal-probe rms=2299.3 peak=18408
16:07:57 [INFO] AUDIO_DEVICE: cable-file -> CABLE Output (VB-Audio Virtual Cable) raw_file=D:\Dev\whisperflow-cloud\debug-wav\cable_live.raw
16:07:57 [WARNING] [audio] AUDIO_FORMAT: external ffmpeg dshow raw-file 16000Hz mono
16:07:57 [INFO] Audio subprocess running (PID external)
16:08:05 [INFO] Streaming: 10 chunks (312 KB) in 13.8s
16:08:14 [INFO] Streaming: 20 chunks (625 KB) in 21.8s
16:08:22 [INFO] Streaming: 30 chunks (938 KB) in 30.4s
16:08:30 [INFO] Streaming: 40 chunks (1250 KB) in 38.4s
16:08:47 [INFO] Streaming: 50 chunks (1562 KB) in 54.9s
16:08:55 [INFO] Streaming: 60 chunks (1875 KB) in 62.8s
16:09:00 [INFO] External audio file detached
16:09:00 [INFO] Debug WAV saved: D:\Dev\whisperflow-cloud\whisperflow_system_cable_20260629-160752.wav
16:09:00 [INFO] Capture complete: 65 chunks (2031 KB) in 68.8s
16:09:00 [INFO] Sent control frame: stop
16:09:07 [INFO] Transcribed: Hardware should we get? What should we do with these local models? Which one sho
16:09:07 [INFO] Received session_stopped
```

User supplied full transcription from the video. It was coherent English speech from the system audio
source; one excerpt from the provided transcript:

```text
Hardware should we get? What should we do with these local models? Which one should we load?
```

## Automated validation

- `.venv/bin/python -m pytest tests/test_whisperflow_client_audio.py -q` -> `23 passed in 0.54s`
- `.venv/bin/python -m py_compile whisperflow_client.py tests/test_whisperflow_client_audio.py` -> exit 0
- `git diff --check` -> clean
- `.venv/bin/python -m pytest -q` -> `43 passed, 1 skipped, 4 deselected in 17.67s`

## Persistence

- **context_agent** (PRIMARY): saved — WF-P3.2 real Windows validation and final route recorded.
- **enterprise_memory**: n/a — machine-specific DirectShow/VB-Cable behavior, not a safe transversal lesson yet.
- **Receipt:** appended to `docs/delivery/receipts.jsonl` with hash of this close report.

## Guardrails

- Deploy / push / paid run: **NO**
- `git add -A`: **NO**
- Dirty pre-existing paths: **not touched**
- Default tests remain offline / non-hardware by marker policy.

## Decision

- **GO / NO-GO:** **GO** for WF-P3.2 technical acceptance.
- System Audio is production-usable on this Windows through the external VB-Cable raw-file route.
- Integrated in-client DirectShow launch remains **not accepted** for this machine; it is documented as best-effort only.
- Next recommended step: review/stage/commit the WF-P3.2 runtime + tests + TDC docs, then decide push/deploy separately under existing GO gates.
