#!/bin/bash
# Install Evolution UI as a systemd service

set -e

SERVICE_DIR="/root/.openclaw/workspace/evolution-ui"
SERVICE_FILE="/etc/systemd/system/evolution-ui.service"

echo "🧬 Installing Evolution UI..."

# Install Python dependencies
echo "📦 Installing Python dependencies..."
cd "$SERVICE_DIR"
pip3 install -q fastapi uvicorn websockets pydantic python-multipart

# Copy service file
echo "📋 Installing systemd service..."
cp "$SERVICE_DIR/evolution-ui.service" "$SERVICE_FILE"

# Reload systemd
systemctl daemon-reload

# Enable and start service
echo "🚀 Starting Evolution UI..."
systemctl enable evolution-ui
systemctl restart evolution-ui

# Check status
sleep 2
if systemctl is-active --quiet evolution-ui; then
    echo "✅ Evolution UI is running!"
    echo ""
    echo "📍 Access the UI at: http://localhost:8080"
    echo ""
    echo "Commands:"
    echo "  Status:  systemctl status evolution-ui"
    echo "  Logs:    journalctl -u evolution-ui -f"
    echo "  Restart: systemctl restart evolution-ui"
    echo "  Stop:    systemctl stop evolution-ui"
else
    echo "❌ Evolution UI failed to start. Check logs:"
    echo "  journalctl -u evolution-ui -n 50"
fi
