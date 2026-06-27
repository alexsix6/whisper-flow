# PHASE CLOSE — `WF-P0.1` Make the default test suite collect and run without external dependencies

> This is the TDC **Result Contract**: the verifiable envelope written when a phase
> closes. A phase is NOT closed by "it works" — only by this report with real evidence.

## Machine fields

```yaml
task_id: WF-P0.1
status: done
runtime: claude-code
closed_at: 2026-06-27
checkpoints: []          # no commit yet — commit/push require explicit user GO
project: whisperflow-cloud
next_recommended: WF-P1.1
go_source: 'user GO 2026-06-27 ("Inicia la implementación del plan TDC")'
```

## Scope

- Files touched:
  - `pytest.ini` (new) — default unit gate definition (markers, asyncio mode, deselect, timeout)
  - `tests/test_transcriber.py` — module-level skip (legacy local-Whisper engine removed)
  - `tests/test_streaming.py` — dropped `whisperflow.transcriber` import + the legacy local-engine test; kept the engine-agnostic streaming unit tests; marked the in-process websocket test `integration`
  - `tests/benchmark/test_benchmark.py` — `pytestmark = integration` (localhost:8181 server)
  - `tests/audio/test_audio.py` — `@pytest.mark.hardware` on the two PyAudio device tests; pure `test_is_silent` stays in the default gate
  - `tests/utils.py` — `test_fast_api` marked `integration` (boots server lifespan needing `OPENAI_API_KEY`)
  - `docs/delivery/{TASKS.yaml,RUNBOOK.md,close/WF-P0.1.md,receipts.jsonl}`
- Files explicitly NOT touched (owned by later phases):
  - `whisperflow_client.py`, `tests/test_whisperflow_client_audio.py` → `WF-P1.1`
  - all dirty pre-existing paths and all `whisperflow/` runtime modules

## Behavior

- What changed: the default `pytest` gate is now hermetic. Tests that need the removed
  local engine, a localhost server, a real OpenAI call, or real audio hardware are
  skipped (legacy) or deselected via `integration`/`hardware` markers. No production or
  test *logic* was changed — only import boundaries, markers, and a gate config.
- What did NOT change: every runtime module; the behavior of the kept tests; the candidate
  client diff (WF-P1.1); all dirty pre-existing paths.
- **Line-ending note:** `tests/audio/test_audio.py`, `tests/benchmark/test_benchmark.py`,
  and `tests/utils.py` were CRLF; `git diff --check` flags the `\r` on added lines as
  trailing whitespace. They were normalized to LF (Python/Linux convention, matching the
  repo's other sources), which is why their diff is full-file. Logic is unchanged.

### Default gate design (`pytest.ini`)

- `testpaths = tests`, `asyncio_mode = strict`, `addopts = -m "not integration and not hardware" --timeout=120`.
- Markers: `integration` (network / localhost server / real OpenAI) and `hardware`
  (PyAudio devices) — both excluded from the default gate; run explicitly when wired.

## Validation (evidence — no claims without output)

- Baseline (from WF-P0.0): full `pytest --collect-only` **stalled >120s (SIGTERM)**;
  `test_transcriber.py` + `test_streaming.py` → `ModuleNotFoundError: whisperflow.transcriber`.
- After (`.venv/bin/python`, py3.10.12 / pytest 7.3.2):
  - `pytest --collect-only -q` → **exit 0, 12.76s**, `7/12 collected (5 deselected)` — no hang.
  - `pytest -q` (default gate) → **`7 passed, 1 skipped, 5 deselected in 13.86s`** (exit 0).
    (1 skipped = `test_transcriber` module skip; 5 deselected = `test_ws`, `test_benchmark`×2, `test_audio` device×2.)
  - `pytest tests/test_whisperflow_client_audio.py tests/test_chat_room.py -q` → **`4 passed in 1.82s`** (exit 0).
  - `git diff --check` → **clean (exit 0)**.
- `grep whisperflow.transcriber` on the two ex-broken files → only docstring mentions, no imports.

## Test gate (test-mapped delivery)

- `test_strategy`: `functional`
- `tdc_verify.py --task WF-P0.1` (real execution):
  - `[PASS] .venv/bin/python -m pytest --collect-only -q`
  - `[PASS] .venv/bin/python -m pytest tests/test_whisperflow_client_audio.py tests/test_chat_room.py -q`
  - `[PASS] git diff --check`
  - **ALL GREEN -> close done (3/3 passed)**, exit 0
- Result: **all green**

## Persistence (required to close)

- **context_agent** (PRIMARY): **saved** — WF-P0.1 close (hermetic default gate, marker design, before/after evidence) persisted as project state for `whisperflow-cloud`.
- **enterprise_memory**: **none** — no genuine transversal lesson (project-specific test-infra cleanup; will not invent one).
- **memory index**: n/a (advisory only).
- **Receipt:** `tdc_receipt.py --task WF-P0.1 --project whisperflow-cloud --context-agent-saved`
- **Verify (gate):** `tdc_persist.py --task WF-P0.1 --project whisperflow-cloud` → PERSISTED (see run output).

## Guardrails

- Did any deploy / smoke / traffic / paid run / push happen? **NO**
- `git add -A` avoided (explicit path staging only): **yes** — nothing staged/committed yet.
- Dirty pre-existing paths left untouched: **yes**
- Other plan guardrails honored: `no_network_in_default_tests`, `no_real_audio_hardware_in_default_tests`,
  `no_openai_api_calls_in_default_tests`, `keep_benchmarks_out_of_default_unit_gate`, `no_push`.
  The default gate runs offline, off-hardware, no OpenAI; benchmarks excluded.

## Risks / follow-ups

- `test_fast_api` lives in `tests/utils.py`, which the default `python_files` pattern does
  not collect; its `integration` marker only applies on explicit invocation. OpenAI-era
  health/contract coverage is owned by **WF-P2.1** (mocked).
- The legacy local-engine test bodies were dropped/skipped, not rebuilt as OpenAI-era tests;
  rebuilding mocked server/transcription coverage is **WF-P2.1**.
- Candidate client diff + its unit tests → **WF-P1.1**.
- Commit of this phase (separate business/runtime vs test commits) is deferred to an explicit
  user GO; nothing is staged.

## Decision

- **GO / NO-GO:** **GO** — default gate is hermetic and green; collection no longer hangs;
  `tdc_verify` 3/3 green; `git diff --check` clean.
- **Next recommended phase:** `WF-P1.1` — Harden Windows FFmpeg/DirectShow client capture and
  unit coverage (adopts the candidate `whisperflow_client.py` + `test_whisperflow_client_audio.py`). Each phase needs its own GO.
