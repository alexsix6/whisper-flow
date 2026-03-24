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

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# --- Configuration ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AUTH_TOKEN = os.getenv("WHISPERFLOW_AUTH_TOKEN", "")
ALLOWED_ORIGINS = os.getenv("WHISPERFLOW_ALLOWED_ORIGINS", "*").split(",")


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
        return await ts_openai.transcribe_pcm_chunks_openai_async(chunks, language="es")

    async def send_back_async(data: dict):
        try:
            await websocket.send_json(data)
        except Exception:
            pass

    session = None
    session_id = None

    async def start_session():
        nonlocal session, session_id
        if session is not None:
            return
        session = st.TranscribeSession(transcribe_async, send_back_async)
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
