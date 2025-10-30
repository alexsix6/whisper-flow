#!/bin/bash
###############################################################################
# WhisperFlow - Start GUI Only
# Inicia solo la GUI (asume que servidor ya está corriendo)
###############################################################################

set -e

PROJECT_DIR="/mnt/d/Dev/whisperflow-cloud"
cd "$PROJECT_DIR"

echo "🎤 Iniciando GUI WhisperFlow..."

# Verificar servidor
if ! curl -s http://localhost:8181/health > /dev/null 2>&1; then
    echo "❌ Servidor no está corriendo"
    echo "Ejecuta primero: ./start_server.sh"
    exit 1
fi

# Configurar WSLg
export DISPLAY=:0
export PULSE_SERVER="unix:/mnt/wslg/PulseServer"

# Activar venv y ejecutar
source .venv/bin/activate
python dictation_gui.py
