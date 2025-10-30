#!/bin/bash
###############################################################################
# WhisperFlow - Launcher Simple (Sin systemd - Compatible WSL2)
# Automatiza inicio completo del sistema (Docker + GUI opcional)
###############################################################################

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_DIR="/mnt/d/Dev/whisperflow-cloud"
cd "$PROJECT_DIR"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}🎤 WhisperFlow - Inicio Automático${NC}"
echo -e "${GREEN}========================================${NC}"

# Modo: start, stop, status, gui
MODE="${1:-start}"

case "$MODE" in
    start)
        echo -e "\n${YELLOW}[1/3]${NC} Verificando Docker..."
        if ! docker info &> /dev/null; then
            echo -e "${RED}❌ Docker no está corriendo${NC}"
            echo -e "${YELLOW}Inicia Docker Desktop y vuelve a ejecutar${NC}"
            exit 1
        fi
        echo -e "${GREEN}✅ Docker OK${NC}"

        echo -e "\n${YELLOW}[2/3]${NC} Iniciando servidor..."
        docker-compose up -d

        echo -e "\n${YELLOW}[3/3]${NC} Esperando health check..."
        sleep 5

        if curl -s http://localhost:8181/health | grep -q "healthy"; then
            echo -e "${GREEN}✅ Servidor listo${NC}"
        else
            echo -e "${RED}❌ Servidor no responde${NC}"
            exit 1
        fi

        echo -e "\n${GREEN}========================================${NC}"
        echo -e "${GREEN}✅ WhisperFlow LISTO${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo -e "\n🎯 Para iniciar GUI:"
        echo -e "  ${YELLOW}./start_gui.sh${NC}"
        echo -e "\n🎯 Para detener:"
        echo -e "  ${YELLOW}./whisperflow_simple.sh stop${NC}"
        ;;

    stop)
        echo -e "${YELLOW}Deteniendo WhisperFlow...${NC}"

        # Matar GUI si está corriendo
        if pgrep -f "dictation_gui.py" > /dev/null; then
            echo "  - Deteniendo GUI..."
            pkill -f "dictation_gui.py"
        fi

        # Detener container
        echo "  - Deteniendo servidor..."
        docker-compose down

        echo -e "${GREEN}✅ WhisperFlow detenido${NC}"
        ;;

    status)
        echo -e "${GREEN}📊 Estado WhisperFlow:${NC}\n"

        echo "Docker Container:"
        docker-compose ps

        echo -e "\nGUI:"
        if pgrep -f "dictation_gui.py" > /dev/null; then
            echo -e "${GREEN}✅ Running${NC} (PID: $(pgrep -f 'dictation_gui.py'))"
        else
            echo -e "${YELLOW}⏸️  No running${NC}"
        fi

        echo -e "\nHealth Check:"
        curl -s http://localhost:8181/health || echo "❌ Servidor no responde"
        ;;

    gui)
        echo -e "${YELLOW}Iniciando GUI...${NC}"
        exec ./start_gui.sh
        ;;

    logs)
        echo -e "${GREEN}Logs (Ctrl+C para salir):${NC}\n"
        docker logs -f whisperflow-server
        ;;

    *)
        echo "Uso: $0 {start|stop|status|gui|logs}"
        echo ""
        echo "  start  - Inicia servidor Docker"
        echo "  stop   - Detiene todo (servidor + GUI)"
        echo "  status - Muestra estado del sistema"
        echo "  gui    - Inicia solo GUI (requiere servidor corriendo)"
        echo "  logs   - Ver logs del servidor"
        exit 1
        ;;
esac
