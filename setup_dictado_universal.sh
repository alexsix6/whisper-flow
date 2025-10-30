#!/bin/bash

# Script de Configuración Automática para Dictado Universal
# WhisperFlow + Cliente Universal

set -e

echo "🎤 =========================================="
echo "   CONFIGURACIÓN DE DICTADO UNIVERSAL"
echo "   WhisperFlow + Cliente Universal"
echo "=========================================="

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Verificar que estamos en el directorio correcto
if [ ! -f "requirements.txt" ] || [ ! -d "whisperflow" ]; then
    print_error "Por favor ejecuta este script desde el directorio raíz del proyecto whisperflow-cloud"
    exit 1
fi

print_status "Paso 1/6: Verificando sistema operativo..."
OS="unknown"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
    print_success "Sistema detectado: Linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
    print_success "Sistema detectado: macOS"
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    OS="windows"
    print_success "Sistema detectado: Windows"
else
    print_warning "Sistema no identificado, asumiendo Linux"
    OS="linux"
fi

print_status "Paso 2/6: Configurando entorno virtual Python..."
if [ ! -d ".venv" ]; then
    print_status "Creando nuevo entorno virtual..."
    python3 -m venv .venv
    print_success "Entorno virtual creado"
else
    print_success "Entorno virtual ya existe"
fi

# Activar entorno virtual
print_status "Activando entorno virtual..."
source .venv/bin/activate
print_success "Entorno virtual activado"

print_status "Paso 3/6: Instalando dependencias base..."
pip install --upgrade pip
pip install -r requirements.txt
print_success "Dependencias base instaladas"

print_status "Paso 4/6: Instalando dependencias del cliente de dictado..."
pip install -r requirements_dictation.txt
print_success "Dependencias del cliente instaladas"

print_status "Paso 5/6: Instalando dependencias del sistema..."
if [ "$OS" = "linux" ]; then
    print_status "Instalando dependencias para Linux..."
    if command -v apt-get &> /dev/null; then
        print_status "Detectado apt-get, instalando dependencias Ubuntu/Debian..."
        sudo apt-get update
        sudo apt-get install -y python3-tk python3-dev portaudio19-dev
        print_success "Dependencias de Linux instaladas"
    elif command -v yum &> /dev/null; then
        print_status "Detectado yum, instalando dependencias RHEL/CentOS..."
        sudo yum install -y tkinter python3-devel portaudio-devel
        print_success "Dependencias de Linux instaladas"
    else
        print_warning "Gestor de paquetes no detectado. Instala manualmente:"
        print_warning "- tkinter, python3-dev, portaudio-dev"
    fi
elif [ "$OS" = "macos" ]; then
    if command -v brew &> /dev/null; then
        print_status "Instalando dependencias para macOS con Homebrew..."
        brew install python-tk portaudio
        print_success "Dependencias de macOS instaladas"
    else
        print_warning "Homebrew no detectado. Instala con: brew install python-tk portaudio"
    fi
else
    print_success "Windows: dependencias generalmente incluidas con Python"
fi

print_status "Paso 6/6: Verificando instalación..."

# Verificar que los modelos existen
if [ -f "whisperflow/models/small.pt" ]; then
    print_success "Modelo Whisper 'small.pt' encontrado"
else
    print_error "⚠️  Modelo 'small.pt' no encontrado en whisperflow/models/"
    print_warning "Los modelos se descargarán automáticamente al primer uso"
fi

# Verificar que el cliente se puede importar
python -c "
try:
    import pynput, pyperclip, websockets, pyaudio
    print('✓ Todas las dependencias del cliente importadas correctamente')
except ImportError as e:
    print(f'✗ Error importando dependencias: {e}')
    exit(1)
" || {
    print_error "Error en las dependencias del cliente"
    exit 1
}

print_success "Instalación completada exitosamente!"

echo ""
echo "🚀 =========================================="
echo "   PASOS PARA USAR EL DICTADO UNIVERSAL"
echo "=========================================="
echo ""
echo -e "${GREEN}1. Iniciar el servidor WhisperFlow:${NC}"
echo "   Terminal 1: ./run.sh -run-server"
echo ""
echo -e "${GREEN}2. Iniciar el cliente de dictado universal:${NC}"
echo "   Terminal 2: python universal_dictation_client.py"
echo ""
echo -e "${GREEN}3. Usar el dictado:${NC}"
echo "   - Abrir cualquier aplicación (Claude, ChatGPT, etc.)"
echo "   - Hacer clic en un campo de texto"
echo "   - Presionar Ctrl+Space para grabar"
echo "   - Hablar claramente"
echo "   - Presionar Ctrl+Space de nuevo para transcribir"
echo "   - El texto aparece automáticamente ✨"
echo ""
echo -e "${BLUE}📖 Documentación completa:${NC} DICTADO_UNIVERSAL_SETUP.md"
echo ""
echo -e "${GREEN}¡Tu sistema de dictado universal está listo! 🎉${NC}"

# Crear script de inicio rápido
cat > start_dictado.sh << 'EOF'
#!/bin/bash
echo "🎤 Iniciando Sistema de Dictado Universal..."
echo "🔌 Terminal 1: Servidor WhisperFlow"
echo "📱 Terminal 2: Cliente de Dictado"
echo ""
echo "Presiona Ctrl+C en cualquier momento para detener"
echo ""

# Activar entorno virtual
source .venv/bin/activate

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

# Esperar un poco para que el servidor inicie
sleep 3

# Verificar que el servidor está corriendo
if curl -s http://localhost:8181/health > /dev/null; then
    echo "✅ Servidor WhisperFlow corriendo en puerto 8181"
else
    echo "❌ Error: Servidor no pudo iniciar"
    kill $SERVER_PID 2>/dev/null
    exit 1
fi

# Iniciar cliente de dictado
echo "🎤 Iniciando cliente de dictado universal..."
echo "📋 Hotkey: Ctrl+Space para comenzar/parar dictado"
python universal_dictation_client.py

# Limpiar al salir
cleanup
EOF

chmod +x start_dictado.sh
print_success "Script de inicio rápido creado: ./start_dictado.sh"

echo ""
echo -e "${YELLOW}💡 Tip: Ejecuta${NC} ${GREEN}./start_dictado.sh${NC} ${YELLOW}para iniciar todo automáticamente${NC}" 