# WhisperFlow Production Readiness Delivery Runbook

Last updated: 2026-06-27
Branch: `spike/realtime-asr-benchmark`
Checkpoint: `e44f6f3`

This runbook is the tracked human-readable source of truth for finishing
WhisperFlow production readiness without losing context across agents, sessions,
or compaction. Its machine-readable companions are:

- `docs/delivery/TASKS.yaml` - task queue and guardrails
- `.claude/scripts/delivery/tdc_next.py` - read-only next-task helper
- `docs/delivery/close/` - phase close reports

Quick start for any agent picking this up:

```bash
python3 .claude/scripts/delivery/tdc_next.py --tasks-file docs/delivery/TASKS.yaml
python3 .claude/scripts/delivery/tdc_next.py --tasks-file docs/delivery/TASKS.yaml --blocked
python3 .claude/scripts/delivery/tdc_next.py --tasks-file docs/delivery/TASKS.yaml --guardrails
```

## Current State

`WF-P0.0` (baseline audit) and `WF-P0.1` (hermetic default test gate) are both
**closed (done, 2026-06-27)** — see `docs/delivery/close/WF-P0.0.md` and
`WF-P0.1.md`, persistence verified (`receipts.jsonl`, context_agent).

`WF-P0.1` made the default `pytest` gate hermetic: new `pytest.ini` deselects
`integration` (network/localhost/OpenAI) and `hardware` (PyAudio) markers; the
legacy local-engine tests (`whisperflow.transcriber`) are skipped/dropped;
benchmark → `integration`; audio device tests → `hardware`. Result: `pytest -q`
= `7 passed, 1 skipped, 5 deselected` (~14s), collection no longer hangs,
`git diff --check` clean, `tdc_verify` 3/3 green. Three CRLF test files were
normalized to LF. No commit yet — commit/push await explicit user GO.

`WF-P1.1` is **closed (done, 2026-06-27)** — the pre-TDC candidate
`whisperflow_client.py` (+135/−66 DirectShow hardening) + its 3 mocked unit
tests were reviewed against all 5 acceptance criteria and adopted as-is; gate
`tdc_verify` 3/3 green (pytest 3 passed, py_compile OK, `git diff --check` clean).
Two minor user-recoverable GUI-state follow-ups are logged for `WF-P3.1` smoke.

`WF-P2.1` is **closed (done, 2026-06-27, rerolled)** — added
`tests/test_server_contract.py` (6 mocked, offline tests) covering `/health`
without a real key, the start/bytes/stop/session_stopped websocket contract with
mocked transcription, auth accept/reject, and the explicit missing-`OPENAI_API_KEY`
error. No runtime change was required. **Reroll:** v1 used Starlette `TestClient`,
which passed locally but HUNG in an external Codex audit (`anyio.start_blocking_portal`
is non-deterministic on WSL/DrvFs); v2 is portal-free (httpx `ASGITransport` +
direct `lifespan` + raw-ASGI websocket driver), stable across repeated runs.
Transversal lesson in enterprise_memory `3b619d42-be74-40e5-a337-e6732374a2de`.

Post-close hardening (commit `d456ccb`): the **entire test suite is now
TestClient-free** — the integration `test_ws` (test_streaming.py) and
`test_fast_api` (utils.py) were removed as superseded by the portal-free contract,
and a portal-free lifespan happy-path test preserves startup coverage. No
`starlette.testclient` / `anyio.start_blocking_portal` anywhere, even in
deselected tests. Default gate: `14 passed, 1 skipped, 4 deselected`.

`WF-P3.2` is **closed (done, 2026-06-29)** — System Audio is validated on the
real Windows client through the controlled VB-Cable route: external/manual FFmpeg
dshow writer -> `WHISPERFLOW_CABLE_RAW_FILE` reader, RMS/peak gate, debug WAV,
streaming, stop/session_stopped, and real transcription. Evidence is in
`docs/delivery/close/WF-P3.2.md`. Integrated Python-launched DirectShow remains
best-effort only on this machine because Python-launched `ffmpeg`/PowerShell and
`sounddevice` cannot open CABLE Output, while direct PowerShell FFmpeg can.

**All technical phases and the VB-Cable System Audio smoke (WF-P0.0, WF-P0.1,
WF-P1.1, WF-P2.1, WF-P3.2) are closed.** No deploy/push has been done; commit,
push, and any Cloud Run deployment remain behind explicit GO gates.

## Non-Negotiable Guardrails

- NO deploy without explicit GO.
- NO paid or external runs without explicit budget GO.
- NO push without explicit GO.
- NO `git add -A`; stage explicit paths only.
- Keep unrelated dirty pre-existing paths out of scoped commits.
- Separate business/runtime commits from test commits.
- Default automated tests must not require OpenAI, network, localhost servers,
  or real audio hardware.
- Production GO requires real Windows client smoke and deployed server smoke
  evidence.

Definition of done for a phase: a `PHASE_CLOSE` report with real evidence
commands, tests, `git diff --check`, persistence receipt, and an explicit GO or
NO-GO.

## Known Dirty Paths To Avoid

These were dirty before this plan started and are treated as unrelated unless
`WF-P0.0` proves otherwise:

- `.agent/`
- `.claude/doc/ultrathink_audio_error_resolution.md`
- `COMO_USAR_RESTAURADO.md`
- `FIX_ERROR_9999.md`
- `START_DICTADO_FIXED.sh`
- `START_DICTADO_FIXED.sh.bak-1761891116`
- `benchmarks/`
- `dictation_gui.py.backup-20251031-010526`
- `dictation_gui.py.backup-20251031-010559`
- `dictation_gui.py.backup-final-fix`

In-scope pre-TDC candidate work exists in `whisperflow_client.py` and
`tests/test_whisperflow_client_audio.py`. It is owned by `WF-P0.0` for
classification and by `WF-P1.1` if adopted into the final client hardening.

## Architecture / Method Summary

The production-readiness effort has three technical gates and one external
smoke gate:

1. Stabilize local test collection and default test boundaries.
2. Harden the Windows DirectShow FFmpeg client path with focused unit coverage.
3. Add mocked server contract tests and production config validation.
4. Run manual Windows client and Cloud Run smoke validation with captured logs.

Do not generalize the WSL/PyAudio `dictation_gui.py` notes into the Cloud client
without direct evidence. The current production client path under review is
`whisperflow_client.py`, which uses an isolated sounddevice subprocess for mic
and FFmpeg DirectShow for system audio.

## Recommended Sequence

1. `WF-P0.0` - Baseline audit and adopt-or-defer pre-TDC diff. Read-only except
   for TDC close/report updates. Classify dirty state and confirm next task.
2. `WF-P0.1` - Make default tests collect and run without OpenAI, network,
   localhost server, or real hardware dependencies.
3. `WF-P1.1` - Harden Windows FFmpeg DirectShow client capture and unit
   coverage. Owns the current pre-TDC client/test candidate diff.
4. `WF-P2.1` - Add mocked server contract tests and production config
   validation.
5. `WF-P3.1` - Manual production smoke on Windows client and Cloud Run server.
   This remains hold until explicit user GO.

## Parallelization Matrix

| Phase | Main files | Parallel status |
| --- | --- | --- |
| `WF-P0.0` | read-only baseline plus TDC close | Serial first |
| `WF-P0.1` | `tests/*` test boundaries | Serial |
| `WF-P1.1` | `whisperflow_client.py`, client audio tests | Serial |
| `WF-P2.1` | `whisperflow/fast_server.py`, OpenAI transcriber tests | Serial |
| `WF-P3.1` | external manual smoke evidence | Hold |

Safe in parallel: none until `WF-P0.0` closes, because dirty state must be
classified first. Not safe in parallel: any two phases touching tests,
`whisperflow_client.py`, or server runtime code.

## Cross-Agent Protocol

Both Claude Code and Codex read this runbook plus `TASKS.yaml` via
`tdc_next.py`. The contract:

1. Before working, run the helper to confirm the next actionable task and its
   guardrails.
2. Stay inside the task `touches`; honor `must_not_run_with` and dirty paths.
3. On finishing, write `docs/delivery/close/<TASK_ID>.md`, update
   `TASKS.yaml`, and refresh this runbook.
4. A phase is not `done` without real command evidence, green gated tests where
   applicable, `git diff --check`, and persistence receipt verification.

## Commit And Push Rules

- Commit only after a `PHASE_CLOSE` report and user GO.
- Separate business/runtime commits from test commits.
- Explicit path staging only; never `git add -A`.
- Push only after explicit user GO. Pushing to `main` also requires the F1.6
  governance signoff.

## WF-P3.1 / WF-P3.2 smoke finding (2026-06-29)

Microphone is **GO** end-to-end (sounddevice subprocess: chunks sent, real
transcription, STOP recovers the UI). Server `/health` + websocket auth
accept/reject **validated**. System Audio is **NO-GO** via WASAPI loopback /
dshow-auto on the current Windows: independent probes (PyAudioWPatch `Invalid
device`, `soundcard` fails, COM/WASAPI LOOPBACK `E_INVALIDARG`, local ffmpeg has
no wasapi backend) prove the native loopback stack rejects capture — not a
name/index/pin/parser bug. System Audio is rerolled to **`WF-P3.2`** (VB-Cable
controlled route, opt-in). The default pytest gate no longer hard-requires
`pytest-timeout` (`--timeout` removed from `addopts`) so it runs in any env.

## Immediate Next Task

```text
No actionable TDC task remains after WF-P3.2. Next operational step is review/stage/commit the scoped WF-P3.2 runtime + tests + TDC docs, then decide push/deploy separately under explicit GO gates. No push/deploy has been performed.
```
