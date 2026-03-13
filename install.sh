#!/bin/bash
# Umlaut - One-line installer
# Usage: curl -fsSL https://raw.githubusercontent.com/Glazkoff/umlaut/master/install.sh | bash

set -e

INSTALL_DIR="${1:-$HOME/.openclaw/workspace/umlaut}"

echo "🧬 Installing Umlaut to $INSTALL_DIR"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Install Python 3.10+ first."
    exit 1
fi

# Clone or update
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "📦 Updating existing installation..."
    cd "$INSTALL_DIR"
    git pull
else
    echo "📦 Cloning repository..."
    rm -rf "$INSTALL_DIR"
    git clone https://github.com/Glazkoff/umlaut.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Install dependencies
if command -v uv &> /dev/null; then
    echo "📦 Installing dependencies with uv..."
    uv sync
else
    echo "📦 Installing dependencies with pip..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip -q
    pip install -r requirements.txt -q
fi

# Create directories
mkdir -p "$HOME/.openclaw/workspace/evolution"
mkdir -p "$HOME/.openclaw/workspace/repos"

echo ""
echo "✅ Umlaut installed!"
echo ""
echo "Start:"
echo "  cd $INSTALL_DIR"
if command -v uv &> /dev/null; then
    echo "  uv run uvicorn main:app --host 127.0.0.1 --port 8080"
else
    echo "  source .venv/bin/activate && uvicorn main:app --host 127.0.0.1 --port 8080"
fi
echo ""
echo "Access: http://localhost:8080"
