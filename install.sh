#!/bin/bash
# WhisperFlow Auto-Start System - Master Installation Script

set -e

echo "🔧 Installing WhisperFlow Auto-Start System..."
echo ""

# Check dependencies
echo "Checking dependencies..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not installed. Please install Docker first."
    echo "   Visit: https://docs.docker.com/engine/install/"
    exit 1
fi
echo "✅ Docker installed"

if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose not installed. Please install docker-compose first."
    echo "   Visit: https://docs.docker.com/compose/install/"
    exit 1
fi
echo "✅ docker-compose installed"

if ! command -v systemctl &> /dev/null; then
    echo "❌ systemctl not available. This system requires systemd."
    exit 1
fi
echo "✅ systemd available"

# Check user in docker group
if ! groups | grep -q docker; then
    echo "⚠️  User not in docker group. Adding..."
    sudo usermod -aG docker $USER
    echo "⚠️  IMPORTANT: Logout and login again for docker group to take effect!"
    echo "   Then re-run this script."
    exit 1
fi
echo "✅ User in docker group"

# Validate Whisper models exist
echo ""
echo "Validating Whisper models..."
if ! ls whisperflow/models/*.pt &> /dev/null; then
    echo "❌ Whisper models not found in whisperflow/models/"
    echo "   Please download models first."
    exit 1
fi
MODEL_COUNT=$(ls whisperflow/models/*.pt | wc -l)
echo "✅ Whisper models found: $MODEL_COUNT files"

# Install systemd service
echo ""
echo "Installing systemd service..."
bash install_systemd.sh
sudo systemctl enable whisperflow-client
echo "✅ systemd service enabled (auto-start on boot)"

# Install CLI tool
echo ""
echo "Installing CLI tool..."
sudo cp whisperflow.sh /usr/local/bin/whisperflow
sudo chmod +x /usr/local/bin/whisperflow
echo "✅ CLI tool installed: /usr/local/bin/whisperflow"

# Build Docker image
echo ""
echo "Building Docker image (this may take 5-10 minutes)..."
docker-compose build
echo "✅ Docker image built"

# Test health endpoint
echo ""
echo "Testing Docker server startup..."
docker-compose up -d
echo "Waiting for server health check..."
HEALTHY=false
for i in {1..12}; do
    if curl -sf http://localhost:8181/health > /dev/null 2>&1; then
        echo "✅ Server is healthy"
        HEALTHY=true
        break
    fi
    sleep 5
    echo "   Waiting... ($i/12)"
done

if [ "$HEALTHY" = false ]; then
    echo "⚠️  Health check timeout. Server may need more time to load Whisper model."
    echo "   Check with: docker-compose logs"
fi

docker-compose down
echo ""

# Installation complete
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Installation complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Usage:"
echo "  whisperflow start   - Start WhisperFlow"
echo "  whisperflow stop    - Stop WhisperFlow"
echo "  whisperflow status  - Check status"
echo "  whisperflow logs    - View logs"
echo "  whisperflow restart - Restart WhisperFlow"
echo ""
echo "Auto-start enabled. WhisperFlow will start automatically on WSL2 boot."
echo ""
echo "To start now:"
echo "  whisperflow start"
echo ""
