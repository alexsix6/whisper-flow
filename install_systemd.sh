#!/bin/bash
set -e

CURRENT_USER=$(whoami)
SERVICE_FILE="whisperflow-client.service"
INSTALL_PATH="/etc/systemd/system/$SERVICE_FILE"

echo "📦 Installing systemd service for user: $CURRENT_USER"

# Replace user placeholder in service file
sed "s/User=aseis/User=$CURRENT_USER/g" $SERVICE_FILE > /tmp/$SERVICE_FILE

# Install service
echo "Installing service to $INSTALL_PATH..."
sudo cp /tmp/$SERVICE_FILE $INSTALL_PATH

# Reload systemd
echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

echo "✅ systemd service installed successfully"
echo ""
echo "To enable auto-start on boot:"
echo "  sudo systemctl enable $SERVICE_FILE"
echo ""
echo "To start the service now:"
echo "  sudo systemctl start whisperflow-client"
echo ""
echo "To check status:"
echo "  sudo systemctl status whisperflow-client"
