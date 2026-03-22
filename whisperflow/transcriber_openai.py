"""OpenAI Whisper API Transcriber"""

import os
import io
import wave
import logging
from openai import OpenAI, AsyncOpenAI

logging.basicConfig(level=logging.INFO)

client = None
async_client = None


def initialize_openai_client(api_key: str = None):
    """Initialize OpenAI client with API key."""
    global client, async_client

    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise ValueError("OPENAI_API_KEY not found")

    client = OpenAI(api_key=key)
    async_client = AsyncOpenAI(api_key=key)
    logging.info("OpenAI client initialized")
    return True


def _pcm_to_wav(audio_bytes: bytes, sample_rate: int = 16000) -> io.BytesIO:
    """Convert raw PCM bytes to WAV format in memory."""
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_bytes)
    wav_buffer.seek(0)
    wav_buffer.name = "audio.wav"
    return wav_buffer


def transcribe_pcm_chunks_openai(chunks: list, language="es") -> dict:
    """Sync transcription using OpenAI Whisper API."""
    global client
    if not client:
        raise RuntimeError("OpenAI client not initialized")

    audio_bytes = b"".join(chunks)
    wav_buffer = _pcm_to_wav(audio_bytes)

    logging.info(f"Sending {len(audio_bytes)} bytes to OpenAI API...")

    transcript = client.audio.transcriptions.create(
        model="whisper-1",
        file=wav_buffer,
        language=language,
        response_format="json",
    )

    logging.info(f"Transcription complete: {len(transcript.text)} chars")
    return {"text": transcript.text, "language": language}


async def transcribe_pcm_chunks_openai_async(chunks: list, language="es") -> dict:
    """Async transcription using AsyncOpenAI client."""
    global async_client
    if not async_client:
        raise RuntimeError("AsyncOpenAI client not initialized")

    audio_bytes = b"".join(chunks)
    wav_buffer = _pcm_to_wav(audio_bytes)

    logging.info(f"Sending {len(audio_bytes)} bytes to OpenAI API (async)...")

    transcript = await async_client.audio.transcriptions.create(
        model="whisper-1",
        file=wav_buffer,
        language=language,
        response_format="json",
    )

    logging.info(f"Transcription complete: {len(transcript.text)} chars")
    return {"text": transcript.text, "language": language}
