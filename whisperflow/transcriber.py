""" transcriber """

import os
import asyncio
import logging  # Añadido para logging detallado

import torch
import numpy as np

import whisper
from whisper import Whisper

# Configura el logging básico si aún no está configurado en otro lugar
# (FastAPI/Uvicorn usualmente lo manejan, pero esto asegura que los mensajes aparezcan)
logging.basicConfig(level=logging.INFO)

models = {}

def get_model(file_name="small.pt") -> Whisper:
    """Carga modelos desde el disco con verificación de ruta."""
    # Usa la caché si el modelo ya está cargado
    if file_name in models:
        logging.info(f"Usando modelo en caché: {file_name}")
        return models[file_name]

    # Construye la ruta absoluta al archivo del modelo dentro del contenedor
    # __file__ es la ruta de este script (transcriber.py)
    # os.path.abspath asegura que sea una ruta absoluta
    # os.path.dirname obtiene el directorio del script (/app/whisperflow/)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # Une el directorio base, la carpeta 'models', y el nombre del archivo
    path = os.path.join(base_dir, "models", file_name)

    logging.info(f"Intentando cargar modelo desde la ruta calculada: {path}")

    # --- Verificación Crítica en Tiempo de Ejecución ---
    if not os.path.exists(path):
        logging.error(f"¡ERROR CRÍTICO! El archivo del modelo NO FUE ENCONTRADO en: {path}")
        # Intenta listar el contenido del directorio 'models' para ayudar a depurar
        models_dir = os.path.join(base_dir, "models")
        if os.path.isdir(models_dir):
            try:
                dir_contents = os.listdir(models_dir)
                logging.error(f"Contenido encontrado en el directorio '{models_dir}': {dir_contents}")
            except Exception as e:
                logging.error(f"No se pudo listar el contenido de '{models_dir}': {e}")
        else:
            logging.error(f"El directorio de modelos '{models_dir}' tampoco fue encontrado.")
        # Lanza un error claro que será capturado por FastAPI y devuelto como 500
        raise FileNotFoundError(f"Archivo de modelo no encontrado en la ruta esperada: {path}")
    else:
        logging.info(f"Archivo de modelo ENCONTRADO en: {path}. Procediendo a cargar...")
    # --- Fin Verificación Crítica ---

    # Si el archivo existe, procede a cargarlo
    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logging.info(f"Cargando {file_name} en el dispositivo: {device}")
        loaded_model = whisper.load_model(path).to(device)
        models[file_name] = loaded_model  # Guarda en caché
        logging.info(f"Modelo {file_name} cargado y añadido a la caché.")
        return loaded_model
    except Exception as e:
        logging.error(f"Error al cargar el modelo desde '{path}': {e}", exc_info=True)
        # Lanza el error para que FastAPI lo maneje
        raise e


def transcribe_pcm_chunks(
    model: Whisper, chunks: list, task="transcribe", language="es", temperature=0.1, log_prob=-0.5
) -> dict:
    """Transcribe una lista de chunks PCM en el idioma especificado (por defecto español)."""
    try:
        audio_bytes = b"".join(chunks)
        arr = (
            np.frombuffer(audio_bytes, np.int16).flatten().astype(np.float32) / 32768.0
        )
        logging.info(f"Procesando {len(audio_bytes)} bytes de audio PCM para transcripción en {language}.")

        # Realiza la transcripción en el idioma especificado
        result = model.transcribe(
            arr,
            fp16=False,
            task=task,           # "transcribe" para mantener el idioma original/especificado
            language=language,   # "es" para transcribir en español
            logprob_threshold=log_prob,
            temperature=temperature,
        )
        logging.info(f"Transcripción completada en idioma: {language}.")
        return result
    except Exception as e:
        logging.error(f"Error durante la ejecución de model.transcribe: {e}", exc_info=True)
        raise e


async def transcribe_pcm_chunks_async(
    model: Whisper, chunks: list, task="transcribe", language="es", temperature=0.1, log_prob=-0.5
) -> dict:
    """Wrapper asíncrono para transcribir chunks PCM en el idioma especificado."""
    loop = asyncio.get_running_loop()
    # Llama a la función síncrona con los nuevos parámetros
    result = await loop.run_in_executor(
        None, transcribe_pcm_chunks, model, chunks, task, language, temperature, log_prob
    )
    return result