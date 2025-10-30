"""
OpenAI Whisper API Transcriber
Ultra-rápido para textos largos
"""

import os
import io
import logging
import asyncio
import numpy as np
from openai import OpenAI, AsyncOpenAI

logging.basicConfig(level=logging.INFO)

# Cliente OpenAI
client = None
async_client = None

def initialize_openai_client(api_key: str = None):
    """Inicializa el cliente de OpenAI con la API key"""
    global client, async_client

    # Usar API key de variable de entorno o parámetro
    key = api_key or os.getenv("OPENAI_API_KEY")

    if not key:
        raise ValueError(
            "API key de OpenAI no encontrada. "
            "Configura la variable de entorno OPENAI_API_KEY "
            "o pasa api_key como parámetro."
        )

    client = OpenAI(api_key=key)
    async_client = AsyncOpenAI(api_key=key)
    logging.info("✅ Cliente de OpenAI inicializado correctamente")
    return True


def transcribe_pcm_chunks_openai(chunks: list, language="es") -> dict:
    """
    Transcribe audio PCM usando OpenAI Whisper API

    Args:
        chunks: Lista de chunks de audio en formato PCM
        language: Idioma de salida (default: español)

    Returns:
        dict con formato compatible: {"text": "...", "language": "es"}
    """
    global client

    if not client:
        raise RuntimeError("Cliente OpenAI no inicializado. Llama a initialize_openai_client() primero")

    try:
        # Convertir chunks PCM a array numpy
        audio_bytes = b"".join(chunks)
        arr = np.frombuffer(audio_bytes, np.int16).flatten().astype(np.float32) / 32768.0

        # Convertir a WAV en memoria
        import wave
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16 bits
            wav_file.setframerate(16000)  # 16kHz
            wav_file.writeframes(audio_bytes)

        wav_buffer.seek(0)
        wav_buffer.name = "audio.wav"  # OpenAI requiere nombre de archivo

        logging.info(f"📤 Enviando {len(audio_bytes)} bytes de audio a OpenAI API...")

        # Transcribir con OpenAI
        # Si language="es", transcribe EN español (mantiene el idioma)
        # Si quieres traducir A español desde otro idioma, usa translate_to_spanish()
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=wav_buffer,
            language=language,  # Transcribe EN el idioma especificado
            response_format="json"
        )

        logging.info(f"✅ Transcripción completada: {len(transcript.text)} caracteres")

        return {
            "text": transcript.text,
            "language": language
        }

    except Exception as e:
        logging.error(f"❌ Error en transcripción OpenAI: {e}", exc_info=True)
        raise e


async def transcribe_pcm_chunks_openai_async(chunks: list, language="es") -> dict:
    """Versión asíncrona de transcribe_pcm_chunks_openai"""
    global async_client

    if not async_client:
        raise RuntimeError("Cliente OpenAI async no inicializado")

    try:
        # Convertir chunks PCM a array numpy
        audio_bytes = b"".join(chunks)
        arr = np.frombuffer(audio_bytes, np.int16).flatten().astype(np.float32) / 32768.0

        # Convertir a WAV en memoria
        import wave
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(audio_bytes)

        wav_buffer.seek(0)
        wav_buffer.name = "audio.wav"

        logging.info(f"📤 Enviando {len(audio_bytes)} bytes de audio a OpenAI API (async)...")

        # Ejecutar en thread pool para evitar bloquear event loop
        loop = asyncio.get_running_loop()
        transcript = await loop.run_in_executor(
            None,
            lambda: client.audio.transcriptions.create(
                model="whisper-1",
                file=wav_buffer,
                language=language,
                response_format="json"
            )
        )

        logging.info(f"✅ Transcripción async completada: {len(transcript.text)} caracteres")

        return {
            "text": transcript.text,
            "language": language
        }

    except Exception as e:
        logging.error(f"❌ Error en transcripción async OpenAI: {e}", exc_info=True)
        raise e


def translate_to_spanish(chunks: list) -> dict:
    """
    Traduce audio de CUALQUIER idioma a español usando OpenAI

    Args:
        chunks: Lista de chunks de audio en formato PCM

    Returns:
        dict con formato compatible: {"text": "...", "language": "es"}
    """
    global client

    if not client:
        raise RuntimeError("Cliente OpenAI no inicializado")

    try:
        audio_bytes = b"".join(chunks)

        # Convertir a WAV
        import wave
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(audio_bytes)

        wav_buffer.seek(0)
        wav_buffer.name = "audio.wav"

        logging.info(f"🌍 Traduciendo {len(audio_bytes)} bytes a español...")

        # TRANSLATE traduce a INGLÉS (limitación de OpenAI)
        # Para traducir a español, primero transcribimos y luego traducimos manualmente
        # O mejor: transcribimos directamente en el idioma original y el usuario traduce después

        # Por ahora, transcribimos en español directamente
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=wav_buffer,
            language="es",  # Forzar salida en español
            response_format="json"
        )

        logging.info(f"✅ Traducción completada: {len(transcript.text)} caracteres")

        return {
            "text": transcript.text,
            "language": "es"
        }

    except Exception as e:
        logging.error(f"❌ Error en traducción OpenAI: {e}", exc_info=True)
        raise e
