#!/bin/bash
# Script de configuración de OpenAI API para WhisperFlow

echo "🔑 Configuración de OpenAI API para WhisperFlow"
echo "=============================================="
echo ""

# Verificar si ya existe .env
if [ -f ".env" ]; then
    echo "⚠️  Archivo .env ya existe. Haciendo backup..."
    cp .env .env.backup-$(date +%Y%m%d-%H%M%S)
fi

# Pedir API key al usuario
echo "Por favor ingresa tu OpenAI API Key:"
echo "(Debe empezar con 'sk-')"
read -p "API Key: " API_KEY

# Validar formato básico
if [[ ! $API_KEY =~ ^sk- ]]; then
    echo "❌ Error: La API key debe empezar con 'sk-'"
    echo "Verifica que copiaste la key correctamente"
    exit 1
fi

# Crear archivo .env
cat > .env <<EOF
# WhisperFlow - Configuración OpenAI
# Archivo generado el $(date)

OPENAI_API_KEY=$API_KEY
TRANSCRIPTION_MODE=openai
LOCAL_MODEL=small
PORT=8181
EOF

echo ""
echo "✅ Archivo .env creado exitosamente"
echo ""
echo "📋 Configuración:"
echo "   - Modo: OpenAI API (ultra-rápido)"
echo "   - Idioma: Español"
echo "   - Fallback: Modelo local 'small' (si API falla)"
echo ""
echo "🚀 Siguiente paso:"
echo "   Ejecuta: ./whisperflow_no_systemd.sh restart"
echo ""
echo "💰 Costos estimados:"
echo "   - 10 minutos de dictado/día = ~$1.80/mes"
echo "   - 30 minutos de dictado/día = ~$5.40/mes"
echo ""
