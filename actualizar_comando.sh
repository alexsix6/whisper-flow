#!/bin/bash
# Script para actualizar el comando global whisperflow

echo "🔧 Actualizando comando whisperflow global..."
echo ""

# Copiar versión nueva (con GUI) al sistema
sudo cp /mnt/d/Dev/whisperflow-cloud/whisperflow_no_systemd.sh /usr/local/bin/whisperflow

# Dar permisos de ejecución
sudo chmod +x /usr/local/bin/whisperflow

echo ""
echo "✅ Comando whisperflow actualizado con versión GUI"
echo ""
echo "Ahora el comando 'whisperflow start' usará la interfaz gráfica"
echo ""
