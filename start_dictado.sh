#!/bin/bash
echo "🎤 Iniciando Sistema de Dictado Universal..."
echo "🔌 Terminal 1: Servidor WhisperFlow"
echo "📱 Terminal 2: Cliente de Dictado"
echo ""
echo "Presiona Ctrl+C en cualquier momento para detener"
echo ""

# Activar entorno virtual
source .venv/bin/activate

# Configurar audio para WSL2/WSLg
export DISPLAY=:0
export PULSE_SERVER="unix:/mnt/wslg/PulseServer"

# Función para limpiar procesos al salir
cleanup() {
    echo "🛑 Deteniendo servicios..."
    pkill -f "uvicorn whisperflow.fast_server"
    pkill -f "universal_dictation_client.py"
    exit 0
}
trap cleanup SIGINT

# Iniciar servidor en background
echo "🚀 Iniciando servidor WhisperFlow..."
uvicorn whisperflow.fast_server:app --host 0.0.0.0 --port 8181 &
SERVER_PID=$!

# Esperar y verificar que el servidor inicie correctamente
echo "⏳ Esperando a que el servidor cargue el modelo..."
MAX_RETRIES=12  # 12 intentos = 60 segundos máximo
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    sleep 5  # Esperar 5 segundos entre intentos
    
    if curl -s http://localhost:8181/health > /dev/null; then
        echo "✅ Servidor WhisperFlow corriendo en puerto 8181"
        break
    else
        RETRY_COUNT=$((RETRY_COUNT + 1))
        echo "⏳ Intento $RETRY_COUNT/$MAX_RETRIES - Servidor aún cargando..."
    fi
done

# Verificar si se agotaron los intentos
if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "❌ Error: Servidor no pudo iniciar después de 60 segundos"
    kill $SERVER_PID 2>/dev/null
    exit 1
fi

# Iniciar cliente de dictado
echo "🎤 Iniciando cliente de dictado universal..."
echo "📋 Hotkey: Ctrl+Space para comenzar/parar dictado"
python universal_dictation_client.py

# Limpiar al salir
cleanup
