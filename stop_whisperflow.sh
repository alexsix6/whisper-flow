#!/bin/bash
###############################################################################
# WhisperFlow - Stop Everything
# Detiene servidor + GUI
###############################################################################

PROJECT_DIR="/mnt/d/Dev/whisperflow-cloud"
cd "$PROJECT_DIR"

echo "🛑 Deteniendo WhisperFlow..."

# Matar GUI si está corriendo
if pgrep -f "dictation_gui.py" > /dev/null; then
    echo "  Deteniendo GUI..."
    pkill -f "dictation_gui.py"
fi

# Detener container
echo "  Deteniendo servidor..."
docker-compose down

echo "✅ WhisperFlow detenido"
