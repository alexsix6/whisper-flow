#!/bin/bash
# WhisperFlow Control Script (NO systemd version)
# Usage: whisperflow {start|stop|status|logs|restart}

set -e

PROJECT_DIR="/mnt/d/Dev/whisperflow-cloud"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

case "$1" in
  start)
    echo -e "${BLUE}🚀 Starting WhisperFlow...${NC}"
    echo ""

    # Start Docker server
    echo "Starting Docker server..."
    cd "$PROJECT_DIR"
    docker-compose up -d

    # Wait for health check
    echo "⏳ Waiting for server to be ready..."
    MAX_WAIT=60
    WAITED=0
    while [ $WAITED -lt $MAX_WAIT ]; do
        if curl -s http://localhost:8181/health > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Server is healthy${NC}"
            break
        fi
        sleep 2
        WAITED=$((WAITED + 2))
        echo -n "."
    done
    echo ""

    if [ $WAITED -ge $MAX_WAIT ]; then
        echo -e "${YELLOW}⚠️  Server health check timeout (may still be loading model)${NC}"
    fi

    # Start client (GUI version)
    if pgrep -f "dictation_gui.py" > /dev/null; then
        echo -e "${YELLOW}⚠️  Client GUI already running${NC}"
    else
        echo "🎤 Starting dictation client GUI..."
        cd "$PROJECT_DIR"

        # Export WSL2 audio variables
        export DISPLAY=:0
        export PULSE_SERVER="unix:/mnt/wslg/PulseServer"

        # Start GUI client
        .venv/bin/python dictation_gui.py > /tmp/whisperflow-client.log 2>&1 &
        CLIENT_PID=$!

        sleep 2

        # Check if client is still running
        if ps -p $CLIENT_PID > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Client GUI started (PID: $CLIENT_PID)${NC}"
            echo "📋 Una ventana debería aparecer en pantalla"
            echo "📋 Client logs: /tmp/whisperflow-client.log"
        else
            echo -e "${RED}❌ Client failed to start. Check logs: /tmp/whisperflow-client.log${NC}"
        fi
    fi

    echo ""
    echo -e "${GREEN}✅ WhisperFlow started${NC}"
    echo "🎯 Use Ctrl+Space to start/stop dictation"
    echo ""
    ;;

  stop)
    echo -e "${BLUE}🛑 Stopping WhisperFlow...${NC}"
    echo ""

    # Stop client (GUI version)
    if pgrep -f "dictation_gui.py" > /dev/null; then
        echo "Stopping dictation client GUI..."
        pkill -f "dictation_gui.py"
        echo -e "${GREEN}✅ Client GUI stopped${NC}"
    else
        echo "⚠️  Client GUI not running"
    fi

    # Stop Docker server
    echo "Stopping Docker server..."
    cd "$PROJECT_DIR"
    docker-compose down
    echo -e "${GREEN}✅ Server stopped${NC}"

    echo ""
    echo -e "${GREEN}✅ WhisperFlow stopped${NC}"
    echo ""
    ;;

  status)
    echo -e "${BLUE}📊 WhisperFlow Status:${NC}"
    echo ""

    # Docker server status
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Docker Server:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    cd "$PROJECT_DIR"
    docker-compose ps
    echo ""

    # Health check
    if curl -s http://localhost:8181/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Server health: HEALTHY${NC}"
    else
        echo -e "${RED}❌ Server health: UNHEALTHY${NC}"
    fi
    echo ""

    # Client status (GUI version)
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Dictation Client GUI:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if pgrep -f "dictation_gui.py" > /dev/null; then
        CLIENT_PID=$(pgrep -f "dictation_gui.py")
        echo -e "${GREEN}✅ Status: RUNNING${NC}"
        echo "   PID: $CLIENT_PID"
        echo "   Logs: /tmp/whisperflow-client.log"
        echo "   Ventana GUI debe estar visible"
    else
        echo -e "${RED}❌ Status: NOT RUNNING${NC}"
    fi
    echo ""
    ;;

  logs)
    echo -e "${BLUE}📋 WhisperFlow Logs (Ctrl+C to exit):${NC}"
    echo ""

    # Create a trap to cleanup background processes
    cleanup() {
        echo ""
        echo "Stopping log tail..."
        kill $DOCKER_PID $CLIENT_PID 2>/dev/null
        exit 0
    }
    trap cleanup SIGINT SIGTERM

    # Tail Docker logs
    cd "$PROJECT_DIR"
    docker-compose logs -f &
    DOCKER_PID=$!

    # Tail client logs
    if [ -f /tmp/whisperflow-client.log ]; then
        tail -f /tmp/whisperflow-client.log &
        CLIENT_PID=$!
    else
        echo "⚠️  Client log file not found: /tmp/whisperflow-client.log"
    fi

    # Wait for interrupt
    wait
    ;;

  restart)
    echo -e "${BLUE}🔄 Restarting WhisperFlow...${NC}"
    echo ""
    $0 stop
    sleep 2
    $0 start
    ;;

  *)
    echo "Usage: $0 {start|stop|status|logs|restart}"
    echo ""
    echo "Commands:"
    echo "  start    - Start WhisperFlow server and client"
    echo "  stop     - Stop WhisperFlow server and client"
    echo "  status   - Show status of all components"
    echo "  logs     - Show logs from server and client"
    echo "  restart  - Restart everything"
    echo ""
    exit 1
    ;;
esac
