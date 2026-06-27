""" test streaming module — OpenAI-era safe subset.

The streaming loop (`whisperflow.streaming`) is engine-agnostic, so its unit
behavior is tested here with a dummy transcriber (no network, no model). The
in-process websocket path (`test_ws`) boots the FastAPI server lifespan, which
requires an OpenAI key and would issue real transcription calls, so it is marked
`integration` and excluded from the default gate. The former
`test_transcribe_streaming` exercised the removed local Whisper engine
(`whisperflow.transcriber.get_model`) and was dropped with that engine; see
`tests/test_transcriber.py` and the WF-P2.1 contract tests.
"""

import asyncio
from queue import Queue

import pytest

import tests.utils as ut
import whisperflow.streaming as st
import whisperflow.fast_server as fs


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


def test_streaming():
    """streaming.get_all drains a queue and tolerates None"""

    queue = Queue()
    queue.put(1)
    queue.put(2)
    res = st.get_all(queue)
    assert res == [1, 2]

    res = st.get_all(None)
    assert not res


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_ws(chunk_size=4096):
    """in-process websocket transcription — boots server lifespan + real OpenAI (integration)"""

    client = ut.TestClient(fs.app)
    with client.websocket_connect("/ws") as websocket:
        res = ut.load_resource("3081-166546-0000")
        chunks = [
            res["audio"][i : i + chunk_size]
            for i in range(0, len(res["audio"]), chunk_size)
        ]

        for chunk in chunks:
            websocket.send_bytes(chunk)

        await asyncio.sleep(3)
        websocket.close()

    assert client
