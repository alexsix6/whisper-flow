#!/bin/bash
###############################################################################
# WhisperFlow - Start Server Only
# Inicia solo el servidor Docker (sin GUI)
###############################################################################

set -e

PROJECT_DIR="/mnt/d/Dev/whisperflow-cloud"
cd "$PROJECT_DIR"

echo "🚀 Iniciando servidor WhisperFlow..."

# Iniciar container
docker-compose up -d

# Esperar health check
echo "⏳ Esperando health check..."
sleep 5

# Verificar
if curl -s http://localhost:8181/health | grep -q "healthy"; then
    echo "✅ Servidor iniciado correctamente"
    echo "🌐 Health: http://localhost:8181/health"
    echo "🔌 WebSocket: ws://localhost:8181/ws"
else
    echo "❌ Servidor no responde - ver logs:"
    echo "   docker logs whisperflow-server"
    exit 1
fi
