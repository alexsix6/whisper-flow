#!/bin/bash
# WhisperFlow Auto-Start System Control Script
# Manages Docker server + systemd client

set -e

PROJECT_DIR="/mnt/d/Dev/whisperflow-cloud"
SERVICE_NAME="whisperflow-client"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Dependency checks
check_dependencies() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Error: docker not installed${NC}"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        echo -e "${RED}❌ Error: docker-compose not installed${NC}"
        exit 1
    fi

    if ! command -v systemctl &> /dev/null; then
        echo -e "${RED}❌ Error: systemctl not available${NC}"
        exit 1
    fi
}

# Start WhisperFlow
start_whisperflow() {
    echo -e "${GREEN}🚀 Starting WhisperFlow...${NC}"
    cd "$PROJECT_DIR"

    # Start Docker server
    echo "Starting Docker server..."
    docker-compose up -d

    # Wait for health check
    echo -e "${YELLOW}⏳ Waiting for server to be healthy...${NC}"
    for i in {1..12}; do
        if curl -sf http://localhost:8181/health > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Server healthy${NC}"
            break
        fi
        if [ $i -eq 12 ]; then
            echo -e "${YELLOW}⚠️  Health check timeout (server may still be starting)${NC}"
        fi
        sleep 5
    done

    # Start client
    echo "Starting systemd client..."
    sudo systemctl start "$SERVICE_NAME"
    sleep 2

    echo -e "${GREEN}✅ WhisperFlow started! (Ctrl+Space to dictate)${NC}"
}

# Stop WhisperFlow
stop_whisperflow() {
    echo -e "${YELLOW}🛑 Stopping WhisperFlow...${NC}"

    # Stop client first (graceful)
    echo "Stopping systemd client..."
    sudo systemctl stop "$SERVICE_NAME" 2>/dev/null || true

    # Stop server
    echo "Stopping Docker server..."
    cd "$PROJECT_DIR"
    docker-compose down

    echo -e "${GREEN}✅ WhisperFlow stopped${NC}"
}

# Show status
status_whisperflow() {
    echo -e "${GREEN}📊 WhisperFlow Status:${NC}"
    echo ""
    echo "Docker Server:"
    cd "$PROJECT_DIR"
    docker-compose ps
    echo ""
    echo "systemd Client:"
    sudo systemctl status "$SERVICE_NAME" --no-pager || true
}

# Show logs
logs_whisperflow() {
    echo -e "${GREEN}📋 WhisperFlow Logs (Ctrl+C to exit):${NC}"
    echo ""

    cd "$PROJECT_DIR"
    docker-compose logs -f &
    DOCKER_PID=$!

    sudo journalctl -u "$SERVICE_NAME" -f &
    JOURNAL_PID=$!

    trap "kill $DOCKER_PID $JOURNAL_PID 2>/dev/null" EXIT
    wait
}

# Restart WhisperFlow
restart_whisperflow() {
    stop_whisperflow
    sleep 2
    start_whisperflow
}

# Usage information
usage() {
    echo "Usage: $0 {start|stop|status|logs|restart}"
    echo ""
    echo "Commands:"
    echo "  start    - Start WhisperFlow (Docker server + systemd client)"
    echo "  stop     - Stop WhisperFlow gracefully"
    echo "  status   - Show status of both components"
    echo "  logs     - Tail logs from both components"
    echo "  restart  - Restart WhisperFlow"
    exit 1
}

# Main
check_dependencies

case "$1" in
    start)
        start_whisperflow
        ;;
    stop)
        stop_whisperflow
        ;;
    status)
        status_whisperflow
        ;;
    logs)
        logs_whisperflow
        ;;
    restart)
        restart_whisperflow
        ;;
    *)
        usage
        ;;
esac
