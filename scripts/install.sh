#!/bin/bash
# Evolution UI Installation Script
# One-command installation for OpenClaw Evolution UI

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Log functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check Python version
check_python() {
    log_info "Checking Python version..."
    
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 not found. Please install Python 3.11 or higher."
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    REQUIRED_VERSION="3.11"
    
    if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
        log_error "Python $REQUIRED_VERSION or higher is required. Found: $PYTHON_VERSION"
        exit 1
    fi
    
    log_success "Python $PYTHON_VERSION found"
}

# Check OpenClaw installation
check_openclaw() {
    log_info "Checking OpenClaw installation..."
    
    if ! command -v openclaw &> /dev/null; then
        log_warning "OpenClaw not found. Some features may not work."
        log_info "Install OpenClaw: npm install -g openclaw"
    else
        log_success "OpenClaw found: $(openclaw --version)"
    fi
}

# Install Evolution UI
install() {
    local INSTALL_DIR="${1:-$HOME/.openclaw/workspace/umlaut}"
    
    log_info "Installing Evolution UI to $INSTALL_DIR"
    
    # Create directory
    mkdir -p "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    
    # Check if already installed
    if [ -f "main.py" ]; then
        log_warning "Evolution UI already installed in $INSTALL_DIR"
        read -p "Reinstall? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Installation cancelled"
            exit 0
        fi
    fi
    
    # Clone or download
    if command -v git &> /dev/null; then
        log_info "Cloning from GitHub..."
        git clone https://github.com/YOUR_USERNAME/umlaut.git . 2>/dev/null || {
            log_warning "Repository already exists, pulling latest..."
            git pull
        }
    else
        log_error "Git not found. Please install git or download manually."
        exit 1
    fi
    
    # Create virtual environment
    log_info "Creating virtual environment..."
    python3 -m venv .venv
    
    # Activate virtual environment
    source .venv/bin/activate
    
    # Install dependencies
    log_info "Installing dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    
    log_success "Dependencies installed"
    
    # Create necessary directories
    log_info "Creating directories..."
    mkdir -p "$HOME/.openclaw/workspace/evolution"
    mkdir -p "$HOME/.openclaw/workspace/repos"
    mkdir -p "/tmp/evolution-logs"
    
    log_success "Directories created"
    
    # Install as OpenClaw skill
    if command -v openclaw &> /dev/null; then
        log_info "Registering as OpenClaw skill..."
        openclaw skill register "$INSTALL_DIR/skill.json" 2>/dev/null || {
            log_warning "Failed to register as skill. Manual registration required."
        }
    fi
    
    # Create systemd service (optional)
    if [ "$EUID" -eq 0 ]; then
        log_info "Installing systemd service..."
        ./scripts/install-service.sh
    else
        log_info "Skipping systemd service (requires root). Run with sudo to install."
    fi
    
    log_success "Evolution UI installed successfully!"
    
    # Print usage
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Evolution UI Installation Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "Usage:"
    echo "  Start server:  cd $INSTALL_DIR && source .venv/bin/activate && uvicorn main:app --host 127.0.0.1 --port 8080"
    echo "  Or:            umlaut start"
    echo ""
    echo "  Access UI:     http://localhost:8080"
    echo "  API docs:      http://localhost:8080/docs"
    echo ""
    echo "Configuration:"
    echo "  Edit config:   $INSTALL_DIR/.env"
    echo "  View logs:     tail -f /tmp/umlaut.log"
    echo ""
    echo "Documentation:"
    echo "  README:        $INSTALL_DIR/README.md"
    echo "  API docs:      https://docs.openclaw.ai/umlaut"
    echo ""
}

# Uninstall Evolution UI
uninstall() {
    local INSTALL_DIR="${1:-$HOME/.openclaw/workspace/umlaut}"
    
    log_warning "This will remove Evolution UI from $INSTALL_DIR"
    read -p "Continue? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Uninstall cancelled"
        exit 0
    fi
    
    log_info "Stopping Evolution UI..."
    pkill -f "uvicorn main:app" || true
    
    log_info "Removing files..."
    rm -rf "$INSTALL_DIR"
    
    log_info "Unregistering skill..."
    openclaw skill unregister umlaut 2>/dev/null || true
    
    log_success "Evolution UI uninstalled"
}

# Update Evolution UI
update() {
    local INSTALL_DIR="${1:-$HOME/.openclaw/workspace/umlaut}"
    
    if [ ! -d "$INSTALL_DIR" ]; then
        log_error "Evolution UI not found at $INSTALL_DIR"
        exit 1
    fi
    
    log_info "Updating Evolution UI..."
    cd "$INSTALL_DIR"
    
    # Pull latest changes
    git pull
    
    # Activate venv and update deps
    source .venv/bin/activate
    pip install -r requirements.txt --upgrade
    
    log_success "Evolution UI updated"
    
    # Restart if running
    if pgrep -f "uvicorn main:app" > /dev/null; then
        log_info "Restarting server..."
        pkill -f "uvicorn main:app"
        sleep 2
        nohup .venv/bin/uvicorn main:app --host 127.0.0.1 --port 8080 > /tmp/umlaut.log 2>&1 &
        log_success "Server restarted"
    fi
}

# Main
main() {
    local ACTION="${1:-install}"
    local INSTALL_DIR="$HOME/.openclaw/workspace/umlaut"
    
    case "$ACTION" in
        install)
            check_python
            check_openclaw
            install "$2"
            ;;
        uninstall)
            uninstall "$2"
            ;;
        update)
            update "$2"
            ;;
        *)
            echo "Usage: $0 {install|uninstall|update} [directory]"
            echo ""
            echo "Examples:"
            echo "  $0 install                    # Install to ~/.openclaw/workspace/umlaut"
            echo "  $0 install /opt/umlaut  # Install to custom directory"
            echo "  $0 uninstall                  # Remove Evolution UI"
            echo "  $0 update                     # Update to latest version"
            exit 1
            ;;
    esac
}

main "$@"
