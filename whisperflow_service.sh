#!/bin/bash

# WhisperFlow - Servicio Permanente de Dictado Universal
# Este script ejecuta el sistema como servicio del sistema

SERVICE_NAME="whisperflow-dictado"
PROJECT_DIR="/mnt/d/Dev/whisperflow-cloud"
LOG_DIR="$PROJECT_DIR/logs"
PID_FILE="$PROJECT_DIR/whisperflow.pid"

# Crear directorio de logs
mkdir -p "$LOG_DIR"

case "$1" in
    start)
        echo "🚀 Iniciando servicio permanente WhisperFlow..."
        
        # Verificar si ya está corriendo
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if ps -p $PID > /dev/null 2>&1; then
                echo "❌ El servicio ya está corriendo (PID: $PID)"
                exit 1
            else
                rm -f "$PID_FILE"
            fi
        fi
        
        # Cambiar al directorio del proyecto
        cd "$PROJECT_DIR"
        
        # Activar entorno virtual y iniciar servidor en background
        source .venv/bin/activate
        nohup python -m uvicorn whisperflow.fast_server:app --host 0.0.0.0 --port 8181 > "$LOG_DIR/server.log" 2>&1 &
        SERVER_PID=$!
        
        # Esperar a que el servidor esté listo
        echo "⏳ Esperando servidor..."
        for i in {1..30}; do
            if curl -s http://localhost:8181/health > /dev/null 2>&1; then
                echo "✅ Servidor iniciado correctamente"
                break
            fi
            sleep 2
        done
        
        # Iniciar cliente en background
        nohup python universal_dictation_client.py > "$LOG_DIR/client.log" 2>&1 &
        CLIENT_PID=$!
        
        # Guardar PIDs
        echo "$SERVER_PID $CLIENT_PID" > "$PID_FILE"
        
        echo "🎉 Servicio WhisperFlow iniciado permanentemente!"
        echo "📋 Hotkey: Ctrl+Space para dictar en cualquier aplicación"
        echo "📁 Logs en: $LOG_DIR/"
        echo "🛑 Para detener: $0 stop"
        ;;
        
    stop)
        echo "🛑 Deteniendo servicio WhisperFlow..."
        
        if [ -f "$PID_FILE" ]; then
            PIDS=$(cat "$PID_FILE")
            for PID in $PIDS; do
                if ps -p $PID > /dev/null 2>&1; then
                    kill $PID
                    echo "✅ Proceso $PID detenido"
                fi
            done
            rm -f "$PID_FILE"
            echo "✅ Servicio WhisperFlow detenido"
        else
            echo "❌ El servicio no está corriendo"
        fi
        ;;
        
    status)
        if [ -f "$PID_FILE" ]; then
            PIDS=$(cat "$PID_FILE")
            RUNNING=0
            for PID in $PIDS; do
                if ps -p $PID > /dev/null 2>&1; then
                    RUNNING=1
                fi
            done
            
            if [ $RUNNING -eq 1 ]; then
                echo "✅ Servicio WhisperFlow está CORRIENDO"
                echo "📋 Presiona Ctrl+Space en cualquier aplicación para dictar"
            else
                echo "❌ Servicio WhisperFlow está PARADO"
                rm -f "$PID_FILE"
            fi
        else
            echo "❌ Servicio WhisperFlow está PARADO"
        fi
        ;;
        
    restart)
        $0 stop
        sleep 3
        $0 start
        ;;
        
    *)
        echo "Uso: $0 {start|stop|status|restart}"
        echo ""
        echo "Comandos:"
        echo "  start   - Iniciar servicio permanente"
        echo "  stop    - Detener servicio"
        echo "  status  - Ver estado del servicio"
        echo "  restart - Reiniciar servicio"
        echo ""
        echo "Una vez iniciado, solo presiona Ctrl+Space para dictar ✨"
        exit 1
        ;;
esac 