"""OpenAI Speech-to-Text Transcriber (gpt-4o-mini-transcribe)"""

import os
import io
import wave
import logging
from openai import OpenAI, AsyncOpenAI

logging.basicConfig(level=logging.INFO)

# gpt-4o-mini-transcribe: better accuracy than whisper-1, auto language detection,
# lower cost than gpt-4o-transcribe. Supports same /v1/audio/transcriptions API.
MODEL = os.getenv("WHISPERFLOW_MODEL", "gpt-4o-mini-transcribe")
TRANSLATION_MODEL = os.getenv("WHISPERFLOW_TRANSLATION_MODEL", "gpt-4o-mini")

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
    logging.info(f"OpenAI client initialized (model: {MODEL})")
    return True


def _pcm_to_wav(audio_bytes: bytes, sample_rate: int = 16000) -> io.BytesIO:
    """Convert raw PCM bytes to WAV format in memory."""
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_bytes)
    wav_buffer.seek(0)
    wav_buffer.name = "audio.wav"
    return wav_buffer


def transcribe_pcm_chunks_openai(chunks: list, language=None, prompt=None) -> dict:
    """Sync transcription using OpenAI API."""
    global client
    if not client:
        raise RuntimeError("OpenAI client not initialized")

    audio_bytes = b"".join(chunks)
    wav_buffer = _pcm_to_wav(audio_bytes)

    logging.info(f"Sending {len(audio_bytes)} bytes ({MODEL})...")

    request = {
        "model": MODEL,
        "file": wav_buffer,
        "response_format": "json",
    }
    if language:
        request["language"] = language
    if prompt:
        request["prompt"] = prompt

    transcript = client.audio.transcriptions.create(**request)

    detected = getattr(transcript, "language", None) or language or "auto"
    logging.info(f"Transcribed: {len(transcript.text)} chars ({detected})")
    return {"text": transcript.text, "language": detected}


async def transcribe_pcm_chunks_openai_async(chunks: list, language=None, prompt=None) -> dict:
    """Async transcription using AsyncOpenAI client."""
    global async_client
    if not async_client:
        raise RuntimeError("AsyncOpenAI client not initialized")

    audio_bytes = b"".join(chunks)
    wav_buffer = _pcm_to_wav(audio_bytes)

    logging.info(f"Sending {len(audio_bytes)} bytes ({MODEL} async)...")

    request = {
        "model": MODEL,
        "file": wav_buffer,
        "response_format": "json",
    }
    if language:
        request["language"] = language
    if prompt:
        request["prompt"] = prompt

    transcript = await async_client.audio.transcriptions.create(**request)

    detected = getattr(transcript, "language", None) or language or "auto"
    logging.info(f"Transcribed: {len(transcript.text)} chars ({detected})")
    return {"text": transcript.text, "language": detected}


async def translate_text_openai_async(
    text: str,
    target_language: str = "Spanish",
    source_language: str | None = None,
    glossary: str | None = None,
) -> dict:
    """Translate transcript text to the configured output language."""
    global async_client
    if not async_client:
        raise RuntimeError("AsyncOpenAI client not initialized")

    source_text = (text or "").strip()
    if not source_text:
        return {"text": "", "language": target_language}

    glossary_text = (glossary or "").strip() or "None"
    source = (source_language or "auto").strip() or "auto"
    messages = [
        {
            "role": "system",
            "content": (
                "Translate transcripts faithfully to the target language. "
                "Do not summarize, add commentary, or omit content. Preserve names, "
                "brands, acronyms, commands, code identifiers, and technical terms "
                "unless they have a natural established translation."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Target language: {target_language}\n"
                f"Source language: {source}\n"
                f"Domain glossary: {glossary_text}\n\n"
                "Transcript:\n"
                f"{source_text}"
            ),
        },
    ]

    response = await async_client.chat.completions.create(
        model=TRANSLATION_MODEL,
        messages=messages,
        temperature=0,
    )
    translated = (response.choices[0].message.content or "").strip()
    logging.info(
        "Translated: %s -> %s (%s chars, %s)",
        source,
        target_language,
        len(translated),
        TRANSLATION_MODEL,
    )
    return {"text": translated, "language": target_language}
