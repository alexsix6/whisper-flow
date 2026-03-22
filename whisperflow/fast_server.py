""" WhisperFlow Cloud - FastAPI WebSocket Server """

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

    # Auth check before accepting connection
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
            pass  # Client disconnected

    session = None
    session_id = None
    try:
        await websocket.accept()
        session = st.TranscribeSession(transcribe_async, send_back_async)
        session_id = session.id
        sessions[session_id] = session
        logging.info(f"Session {session_id} started from {websocket.client.host}")

        while True:
            data = await websocket.receive_bytes()
            if data:
                session.add_chunk(data)
            else:
                break

    except WebSocketDisconnect:
        logging.info(f"Session {session_id} client disconnected")
    except Exception as e:
        logging.error(f"Session {session_id}: {e}")
    finally:
        if session and session_id in sessions:
            try:
                await session.stop()
            except Exception:
                pass
            sessions.pop(session_id, None)
        logging.info(f"Session {session_id} closed ({len(sessions)} active)")


# --- Health Check ---
@app.get("/health")
async def health_check():
    """Health check for Cloud Run."""
    return {
        "status": "healthy",
        "version": __version__,
        "active_sessions": len(sessions),
    }
