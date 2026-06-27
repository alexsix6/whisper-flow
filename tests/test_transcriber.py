"""Legacy local-Whisper transcriber tests (skipped).

The local PyTorch/Whisper engine — `whisperflow/transcriber.py` with `get_model`,
`transcribe_pcm_chunks`, and the `/transcribe_pcm_chunk` endpoint — was removed in
the OpenAI-API migration (v2 → v3). Every test in this module targeted that
deleted engine, so the module is skipped at collection time to keep the default
gate green without the removed dependency.

OpenAI-era transcription/server behavior is covered by the WF-P2.1 mocked server
contract tests (`tests/test_server_contract.py`).
"""

import pytest

pytest.skip(
    "legacy local Whisper engine removed in the OpenAI migration; "
    "OpenAI-era coverage lives in WF-P2.1 server contract tests",
    allow_module_level=True,
)
