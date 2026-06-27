# PHASE CLOSE — `WF-P1.1` Harden Windows FFmpeg/DirectShow client capture and unit coverage

> TDC Result Contract. A phase is NOT closed by "it works" — only by this report with real evidence.

## Machine fields

```yaml
task_id: WF-P1.1
status: done
runtime: claude-code
closed_at: 2026-06-27
checkpoints: []          # no commit yet — commit/push require explicit user GO
project: whisperflow-cloud
next_recommended: WF-P2.1
go_source: 'user GO 2026-06-27 ("Continúa con WF-P1.1" — AskUserQuestion)'
```

## Scope

- Files adopted/owned by this phase (pre-TDC candidate, reviewed and accepted as-is — meets all acceptance criteria, no further edits required):
  - `whisperflow_client.py` (` M`, +135/−66) — DirectShow capture hardening
  - `tests/test_whisperflow_client_audio.py` (`??`) — 3 focused, fully-mocked unit tests
- Files touched by this phase's actions (governance only):
  - `docs/delivery/{TASKS.yaml,RUNBOOK.md,close/WF-P1.1.md,receipts.jsonl}`
- Files explicitly NOT touched: all dirty pre-existing paths; all `whisperflow/` runtime; all other tests.

## Behavior

- What changed: nothing new this phase — the candidate DirectShow hardening was **reviewed against
  the acceptance criteria and adopted as-is** (it already satisfies them). The phase formally takes
  ownership of `whisperflow_client.py` + its unit test and verifies them with the gate.
- What did NOT change: GUI state machine, sounddevice mic path, server, deploy state.

### Acceptance verification (criterion → evidence, `whisperflow_client.py`)

| Acceptance criterion | Evidence |
| --- | --- |
| DirectShow discovery parses devices + alternative names from stdout **or** stderr | `_discover_ffmpeg_devices` merges `stdout`+`stderr` (L415), case-insensitive section scan, captures `{name, alt}` incl. `Alternative name` (L437–442), plus heuristic fallback scan (L443–460) |
| System candidates prefer VB-Audio / Stereo Mix; honor name, alt-name, index overrides | `_score_ffmpeg_system_device` (L545–563): VB-Audio Cable +600, other virtual +520, system +400, stereo-mix/mezcla +80, alt +15; `_pick_override_ffmpeg_device` (L528–543) resolves digit→index→name and name/alt substrings |
| Startup tries alt names then pin fallback, deterministic order | `_ffmpeg_system_candidates` (L565–595) emits `:alt` then plain name, dedup via `seen`, override-first then score-sorted auto; `_start_system_capture` (L606–635) attempts `(None, spec)` then each `COMMON_AUDIO_PIN_NAMES` pin in fixed order |
| Stop / failed capture cannot leave the UI permanently disabled | three recovery paths: capture-error re-enables RECORD + mode (L1014–1016); 15s `_on_stop_timeout` → `_finish_processing` re-enables (L943–946, L924–933); connection-closed-while-awaiting → `_finish_processing` (L1126) |
| Error logs identify ffmpeg missing / no dshow devices / rejected candidates / selected alt name / selected pin | ffmpeg missing raises (L601); no dshow raises (L603) + discovery warns (L471); rejected `AUDIO_WARN: rejected … spec=… pin=…` (L643, L660); selected alt + pin in `AUDIO_DEVICE: … using alt=… pin=…` (L651, L653) |

## Validation (evidence — no claims without output)

- `.venv/bin/python -m pytest tests/test_whisperflow_client_audio.py -q` → **`3 passed in 0.08s`**
- `.venv/bin/python -m py_compile whisperflow_client.py tests/test_whisperflow_client_audio.py` → **OK**
- `.venv/bin/python -m black --check tests/test_whisperflow_client_audio.py` → **`1 file would be left unchanged`** (clean)
- `git diff --check` → **clean**
- line endings: `whisperflow_client.py` and the test are both **LF**

## Test gate (test-mapped delivery)

- `test_strategy`: `functional`
- `tdc_verify.py --task WF-P1.1`:
  - `[PASS] pytest tests/test_whisperflow_client_audio.py -q`
  - `[PASS] py_compile whisperflow_client.py tests/test_whisperflow_client_audio.py`
  - `[PASS] git diff --check`
  - **ALL GREEN -> close done (3/3 passed)**, exit 0
- Result: **all green**

## Persistence (required to close)

- **context_agent** (PRIMARY): **saved** — WF-P1.1 adoption + acceptance verification persisted as project state.
- **enterprise_memory**: **none** — no genuine transversal lesson (project-specific client hardening).
- **memory index**: n/a.
- **Receipt:** `tdc_receipt.py --task WF-P1.1 --project whisperflow-cloud --context-agent-saved`
- **Verify (gate):** `tdc_persist.py --task WF-P1.1 --project whisperflow-cloud` → PERSISTED.

## Guardrails

- Deploy / smoke / traffic / paid run / push? **NO**
- `git add -A` avoided (explicit path staging only): **yes** — nothing staged/committed.
- Dirty pre-existing paths left untouched: **yes**
- `review_pre_tdc_directshow_diff_before_adopting`: **done** (full review above).
- `no_windows_assumptions_without_test_or_smoke_evidence`: honored — unit tests cover the discovery /
  candidate-ranking / alt→pin logic; the real Windows audio path is deferred to `WF-P3.1` smoke and
  not claimed here.

## Risks / follow-ups

- Minor GUI state inconsistencies in `_capture_worker` (NOT acceptance-blocking; UI is never *permanently*
  disabled, only momentarily inconsistent and user-recoverable):
  1. The capture-error path (L1010–1017) re-labels the button "RECORD" but does not reset
     `is_recording=False`, so the first click then routes through `_stop_recording` before recovering.
  2. A mid-capture device death (`read_chunk` → `active=False` → loop break, no exception, not awaiting
     stop) leaves the "RECORDING" label with STOP still enabled (recoverable by clicking STOP).
  These touch tkinter UI state and need manual smoke evidence → surface in **WF-P3.1**.
- OpenAI-era mocked server contract + production config validation → **WF-P2.1**.
- Commit of this phase (business/runtime vs test commits, separated) deferred to explicit user GO.

## Decision

- **GO / NO-GO:** **GO** — candidate adopted; all 5 acceptance criteria verified against code; gate 3/3 green.
- **Next recommended phase:** `WF-P2.1` — mocked server contract tests + production config validation. Each phase needs its own GO.
