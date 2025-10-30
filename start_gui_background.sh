#!/bin/bash
###############################################################################
# WhisperFlow - Start GUI in Background
# Inicia GUI en background (sin ocupar terminal)
###############################################################################

PROJECT_DIR="/mnt/d/Dev/whisperflow-cloud"
cd "$PROJECT_DIR"

# Verificar servidor
if ! curl -s http://localhost:8181/health > /dev/null 2>&1; then
    echo "❌ Servidor no está corriendo"
    echo "Ejecuta primero: ./whisperflow_simple.sh start"
    exit 1
fi

# Verificar si GUI ya está corriendo
if pgrep -f "dictation_gui.py" > /dev/null; then
    echo "⚠️  GUI ya está corriendo (PID: $(pgrep -f 'dictation_gui.py'))"
    echo "Para ver logs: tail -f /tmp/whisperflow-gui.log"
    exit 0
fi

# Configurar WSLg
export DISPLAY=:0
export PULSE_SERVER="unix:/mnt/wslg/PulseServer"

# Activar venv y ejecutar en background
echo "🚀 Iniciando GUI en background..."
source .venv/bin/activate
nohup python dictation_gui.py > /tmp/whisperflow-gui.log 2>&1 &
GUI_PID=$!

sleep 2

if ps -p $GUI_PID > /dev/null; then
    echo "✅ GUI iniciada en background (PID: $GUI_PID)"
    echo "📋 Logs: /tmp/whisperflow-gui.log"
    echo "🎤 La ventana de WhisperFlow debe estar visible"
    echo ""
    echo "Para detener:"
    echo "  pkill -f dictation_gui.py"
else
    echo "❌ GUI falló al iniciar"
    echo "Ver logs: cat /tmp/whisperflow-gui.log"
    exit 1
fi
