"""Mocked server contract tests for `whisperflow.fast_server` (OpenAI-era).

Portable + hermetic: no real OpenAI key, no network, and **no Starlette
`TestClient`** (its `anyio.start_blocking_portal` sync→async bridge hangs
intermittently on WSL/DrvFs). Instead:

- `/health` is driven with `httpx.ASGITransport` in the running event loop.
- the missing-key config error is asserted by entering `fast_server.lifespan` directly.
- auth accept/reject is a pure `verify_token` unit.
- the websocket start/bytes/stop/session_stopped contract is driven through the raw
  ASGI interface with plain `asyncio` queues (no blocking portal).

`whisperflow.transcriber_openai` is mocked at the module boundary, so the contract
never calls OpenAI. These tests are part of the default unit gate.
"""

import asyncio
import json

import httpx
import pytest

import whisperflow.fast_server as fs


@pytest.fixture
def mock_transcriber(monkeypatch):
    """Replace the OpenAI transcription call with a canned async result."""

    async def fake_transcribe(chunks, language=None, prompt=None):
        return {"text": "hello world", "language": "en"}

    monkeypatch.setattr(
        fs.ts_openai, "transcribe_pcm_chunks_openai_async", fake_transcribe
    )
    return fake_transcribe


# --- /health (no key, no lifespan, no portal) ---


@pytest.mark.asyncio
async def test_health_does_not_require_openai_key():
    transport = httpx.ASGITransport(app=fs.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert "version" in body
    assert "active_sessions" in body


# --- production config validation ---


@pytest.mark.asyncio
async def test_missing_openai_key_fails_with_explicit_error(monkeypatch):
    """Required production config error is explicit and actionable."""
    monkeypatch.setattr(fs, "OPENAI_API_KEY", "")
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        async with fs.lifespan(fs.app):
            pass


# --- auth accept / reject (pure) ---


def test_verify_token_accept_and_reject(monkeypatch):
    monkeypatch.setattr(fs, "AUTH_TOKEN", "secret")
    assert fs.verify_token("secret") is True
    assert fs.verify_token("wrong") is False
    # empty token configured = dev mode -> allow all
    monkeypatch.setattr(fs, "AUTH_TOKEN", "")
    assert fs.verify_token("anything") is True


# --- raw-ASGI websocket driver (no TestClient / no blocking portal) ---


class _ASGIWebSocket:
    """Drive a Starlette ASGI websocket app in the current event loop."""

    def __init__(self, app, scope):
        self._app = app
        self._scope = scope
        self._to_app = asyncio.Queue()
        self._from_app = asyncio.Queue()
        self._task = None
        self.handshake = None

    async def __aenter__(self):
        await self._to_app.put({"type": "websocket.connect"})
        self._task = asyncio.create_task(
            self._app(self._scope, self._to_app.get, self._from_app.put)
        )
        self.handshake = await asyncio.wait_for(self._from_app.get(), timeout=5)
        return self

    async def __aexit__(self, *exc):
        await self._to_app.put({"type": "websocket.disconnect", "code": 1000})
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()

    async def send_json(self, obj):
        await self._to_app.put({"type": "websocket.receive", "text": json.dumps(obj)})

    async def send_bytes(self, data):
        await self._to_app.put({"type": "websocket.receive", "bytes": data})

    async def receive_json(self):
        msg = await asyncio.wait_for(self._from_app.get(), timeout=5)
        if msg.get("type") == "websocket.close":
            raise AssertionError(f"server closed unexpectedly: {msg}")
        return json.loads(msg["text"])


def _ws_scope(query_string=b""):
    return {
        "type": "websocket",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "path": "/ws",
        "raw_path": b"/ws",
        "query_string": query_string,
        "headers": [],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "scheme": "ws",
        "subprotocols": [],
    }


@pytest.mark.asyncio
async def test_ws_rejects_invalid_token(monkeypatch, mock_transcriber):
    monkeypatch.setattr(fs, "AUTH_TOKEN", "secret")
    ws = _ASGIWebSocket(fs.app, _ws_scope(b"token=wrong"))
    async with ws:
        assert ws.handshake.get("type") == "websocket.close"
        assert ws.handshake.get("code") == 4001


@pytest.mark.asyncio
async def test_ws_accepts_valid_token_and_runs_stop_contract(monkeypatch, mock_transcriber):
    monkeypatch.setattr(fs, "AUTH_TOKEN", "secret")
    ws = _ASGIWebSocket(fs.app, _ws_scope(b"token=secret"))
    async with ws:
        assert ws.handshake.get("type") == "websocket.accept"

        await ws.send_json({"type": "start"})
        started = await ws.receive_json()
        assert started["type"] == "session_started"
        assert "session_id" in started

        await ws.send_bytes(b"\x00\x01" * 8000)
        await ws.send_json({"type": "stop"})

        types = []
        transcripts = []
        for _ in range(30):
            msg = await ws.receive_json()
            types.append(msg.get("type"))
            data = msg.get("data") or {}
            if data.get("text"):
                transcripts.append(data["text"])
            if msg.get("type") == "session_stopped":
                break

    assert "session_stopped" in types
    assert "hello world" in transcripts


@pytest.mark.asyncio
async def test_ws_without_auth_token_allows_connection(monkeypatch, mock_transcriber):
    """No AUTH_TOKEN configured = dev mode: connection accepted (ping/pong)."""
    monkeypatch.setattr(fs, "AUTH_TOKEN", "")
    ws = _ASGIWebSocket(fs.app, _ws_scope())
    async with ws:
        assert ws.handshake.get("type") == "websocket.accept"
        await ws.send_json({"type": "ping"})
        pong = await ws.receive_json()
    assert pong["type"] == "pong"
