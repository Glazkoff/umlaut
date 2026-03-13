#!/bin/bash
# Umlaut - Installer & Updater
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Glazkoff/umlaut/main/install.sh | bash          # Install
#   curl -fsSL https://raw.githubusercontent.com/Glazkoff/umlaut/main/install.sh | bash -s -- update  # Update
#   ./install.sh install   # Install
#   ./install.sh update    # Update existing
#   ./install.sh restart   # Restart systemd service
#   ./install.sh status    # Check status

set -e

INSTALL_DIR="${INSTALL_DIR:-$HOME/.openclaw/workspace/umlaut}"
SERVICE_NAME="umlaut"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERR]${NC} $1"; }

check_python() {
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 not found. Install Python 3.10+ first."
        exit 1
    fi
}

install() {
    log_info "Installing Umlaut to $INSTALL_DIR"
    
    check_python
    
    # Clone or update
    if [ -d "$INSTALL_DIR/.git" ]; then
        log_info "Repository exists, updating..."
        cd "$INSTALL_DIR"
        git pull
    else
        log_info "Cloning repository..."
        rm -rf "$INSTALL_DIR"
        git clone https://github.com/Glazkoff/umlaut.git "$INSTALL_DIR"
        cd "$INSTALL_DIR"
    fi
    
    # Install dependencies
    if command -v uv &> /dev/null; then
        log_info "Installing dependencies with uv..."
        uv sync
    else
        log_info "Creating virtual environment..."
        python3 -m venv .venv
        source .venv/bin/activate
        pip install --upgrade pip -q
        pip install -r requirements.txt -q
    fi
    
    # Create directories
    mkdir -p "$HOME/.openclaw/workspace/evolution"
    mkdir -p "$HOME/.openclaw/workspace/repos"
    
    log_success "Umlaut installed!"
    
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Umlaut Installed!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "Start:"
    echo "  cd $INSTALL_DIR"
    if command -v uv &> /dev/null; then
        echo "  uv run uvicorn main:app --host 127.0.0.1 --port 8080"
    else
        echo "  source .venv/bin/activate"
        echo "  uvicorn main:app --host 127.0.0.1 --port 8080"
    fi
    echo ""
    echo "Systemd (Linux):"
    echo "  sudo cp $INSTALL_DIR/umlaut.service /etc/systemd/system/"
    echo "  sudo systemctl daemon-reload"
    echo "  sudo systemctl enable umlaut"
    echo "  sudo systemctl start umlaut"
    echo ""
    echo "Access: http://localhost:8080"
}

update() {
    log_info "Updating Umlaut..."
    
    if [ ! -d "$INSTALL_DIR/.git" ]; then
        log_error "Umlaut not installed at $INSTALL_DIR"
        log_info "Run: ./install.sh install"
        exit 1
    fi
    
    cd "$INSTALL_DIR"
    
    # Stash any local changes
    git stash -q 2>/dev/null || true
    
    # Pull latest
    log_info "Pulling latest changes..."
    git pull
    
    # Update dependencies
    if command -v uv &> /dev/null; then
        log_info "Updating dependencies with uv..."
        uv sync
    else
        log_info "Updating dependencies with pip..."
        source .venv/bin/activate
        pip install -r requirements.txt --upgrade -q
    fi
    
    # Restart service if running
    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        log_info "Restarting systemd service..."
        sudo systemctl restart "$SERVICE_NAME"
        sleep 2
        log_success "Service restarted"
    fi
    
    # Show version
    VERSION=$(git log -1 --oneline 2>/dev/null | cut -d' ' -f1)
    log_success "Updated to $VERSION"
    
    echo ""
    echo "Changelog: https://github.com/Glazkoff/umlaut/commits/main"
}

restart() {
    if ! systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        log_error "Umlaut service not running"
        log_info "Start with: sudo systemctl start $SERVICE_NAME"
        exit 1
    fi
    
    log_info "Restarting Umlaut..."
    sudo systemctl restart "$SERVICE_NAME"
    sleep 2
    systemctl status "$SERVICE_NAME" --no-pager -l | head -15
}

status() {
    echo -e "${BLUE}Umlaut Status${NC}"
    echo ""
    
    # Check installation
    if [ -d "$INSTALL_DIR/.git" ]; then
        cd "$INSTALL_DIR"
        VERSION=$(git log -1 --oneline 2>/dev/null | cut -d' ' -f1)
        BRANCH=$(git branch --show-current 2>/dev/null)
        echo -e "Installation: ${GREEN}✓${NC} $INSTALL_DIR"
        echo "  Version: $VERSION"
        echo "  Branch: $BRANCH"
    else
        echo -e "Installation: ${RED}✗${NC} Not installed"
        exit 1
    fi
    
    echo ""
    
    # Check systemd
    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        echo -e "Service: ${GREEN}✓${NC} Running"
        systemctl status "$SERVICE_NAME" --no-pager | grep -E "Active|Main PID" | head -2
    elif systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
        echo -e "Service: ${YELLOW}○${NC} Stopped (enabled)"
    else
        echo -e "Service: ${YELLOW}○${NC} Not configured"
    fi
    
    echo ""
    
    # Check port
    if command -v ss &> /dev/null; then
        if ss -tlnp | grep -q ":8080"; then
            echo -e "Port 8080: ${GREEN}✓${NC} Listening"
        else
            echo -e "Port 8080: ${RED}✗${NC} Not in use"
        fi
    fi
    
    # Quick health check
    if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080/ 2>/dev/null | grep -q "200\|405"; then
        echo -e "Health: ${GREEN}✓${NC} Responding"
    else
        echo -e "Health: ${RED}✗${NC} Not responding"
    fi
}

logs() {
    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        journalctl -u "$SERVICE_NAME" -f
    else
        log_error "Service not running"
    fi
}

usage() {
    echo "Umlaut - Installer & Updater"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  install    Install Umlaut (default)"
    echo "  update     Update existing installation"
    echo "  restart    Restart systemd service"
    echo "  status     Check installation status"
    echo "  logs       View service logs (follow)"
    echo ""
    echo "Environment:"
    echo "  INSTALL_DIR=$INSTALL_DIR"
}

# Main
case "${1:-install}" in
    install)
        install
        ;;
    update|upgrade)
        update
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    logs)
        logs
        ;;
    -h|--help|help)
        usage
        ;;
    *)
        log_error "Unknown command: $1"
        usage
        exit 1
        ;;
esac
