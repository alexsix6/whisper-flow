#!/bin/bash
set -e

echo "🔧 Installing WhisperFlow Auto-Start System (WITHOUT systemd)..."
echo ""

# Colores para output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check dependencies
echo "Checking dependencies..."

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker installed${NC}"

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ docker-compose not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ docker-compose installed${NC}"

# Check if user is in docker group
if ! groups | grep -q docker; then
    echo -e "${YELLOW}⚠️  User not in docker group. Adding...${NC}"
    sudo usermod -aG docker $USER
    echo -e "${YELLOW}⚠️  You need to logout and login again for docker group to take effect${NC}"
    echo -e "${YELLOW}⚠️  After logout/login, run this script again${NC}"
    exit 0
fi
echo -e "${GREEN}✅ User in docker group${NC}"

# Validate Whisper models exist
MODEL_DIR="./whisperflow/models"
if [ ! -d "$MODEL_DIR" ]; then
    echo -e "${RED}❌ Models directory not found: $MODEL_DIR${NC}"
    exit 1
fi

MODEL_COUNT=$(find "$MODEL_DIR" -name "*.pt" | wc -l)
if [ $MODEL_COUNT -eq 0 ]; then
    echo -e "${RED}❌ No Whisper models found in $MODEL_DIR${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Whisper models found: $MODEL_COUNT files${NC}"
echo ""

# Build Docker image
echo "🐳 Building Docker image..."
docker-compose build
echo -e "${GREEN}✅ Docker image built${NC}"
echo ""

# Create startup script in user's home directory
STARTUP_SCRIPT="$HOME/.whisperflow_startup.sh"
echo "📝 Creating startup script: $STARTUP_SCRIPT"

cat > "$STARTUP_SCRIPT" << 'EOF'
#!/bin/bash
# WhisperFlow Auto-Start Script (NO systemd)
# This script is called from ~/.bashrc to auto-start WhisperFlow

PROJECT_DIR="/mnt/d/Dev/whisperflow-cloud"

# Check if already running
if docker ps | grep -q whisperflow-server; then
    echo "✅ WhisperFlow server already running"
    return 0
fi

# Start Docker server
echo "🚀 Starting WhisperFlow server..."
cd "$PROJECT_DIR"
docker-compose up -d

# Wait for server to be healthy
echo "⏳ Waiting for server to be ready..."
MAX_WAIT=60
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    if curl -s http://localhost:8181/health > /dev/null 2>&1; then
        echo "✅ WhisperFlow server is healthy"
        break
    fi
    sleep 2
    WAITED=$((WAITED + 2))
done

if [ $WAITED -ge $MAX_WAIT ]; then
    echo "⚠️  Server health check timeout (this is normal on first start)"
fi

# Start client in background
if ! pgrep -f "universal_dictation_client.py" > /dev/null; then
    echo "🎤 Starting dictation client..."
    cd "$PROJECT_DIR"

    # Export WSL2 audio variables
    export DISPLAY=:0
    export PULSE_SERVER="unix:/mnt/wslg/PulseServer"

    # Start client in background with nohup
    nohup .venv/bin/python universal_dictation_client.py > /tmp/whisperflow-client.log 2>&1 &

    echo "✅ WhisperFlow client started (PID: $!)"
    echo "📋 Logs: /tmp/whisperflow-client.log"
else
    echo "✅ WhisperFlow client already running"
fi

echo ""
echo "🎯 WhisperFlow is ready!"
echo "   Use Ctrl+Space to start/stop dictation"
echo ""
EOF

chmod +x "$STARTUP_SCRIPT"
echo -e "${GREEN}✅ Startup script created${NC}"
echo ""

# Add to .bashrc if not already present
BASHRC="$HOME/.bashrc"
if ! grep -q ".whisperflow_startup.sh" "$BASHRC"; then
    echo "📝 Adding auto-start to ~/.bashrc"
    cat >> "$BASHRC" << 'EOF'

# WhisperFlow Auto-Start
if [ -f "$HOME/.whisperflow_startup.sh" ]; then
    source "$HOME/.whisperflow_startup.sh"
fi
EOF
    echo -e "${GREEN}✅ Added to ~/.bashrc${NC}"
else
    echo -e "${YELLOW}⚠️  Auto-start already in ~/.bashrc${NC}"
fi
echo ""

# Install CLI tool to PATH
echo "🛠️  Installing CLI tool..."
sudo cp whisperflow_no_systemd.sh /usr/local/bin/whisperflow
sudo chmod +x /usr/local/bin/whisperflow
echo -e "${GREEN}✅ CLI tool installed: /usr/local/bin/whisperflow${NC}"
echo ""

# Installation complete
echo ""
echo "=========================================="
echo -e "${GREEN}✅ INSTALLATION COMPLETE!${NC}"
echo "=========================================="
echo ""
echo "📖 Usage:"
echo "   whisperflow start    - Start WhisperFlow"
echo "   whisperflow stop     - Stop WhisperFlow"
echo "   whisperflow status   - Check status"
echo "   whisperflow logs     - View logs"
echo "   whisperflow restart  - Restart everything"
echo ""
echo "🎯 Dictation Hotkey: Ctrl+Space"
echo ""
echo "⚡ Auto-Start: WhisperFlow will start automatically when you open a new terminal"
echo ""
echo "🚀 To start now, run:"
echo "   whisperflow start"
echo ""
