""" test streaming module — OpenAI-era safe subset.

The streaming loop (`whisperflow.streaming`) is engine-agnostic, so its unit
behavior is tested here with a dummy transcriber (no network, no model). The
in-process websocket transcription path is covered portably in
`tests/test_server_contract.py` (raw-ASGI driver, mocked transcription) — no
Starlette `TestClient`, whose `anyio` blocking portal hangs on WSL/DrvFs. The
former `test_transcribe_streaming` exercised the removed local Whisper engine
(`whisperflow.transcriber.get_model`) and was dropped with that engine.
"""

import asyncio
from queue import Queue

import pytest

import whisperflow.streaming as st


@pytest.mark.asyncio
async def test_simple():
    """streaming.transcribe drains the queue and stops cleanly with a dummy transcriber"""

    queue, should_stop = Queue(), [False]
    queue.put(1)

    async def dummy_transcriber(items: list) -> dict:
        await asyncio.sleep(0.01)
        if queue.qsize() == 0:
            should_stop[0] = True
        return {"text": str(len(items))}

    async def dummy_segment_closed(_result: dict) -> None:
        await asyncio.sleep(0.01)

    await st.transcribe(should_stop, queue, dummy_transcriber, dummy_segment_closed)
    assert queue.qsize() == 0


@pytest.mark.asyncio
async def test_transcribe_final_only_waits_for_stop_before_transcribing():
    queue, should_stop = Queue(), [False]
    queue.put(b"audio-1")
    calls = []
    results = []

    async def dummy_transcriber(items: list) -> dict:
        calls.append(list(items))
        return {"text": f"final-{len(items)}"}

    async def dummy_segment_closed(result: dict) -> None:
        results.append(result)

    task = asyncio.create_task(
        st.transcribe(
            should_stop,
            queue,
            dummy_transcriber,
            dummy_segment_closed,
            emit_partials=False,
        )
    )
    await asyncio.sleep(0.05)
    assert calls == []

    queue.put(b"audio-2")
    should_stop[0] = True
    await task

    assert calls == [[b"audio-1", b"audio-2"]]
    assert len(results) == 1
    assert results[0]["is_partial"] is False
    assert results[0]["data"] == {"text": "final-2"}
    assert results[0]["time"] >= 0


def test_streaming():
    """streaming.get_all drains a queue and tolerates None"""

    queue = Queue()
    queue.put(1)
    queue.put(2)
    res = st.get_all(queue)
    assert res == [1, 2]

    res = st.get_all(None)
    assert not res
