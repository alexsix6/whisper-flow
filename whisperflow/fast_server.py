""" fast api declaration """

import logging
import subprocess
import tempfile
import shutil
import asyncio # Asegúrate que esté importado
import os # Importación necesaria para el endpoint de diagnóstico
from contextlib import asynccontextmanager # Importa asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, WebSocket, Form, File, UploadFile, HTTPException

from whisperflow import __version__
import whisperflow.streaming as st
# transcriber.py (local model) REMOVED - OpenAI API only

# OpenAI Transcriber (opcional)
try:
    import whisperflow.transcriber_openai as ts_openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logging.warning("OpenAI library not available. Using local model only.")

# --- Inicio: Configuración y Carga de Modelo en Startup ---

# Configura el logging básico (Uvicorn/FastAPI pueden sobreescribirlo, pero asegura visibilidad)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuración del modo de transcripción
TRANSCRIPTION_MODE = os.getenv("TRANSCRIPTION_MODE", "openai")  # Solo OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Variables globales
use_openai = False  # Flag para saber si usar OpenAI (se activa en lifespan)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global use_openai
    logging.info("🚀 Iniciando ciclo de vida de la aplicación...")

    # Require OpenAI API (no fallback to local model)
    if not OPENAI_API_KEY:
        raise ValueError("❌ OPENAI_API_KEY no configurada en .env - OpenAI API es REQUERIDA")

    if not OPENAI_AVAILABLE:
        raise ImportError("❌ Librería openai no instalada - Ejecuta: pip install openai")

    try:
        ts_openai.initialize_openai_client(OPENAI_API_KEY)
        use_openai = True
        logging.info("✅ Modo OpenAI activado - Transcripción ultra-rápida disponible")
    except Exception as e:
        logging.error(f"❌ No se pudo inicializar OpenAI: {e}")
        raise

    yield

    logging.info("Finalizando ciclo de vida de la aplicación.")

app = FastAPI(lifespan=lifespan)

# --- Fin: Carga de Modelo en Startup ---

sessions = {} # Para websockets

# --- NUEVO ENDPOINT DE DIAGNÓSTICO ---
@app.get("/check_model_file/{model_filename}")
async def check_model_file(model_filename: str):
    """
    Verifica la existencia, tamaño y legibilidad de un archivo de modelo
    en la carpeta /app/whisperflow/models/.
    """
    logging.info(f"Solicitud de diagnóstico para: {model_filename}")
    # Construye la ruta absoluta esperada dentro del contenedor
    # __file__ es la ruta de este script (fast_server.py)
    base_dir = os.path.dirname(os.path.abspath(__file__)) # Directorio de fast_server.py (/app/whisperflow)
    model_dir = os.path.join(base_dir, "models") # /app/whisperflow/models
    model_path = os.path.join(model_dir, model_filename) # /app/whisperflow/models/nombre_archivo

    logging.info(f"Ruta absoluta calculada para verificar: {model_path}")

    result = {
        "model_filename": model_filename,
        "checked_path": model_path,
        "exists": False,
        "is_file": False,
        "size_bytes": None,
        "error": None,
        "directory_listing": None, # Para listar contenido si falla
        "directory_error": None
    }

    try:
        result["exists"] = os.path.exists(model_path)
        if result["exists"]:
            result["is_file"] = os.path.isfile(model_path)
            if result["is_file"]:
                # Intenta obtener el tamaño del archivo
                try:
                     result["size_bytes"] = os.path.getsize(model_path)
                except OSError as size_e:
                     logging.error(f"Error al obtener tamaño de {model_path}: {size_e}")
                     result["error"] = f"Error al obtener tamaño: {str(size_e)}"
            else:
                 result["error"] = "La ruta existe pero no es un archivo."
        else:
             # Si el archivo no existe, intenta listar el directorio models
             logging.warning(f"Archivo no encontrado en {model_path}. Listando directorio {model_dir}...")
             if os.path.isdir(model_dir):
                 try:
                     dir_contents = os.listdir(model_dir)
                     logging.info(f"Contenido de '{model_dir}': {dir_contents}")
                     result["directory_listing"] = dir_contents
                 except Exception as list_e:
                     logging.error(f"No se pudo listar el directorio '{model_dir}': {list_e}")
                     result["directory_error"] = str(list_e)
             else:
                  logging.error(f"El directorio de modelos '{model_dir}' tampoco existe.")
                  result["directory_error"] = "Directorio de modelos no encontrado."

    except Exception as e:
        logging.error(f"Error inesperado durante la verificación de {model_filename}: {e}", exc_info=True)
        result["error"] = f"Error inesperado: {str(e)}"

    # Devuelve 404 solo si el archivo específicamente no existe o no es un archivo
    if not result["exists"] or (result["exists"] and not result["is_file"]):
         raise HTTPException(status_code=404, detail=result)

    # Devuelve 200 OK con la información si el archivo existe (incluso si hubo error al leer tamaño)
    return result
# --- FIN ENDPOINT DE DIAGNÓSTICO ---

# DEPRECATED: /transcribe_pcm_chunk endpoint REMOVED
# GUI uses WebSocket (/ws) exclusively - no batch upload needed
# Local model (transcriber.py) removed in favor of OpenAI API only


# --- Endpoint WebSocket (OpenAI API only) ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Implementación de WebSocket usando OpenAI API."""
    global use_openai

    # Verificar que OpenAI esté disponible
    if not use_openai:
        logging.error("Intento de conexión WebSocket fallido: OpenAI API no disponible.")
        await websocket.close(code=1011, reason="OpenAI API no disponible")
        return

    logging.info("✅ OpenAI Whisper API disponible - WebSocket conectado")

    async def transcribe_async(chunks: list):
        # Usar OpenAI API
        return await ts_openai.transcribe_pcm_chunks_openai_async(chunks, language="es")

    async def send_back_async(data: dict):
        # Envía el resultado de vuelta al cliente
        try:
            await websocket.send_json(data)
        except Exception as e:
            logging.warning(f"Error al enviar JSON por WebSocket (cliente podría haberse desconectado): {e}")

    session = None # Inicializa session a None
    session_id = None
    try:
        await websocket.accept()
        # Crea la sesión de transcripción
        session = st.TranscribeSession(transcribe_async, send_back_async)
        session_id = session.id # Guarda el ID para logging
        sessions[session_id] = session
        logging.info(f"WebSocket session {session_id} iniciada.")

        while True:
            # Espera recibir datos binarios (chunks de audio PCM)
            data = await websocket.receive_bytes()
            if data:
                 logging.debug(f"WebSocket session {session_id} recibió {len(data)} bytes.")
                 # Añade el chunk a la sesión para ser procesado
                 session.add_chunk(data)
            else:
                 logging.info(f"WebSocket session {session_id} recibió mensaje vacío o señal de cierre.")
                 break # Salir del bucle si no hay datos

    except Exception as exception:
        logging.error(f"Error en WebSocket session {session_id if session_id else 'N/A'}: {exception}", exc_info=True)
    finally:
        logging.info(f"Cerrando WebSocket session {session_id if session_id else 'N/A'}")
        if session and session_id in sessions:
            try:
                await session.stop()
            except Exception as stop_e:
                 logging.error(f"Error al detener sesión {session_id}: {stop_e}")
            # Verifica si la clave existe antes de intentar eliminarla
            if session_id in sessions:
                del sessions[session_id]
        try:
            if websocket.client_state == websocket.client_state.CONNECTED:
                 await websocket.close()
                 logging.info(f"WebSocket {session_id if session_id else 'N/A'} cerrado correctamente.")
            else:
                 logging.info(f"WebSocket {session_id if session_id else 'N/A'} ya estaba cerrado o desconectado.")
        except Exception as close_e:
            logging.warning(f"Excepción al cerrar WebSocket {session_id if session_id else 'N/A'} (puede estar ya cerrado): {close_e}")


# --- Endpoint de Health Check ---
@app.get("/health")
async def health_check():
    """Endpoint simple para verificar si el servidor está corriendo"""
    global use_openai
    model_status = "openai_ready" if use_openai else "not_ready"
    return {
        "status": "healthy",
        "model_status": model_status,
        "transcription_mode": "openai",
        "server_version": __version__,
        "active_sessions": len(sessions)
    }