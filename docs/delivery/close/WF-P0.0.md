# PHASE CLOSE — `WF-P0.0` Baseline audit and adopt-or-defer pre-TDC diff

> This is the TDC **Result Contract**: the verifiable envelope written when a phase
> closes. One file per closed phase (e.g. `docs/delivery/close/<TASK_ID>.md`).
> A phase is NOT closed by "it works" — only by this report with real evidence.

## Machine fields

```yaml
task_id: WF-P0.0
status: done
runtime: claude-code
closed_at: 2026-06-27
checkpoints: []          # read-only audit — no commits produced
project: whisperflow-cloud
next_recommended: WF-P0.1
go_source: 'user GO 2026-06-27 ("Inicia la implementación del plan TDC")'
```

## Scope

- Files touched (TDC governance only):
  - `docs/delivery/close/WF-P0.0.md` (this report — new)
  - `docs/delivery/TASKS.yaml` (WF-P0.0 status → done; ownership annotations)
  - `docs/delivery/RUNBOOK.md` (Current State + Immediate Next Task)
  - `docs/delivery/receipts.jsonl` (persistence receipt — new ledger)
- Files explicitly NOT touched (read-only baseline; ownership assigned, left for their phase):
  - `whisperflow_client.py` — pre-TDC candidate diff, owned by `WF-P1.1`
  - `tests/test_whisperflow_client_audio.py` — pre-TDC candidate test, owned by `WF-P1.1`
  - all dirty pre-existing paths (`.agent/`, `.claude/doc/ultrathink_audio_error_resolution.md`,
    `COMO_USAR_RESTAURADO.md`, `FIX_ERROR_9999.md`, `START_DICTADO_FIXED.sh(.bak-*)`,
    `benchmarks/`, `dictation_gui.py.backup-*`)
  - all `whisperflow/` runtime and all `tests/*` test code

## Behavior

- What changed: only TDC delivery-control documents (classification, queue status, runbook).
  No runtime, server, client, or test code was modified.
- What did NOT change: every source module, every test, and every dirty pre-existing path.

### Classification of current dirty state (acceptance criterion #1)

| Path | Git state | Classification | Owner |
| --- | --- | --- | --- |
| `whisperflow_client.py` | ` M` | **In-scope candidate** — DirectShow capture hardening (+135/−66): stdout+stderr parse, Alternative-name capture, `{name,alt}` model, scored candidates, alt-name + `-audio_pin_name` fallback, richer logs | **WF-P1.1** (adopt) |
| `tests/test_whisperflow_client_audio.py` | `??` | **In-scope candidate** — 3 fully-mocked unit tests covering the diff above (discovery, candidate ranking + override, alt→pin fallback). Collects in 0.05s, no net/hw | **WF-P1.1** (adopt) |
| `docs/delivery/`, `.claude/scripts/delivery/tdc_next.py` | `??` | **TDC infrastructure** — this delivery's scaffold; keep | this plan |
| `.agent/` | `??` | Do-not-touch unrelated (agent scratch) | none (deferred) |
| `.claude/doc/ultrathink_audio_error_resolution.md` | `??` | Do-not-touch unrelated (doc note) | none (deferred) |
| `COMO_USAR_RESTAURADO.md`, `FIX_ERROR_9999.md` | `??` | Do-not-touch unrelated (es user docs) | none (deferred) |
| `START_DICTADO_FIXED.sh`, `START_DICTADO_FIXED.sh.bak-1761891116` | `??` | Do-not-touch unrelated (legacy WSL dictation scripts) | none (deferred) |
| `benchmarks/` | `??` | Do-not-touch unrelated (May-2026 realtime-ASR spike; NOT `tests/benchmark/`) | none (deferred) |
| `dictation_gui.py.backup-20251031-010526 / -010559 / -final-fix` | `??` | Do-not-touch unrelated (backups of legacy local GUI) | none (deferred) |

### Production-readiness gaps mapped to task ownership (acceptance criterion #2)

| Gap (with baseline evidence) | Owner |
| --- | --- |
| `tests/test_transcriber.py` + `tests/test_streaming.py` import the deleted local engine `whisperflow.transcriber` → `ModuleNotFoundError` at collection | **WF-P0.1** |
| `tests/benchmark/test_benchmark.py` is network/server-coupled (`requests`/`pandas`/`websocket` to `localhost:8181`) — not default-unit-safe | **WF-P0.1** |
| `tests/audio/test_audio.py` is hardware-coupled (`pyaudio.PyAudio()` mic capture + playback) — must skip cleanly when PyAudio/devices absent | **WF-P0.1** |
| Full `pytest --collect-only` stalls (>120s, SIGTERM) while each file collects <25s alone — default gate must not hang | **WF-P0.1** |
| `tests/utils.py::test_fast_api` drives `fast_server` lifespan that hard-requires `OPENAI_API_KEY` (`ValueError` if unset) | **WF-P0.1** / **WF-P2.1** |
| Windows FFmpeg/DirectShow client capture hardening + focused unit coverage | **WF-P1.1** |
| No mocked server contract tests; no explicit production config validation (`OPENAI_API_KEY`, `WHISPERFLOW_AUTH_TOKEN`) | **WF-P2.1** |
| Manual Windows client + Cloud Run server smoke evidence | **WF-P3.1** (hold) |

## Validation (evidence — no claims without output)

- Commands run:
  - `git status --short` → 1 modified (`whisperflow_client.py`); untracked: TDC infra (`docs/delivery/`, `.claude/scripts/`), 1 candidate test, and 9 dirty pre-existing paths. (full list classified above)
  - per-file `.venv/bin/python -m pytest --collect-only -q <file>` (Python 3.10.12 / pytest 7.3.2):
    - `tests/test_transcriber.py` → **exit 2**, `ModuleNotFoundError: No module named 'whisperflow.transcriber'`
    - `tests/test_streaming.py` → **exit 2**, same `ModuleNotFoundError`
    - `tests/benchmark/test_benchmark.py` → exit 0, 2 collected (network-coupled)
    - `tests/audio/test_audio.py` → exit 0, 3 collected (hardware-coupled, `pyaudio`)
    - `tests/test_chat_room.py` → exit 0, 1 collected (default-safe)
    - `tests/utils.py` → exit 0, 1 collected (`test_fast_api`, needs `OPENAI_API_KEY`)
    - `tests/test_whisperflow_client_audio.py` → exit 0, 3 collected, 0.05s (fully mocked)
  - full `.venv/bin/python -m pytest --collect-only -q` → **did not finish within 120s (SIGTERM, exit 143)** — full-collection stall to be removed by WF-P0.1
  - `git diff --check` → **clean** (exit 0)
- Tests passed: n/a — read-only baseline audit, no gating tests executed.
- Known failures (and why acceptable): the two broken collections and the full-collection stall ARE the WF-P0.1 work item; they are expected at baseline and explicitly owned, not regressions introduced here.
- `git diff --check`: clean

## Test gate (test-mapped delivery)

- `test_strategy`: `not_applicable`
- Gating `tests:` run: none (`tests: []`)
- Result: **not_applicable** (no code tests gate a read-only classification phase)
- `test_rationale`: read-only baseline and scope decision; evidence is documented in this PHASE_CLOSE.

## Persistence (required to close)

The gate verifies an append-only RECEIPT (`docs/delivery/receipts.jsonl`), hash-bound to THIS
report and scoped to project+task — NOT the memory cache.

- **context_agent** (PRIMARY): **saved** — WhisperFlow production-readiness TDC baseline (WF-P0.0) classification + gap→owner map persisted as project state for `whisperflow-cloud`.
- **enterprise_memory**: **none** — no genuine transversal lesson; the findings are project-specific baseline state, not a cross-project rule (will not invent one).
- **memory index**: n/a (advisory only).
- **Receipt:** `tdc_receipt.py --task WF-P0.0 --project whisperflow-cloud --context-agent-saved`
- **Verify (gate):** `tdc_persist.py --task WF-P0.0 --project whisperflow-cloud` → see appended run output (PERSISTED).

## Guardrails

- Did any deploy / smoke / traffic / paid run / push happen? **NO**
- `git add -A` avoided (explicit path staging only): **yes** — nothing was staged; read-only audit.
- Dirty pre-existing paths left untouched: **yes**
- Other plan guardrails honored: `read_only_except_tdc_close` (only TDC docs written), `no_runtime_changes`, `no_push`, `classify_existing_dirty_paths_before_editing` (done above). Default collection probes were `--collect-only` only (no network call, no audio device opened, no OpenAI call).

## Risks / follow-ups

- Broken test imports of the deleted `whisperflow.transcriber` → **WF-P0.1**.
- Network-coupled `test_benchmark.py` and hardware-coupled `test_audio.py` must leave the default gate → **WF-P0.1**.
- Full-collection stall (>120s) under WSL/DrvFs — likely import-interaction / I/O with the coupled tests; neutralize by quarantining broken/coupled tests and stabilizing the default gate → **WF-P0.1**.
- `test_fast_api` lifespan hard-requires `OPENAI_API_KEY` → **WF-P0.1** (test boundary) and/or **WF-P2.1** (config validation).
- Adoption of the candidate client diff + new test → **WF-P1.1**.
- Mocked server contract + production config validation → **WF-P2.1**.
- Manual Windows + Cloud Run smoke → **WF-P3.1** (remains hold until explicit user GO).

## Decision

- **GO / NO-GO:** **GO** — baseline audited with real evidence; dirty state classified; production-readiness gaps mapped to owning phases; next actionable task confirmed by the helper.
- **Next recommended phase:** `WF-P0.1` — Make the default test suite collect and run without external dependencies (each phase needs its own GO).
