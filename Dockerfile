# Imagen base con Python 3.10 (mejor compatibilidad con WhisperFlow)
FROM python:3.10-slim

# Variables de entorno necesarias
ENV PORT=8181

# Instala dependencias del sistema necesarias para audio y compilación
# --no-install-recommends reduce el tamaño de la imagen
# build-essential incluye gcc y otras herramientas necesarias para compilar PyAudio
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    libsndfile1 \
    portaudio19-dev \
    # Limpia la caché de apt para reducir el tamaño de la imagen
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Crea y define el directorio de trabajo
WORKDIR /app

# Copia todo el contenido del proyecto al contenedor (respetando .dockerignore)
COPY . .

# Verifica la estructura de directorios para diagnóstico
RUN find /app -type d | sort

# Asegúrate de que la carpeta de modelos existe
RUN mkdir -p /app/whisperflow/models

# Models will be mounted as volume at runtime (not copied into image)
# COPY whisperflow/models/*.pt /app/whisperflow/models/

# Instala las dependencias de Python sin usar caché para reducir tamaño
# Configuración resiliente: timeouts y retries para evitar errores transitorios PyPI
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
        --timeout 60 \
        --retries 5 \
        -r requirements.txt

# Expone el puerto 8181 (WhisperFlow production port)
EXPOSE 8181

# Comando para ejecutar el servidor FastAPI con uvicorn
CMD ["uvicorn", "whisperflow.fast_server:app", "--host", "0.0.0.0", "--port", "8181"]