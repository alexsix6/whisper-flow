""" WhisperFlow Cloud - FastAPI WebSocket Server """

import json
import logging
import os
import hmac
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, Query
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketDisconnect

from whisperflow import __version__
import whisperflow.streaming as st
import whisperflow.transcriber_openai as ts_openai
import whisperflow.prompting as prompting

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# --- Configuration ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AUTH_TOKEN = os.getenv("WHISPERFLOW_AUTH_TOKEN", "")
ALLOWED_ORIGINS = os.getenv("WHISPERFLOW_ALLOWED_ORIGINS", "*").split(",")
EMIT_PARTIALS = os.getenv("WHISPERFLOW_PARTIALS", "").strip().lower() in {"1", "true", "yes", "on"}
OUTPUT_LANGUAGE = os.getenv("WHISPERFLOW_OUTPUT_LANGUAGE", "es").strip()
TRANSLATE_PARTIALS = os.getenv("WHISPERFLOW_TRANSLATE_PARTIALS", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
_OFF_VALUES = {"", "off", "0", "false", "no", "none", "disabled"}
_LANGUAGE_LABELS = {
    "es": "Spanish",
    "español": "Spanish",
    "spanish": "Spanish",
    "en": "English",
    "english": "English",
}
_LANGUAGE_CODES = {
    "español": "es",
    "spanish": "es",
    "english": "en",
}


# --- Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not configured")

    ts_openai.initialize_openai_client(OPENAI_API_KEY)
    logging.info(f"WhisperFlow v{__version__} started - OpenAI API ready")

    if AUTH_TOKEN:
        logging.info("Auth token configured - WebSocket connections require authentication")
    else:
        logging.warning("No WHISPERFLOW_AUTH_TOKEN set - WebSocket is UNAUTHENTICATED")

    if _translation_enabled(is_partial=False):
        logging.info(
            "Output translation enabled: target=%s partials=%s",
            _target_language_label(),
            TRANSLATE_PARTIALS,
        )
    else:
        logging.info("Output translation disabled")

    yield
    logging.info("WhisperFlow shutting down")


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)

sessions = {}
MAX_PROMPT_CHARS = int(os.getenv("WHISPERFLOW_PROMPT_CHARS", "400"))
# Static domain glossary prepended to the transcription prompt (biases vocabulary
# from the first chunk). Configurable via WHISPERFLOW_PROMPT / WHISPERFLOW_GLOSSARY.
BASE_PROMPT = prompting.load_base_prompt()
PROMPT_TOTAL_CHARS = int(os.getenv("WHISPERFLOW_PROMPT_TOTAL_CHARS", "800"))


def _append_prompt(prompt: str, text: str) -> str:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return prompt
    merged = f"{prompt} {cleaned}".strip() if prompt else cleaned
    return merged[-MAX_PROMPT_CHARS:]


def _output_language_value() -> str:
    return (OUTPUT_LANGUAGE or "").strip().lower()


def _translation_enabled(is_partial: bool) -> bool:
    value = _output_language_value()
    if value in _OFF_VALUES:
        return False
    return not is_partial or TRANSLATE_PARTIALS


def _target_language_label() -> str:
    value = _output_language_value()
    return _LANGUAGE_LABELS.get(value, OUTPUT_LANGUAGE.strip() or "Spanish")


def _target_language_code() -> str:
    value = _output_language_value()
    return _LANGUAGE_CODES.get(value, value or "es")


async def _translate_payload_if_needed(payload: dict, is_partial: bool) -> dict:
    if not _translation_enabled(is_partial):
        return payload

    source_text = (payload.get("text") or "").strip()
    if not source_text:
        return payload

    source_language = payload.get("language") or "auto"
    try:
        translated = await ts_openai.translate_text_openai_async(
            source_text,
            target_language=_target_language_label(),
            source_language=source_language,
            glossary=BASE_PROMPT,
        )
    except Exception as exc:
        logging.error("Translation failed: %s", exc)
        enriched = dict(payload)
        enriched["source_text"] = source_text
        enriched["source_language"] = source_language
        enriched["translation_error"] = str(exc)[:300]
        return enriched

    translated_text = (translated.get("text") or "").strip()
    if not translated_text:
        return payload

    enriched = dict(payload)
    enriched["source_text"] = source_text
    enriched["source_language"] = source_language
    enriched["text"] = translated_text
    enriched["language"] = _target_language_code()
    return enriched


def verify_token(token: str) -> bool:
    """Verify auth token using constant-time comparison."""
    if not AUTH_TOKEN:
        return True  # No token configured = allow all (dev mode)
    return hmac.compare_digest(token, AUTH_TOKEN)


# --- WebSocket Endpoint ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(default="")):
    """WebSocket endpoint for real-time audio transcription via OpenAI API."""

    if not verify_token(token):
        await websocket.close(code=4001, reason="Unauthorized")
        logging.warning(f"Rejected unauthorized WebSocket from {websocket.client.host}")
        return

    async def transcribe_async(chunks: list):
        logging.info(f"Transcribing {len(chunks)} audio chunks (partials={EMIT_PARTIALS})")
        result = await ts_openai.transcribe_pcm_chunks_openai_async(
            chunks,
            language=session_context["language"],
            prompt=prompting.build_prompt(
                BASE_PROMPT, session_context["prompt"], PROMPT_TOTAL_CHARS
            )
            or None,
        )
        logging.info(f"Transcription complete: {len((result.get('text') or '').strip())} chars")
        return result

    async def send_back_async(data: dict):
        payload = data.get("data") or {}
        is_partial = data.get("is_partial", False)
        detected_language = payload.get("language")
        if detected_language and detected_language != "auto" and not is_partial:
            session_context["language"] = detected_language

        text_value = (payload.get("text") or "").strip()
        if text_value and not is_partial:
            session_context["prompt"] = _append_prompt(session_context["prompt"], text_value)

        translated_payload = await _translate_payload_if_needed(payload, is_partial)
        if translated_payload is not payload:
            data = dict(data)
            data["data"] = translated_payload

        try:
            await websocket.send_json(data)
        except Exception:
            pass

    session = None
    session_id = None
    session_context = {"language": None, "prompt": ""}

    async def start_session():
        nonlocal session, session_id
        if session is not None:
            return
        session_context["language"] = None
        session_context["prompt"] = ""
        session = st.TranscribeSession(transcribe_async, send_back_async, emit_partials=EMIT_PARTIALS)
        session_id = session.id
        sessions[session_id] = session
        logging.info(f"Session {session_id} started from {websocket.client.host}")
        try:
            await websocket.send_json({"type": "session_started", "session_id": str(session_id)})
        except Exception:
            pass

    async def stop_session(notify: bool):
        nonlocal session, session_id
        current_session = session
        current_session_id = session_id
        session = None
        session_id = None

        if current_session is not None:
            try:
                await current_session.stop()
            except Exception as exc:
                logging.error(f"Session {current_session_id} stop failed: {exc}")
            sessions.pop(current_session_id, None)
            logging.info(f"Session {current_session_id} closed ({len(sessions)} active)")

        if notify:
            try:
                await websocket.send_json({"type": "session_stopped"})
            except Exception:
                pass

    try:
        await websocket.accept()

        while True:
            message = await websocket.receive()
            msg_type = message.get("type")

            if msg_type == "websocket.disconnect":
                raise WebSocketDisconnect()

            data = message.get("bytes")
            if data is not None:
                if session is None:
                    await start_session()
                if data:
                    session.add_chunk(data)
                continue

            raw_text = message.get("text")
            if raw_text is None:
                continue

            try:
                payload = json.loads(raw_text)
            except json.JSONDecodeError:
                logging.warning("Ignoring non-JSON websocket text frame")
                continue

            control = payload.get("type")
            if control == "stop":
                await stop_session(notify=True)
            elif control == "start":
                await start_session()
            elif control == "ping":
                await websocket.send_json({"type": "pong"})
            else:
                logging.warning(f"Ignoring unknown websocket control frame: {control}")

    except WebSocketDisconnect:
        logging.info(f"Session {session_id} client disconnected")
    except Exception as e:
        logging.error(f"Session {session_id}: {e}")
    finally:
        await stop_session(notify=False)


# --- Health Check ---
@app.get("/health")
async def health_check():
    """Health check for Cloud Run."""
    return {
        "status": "healthy",
        "version": __version__,
        "active_sessions": len(sessions),
    }
