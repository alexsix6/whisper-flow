# PHASE CLOSE — `WF-P2.1` Add mocked server contract tests and production config validation

> TDC Result Contract. A phase is NOT closed by "it works" — only by this report with real evidence.

## Machine fields

```yaml
task_id: WF-P2.1
status: done
runtime: claude-code
closed_at: 2026-06-27
checkpoints: []          # no commit yet — commit/push require explicit user GO
project: whisperflow-cloud
next_recommended: WF-P3.1
go_source: 'user GO 2026-06-27 ("Inicia la implementación del plan TDC"); reroll directed by external audit GO same day'
reroll: 'v1 (TestClient-based) reopened after external Codex audit found a non-deterministic hang; v2 is portal-free'
```

## Reroll history (transparency)

- **v1** used `starlette.testclient.TestClient` for the contract. It passed in this session
  (`5 passed`) but an **external Codex audit on a different WSL/DrvFs environment found it HANGS**
  (`tdc_verify` and `pytest -q` hung; even a minimal `FastAPI()` + `TestClient(app)` hung; root cause:
  `anyio.start_blocking_portal()`, the TestClient sync→async bridge). A gate that passes locally but
  hangs in audit is **not reproducible and not done** (commit-vs-deploy / external-audit-before-closure).
- **v2** (this close) removes the blocking-portal dependency entirely — no `TestClient`, no
  `start_blocking_portal`. Verified stable across repeated runs.

## Scope

- Files touched:
  - `tests/test_server_contract.py` (new, portal-free) — 6 mocked, offline tests
  - `docs/delivery/{TASKS.yaml,RUNBOOK.md,close/WF-P2.1.md,receipts.jsonl}`
- Files reviewed, intentionally NOT modified (no runtime change required):
  - `whisperflow/fast_server.py` — required-config error already explicit (`lifespan` raises
    `ValueError("OPENAI_API_KEY not configured")`); `AUTH_TOKEN` empty = dev mode by design.
  - `whisperflow/transcriber_openai.py` — mocked at the module boundary; not modified.
- Files explicitly NOT touched: all dirty pre-existing paths; the client; other tests.

## Behavior

- What changed: added a **portable, hermetic** server contract test module.
  `whisperflow.transcriber_openai` is mocked at the module boundary, so the contract runs with **no
  real OpenAI key, no network, and no `TestClient`/blocking portal**.
- Portal-free techniques used:
  - `/health` → `httpx.ASGITransport(app=fs.app)` + `httpx.AsyncClient` in the running event loop
    (no portal; ASGITransport does not run lifespan, so `/health` needs no key).
  - missing-key config error → enter `fs.lifespan(fs.app)` directly and assert `ValueError`.
  - auth accept/reject → pure `fs.verify_token` unit with monkeypatched `AUTH_TOKEN`.
  - websocket start/bytes/stop/session_stopped → raw ASGI driver: `await app(scope, receive, send)`
    with plain `asyncio.Queue` receive/send (no `TestClient`).
- What did NOT change: production runtime, deploy state, the client.

### Acceptance coverage (criterion → test)

| Acceptance criterion | Test |
| --- | --- |
| Health check covered without a real OpenAI key | `test_health_does_not_require_openai_key` (httpx ASGITransport) |
| Websocket start / bytes / stop / session_stopped with mocked transcription | `test_ws_accepts_valid_token_and_runs_stop_contract` (raw ASGI; asserts `session_started`, mocked `"hello world"`, `session_stopped`) |
| Auth token accept **and** reject paths | `test_verify_token_accept_and_reject` (unit), `test_ws_rejects_invalid_token` (close code 4001 before session), `test_ws_without_auth_token_allows_connection` (dev mode) |
| Required production config errors explicit and actionable | `test_missing_openai_key_fails_with_explicit_error` (`ValueError` matches `OPENAI_API_KEY`) |

## Validation (evidence — no claims without output)

- `.venv/bin/python -m pytest tests/test_server_contract.py -q` → **`6 passed in 7.62s`**, repeated → **`6 passed in 7.75s`** (stable, no hang)
- Full default gate `.venv/bin/python -m pytest -q` → **`13 passed, 1 skipped, 5 deselected in 13.35s`**
- `.venv/bin/python -m pytest --collect-only -q` → exit 0, `13/18 collected (5 deselected) in 12.29s` (no hang)
- `git diff --check` → **clean**
- `grep -E "TestClient|start_blocking_portal" tests/test_server_contract.py` → only in comments/docstring (no usage)

## Test gate (test-mapped delivery)

- `test_strategy`: `functional`
- `tdc_verify.py --task WF-P2.1` (post-reroll):
  - `[PASS] pytest tests/test_server_contract.py -q`
  - `[PASS] pytest --collect-only -q`
  - `[PASS] git diff --check`
  - **ALL GREEN -> close done (3/3 passed)**, exit 0
- Result: **all green**

## Persistence (required to close)

- **context_agent** (PRIMARY): **saved** — WF-P2.1 reroll record + portal-free approach + evidence persisted as project state.
- **enterprise_memory**: **`3b619d42-be74-40e5-a337-e6732374a2de`** — genuine transversal lesson:
  Starlette `TestClient`/`anyio.start_blocking_portal` hangs non-deterministically on WSL/DrvFs; use
  `httpx.ASGITransport` + direct lifespan + raw-ASGI websocket driver for portable FastAPI contract tests.
- **memory index**: n/a.
- **Receipt:** `tdc_receipt.py --task WF-P2.1 --project whisperflow-cloud --context-agent-saved --em-id 3b619d42-be74-40e5-a337-e6732374a2de`
- **Verify (gate):** `tdc_persist.py --task WF-P2.1 --project whisperflow-cloud` → PERSISTED.

## Guardrails

- Deploy / smoke / traffic / paid run / push? **NO**
- `git add -A` avoided (explicit path staging only): **yes** — nothing staged/committed.
- Dirty pre-existing paths left untouched: **yes**
- `mock_openai_api`, `no_real_network_calls`, `no_deploy`, `no_push`: honored — OpenAI mocked at the
  module boundary; contract runs fully offline; no portal/threaded transport.

## Risks / follow-ups

- The contract is verified against mocks; real deployed-server behavior (Cloud Run health, real
  websocket auth, real OpenAI transcription) is `WF-P3.1` manual smoke (hold).
- Config validation is intentionally minimal (only `OPENAI_API_KEY` is hard-required; `AUTH_TOKEN`
  empty = dev mode). Forbidding the unauthenticated dev mode in production is a policy decision to
  raise with the user before any runtime change.
- Commit of the test phases (separated from runtime) deferred to explicit user GO.

## Decision

- **GO / NO-GO:** **GO** — server contract covered offline and **portably** (no flaky TestClient/portal);
  all 4 acceptance criteria met; gate 3/3 green; stable across repeated runs.
- **Next recommended phase:** `WF-P3.1` — manual Windows client + Cloud Run server smoke. **Remains `hold`**
  until explicit user GO (external/manual, real audio + deployed endpoint, possible paid run).
