#!/bin/bash
# Umlaut Installation Script
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
        log_error "Python 3 not found. Please install Python 3.10 or higher."
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    REQUIRED_VERSION="3.10"
    
    if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
        log_error "Python $REQUIRED_VERSION or higher is required. Found: $PYTHON_VERSION"
        exit 1
    fi
    
    log_success "Python $PYTHON_VERSION found"
}

# Install Umlaut
install() {
    local INSTALL_DIR="${1:-$HOME/.openclaw/workspace/umlaut}"
    
    log_info "Installing Umlaut to $INSTALL_DIR"
    
    # Create parent directory
    mkdir -p "$(dirname "$INSTALL_DIR")"
    
    # Check if already installed
    if [ -d "$INSTALL_DIR/.git" ]; then
        log_warning "Umlaut already installed in $INSTALL_DIR"
        read -p "Reinstall? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Installation cancelled"
            exit 0
        fi
        rm -rf "$INSTALL_DIR"
    fi
    
    # Clone
    if command -v git &> /dev/null; then
        log_info "Cloning from GitHub..."
        git clone https://github.com/Glazkoff/umlaut.git "$INSTALL_DIR"
    else
        log_error "Git not found. Please install git."
        exit 1
    fi
    
    cd "$INSTALL_DIR"
    
    # Install dependencies
    if command -v uv &> /dev/null; then
        log_info "Installing dependencies with uv..."
        uv sync
    else
        log_info "Creating virtual environment..."
        python3 -m venv .venv
        source .venv/bin/activate
        pip install --upgrade pip
        pip install -r requirements.txt
    fi
    
    log_success "Dependencies installed"
    
    # Create necessary directories
    log_info "Creating directories..."
    mkdir -p "$HOME/.openclaw/workspace/evolution"
    mkdir -p "$HOME/.openclaw/workspace/repos"
    
    log_success "Directories created"
    
    log_success "Umlaut installed successfully!"
    
    # Print usage
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Umlaut Installation Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "Start server:"
    echo "  cd $INSTALL_DIR"
    if command -v uv &> /dev/null; then
        echo "  uv run uvicorn main:app --host 127.0.0.1 --port 8080"
    else
        echo "  source .venv/bin/activate"
        echo "  uvicorn main:app --host 127.0.0.1 --port 8080"
    fi
    echo ""
    echo "  Access UI:     http://localhost:8080"
    echo "  API docs:      http://localhost:8080/docs"
    echo ""
    echo "Systemd (Linux):"
    echo "  sudo cp $INSTALL_DIR/umlaut.service /etc/systemd/system/"
    echo "  sudo systemctl daemon-reload"
    echo "  sudo systemctl enable umlaut"
    echo "  sudo systemctl start umlaut"
    echo ""
}

# Uninstall Umlaut
uninstall() {
    local INSTALL_DIR="${1:-$HOME/.openclaw/workspace/umlaut}"
    
    log_warning "This will remove Umlaut from $INSTALL_DIR"
    read -p "Continue? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Uninstall cancelled"
        exit 0
    fi
    
    log_info "Stopping Umlaut..."
    pkill -f "uvicorn main:app" || true
    systemctl stop umlaut 2>/dev/null || true
    
    log_info "Removing files..."
    rm -rf "$INSTALL_DIR"
    
    log_success "Umlaut uninstalled"
}

# Update Umlaut
update() {
    local INSTALL_DIR="${1:-$HOME/.openclaw/workspace/umlaut}"
    
    if [ ! -d "$INSTALL_DIR" ]; then
        log_error "Umlaut not found at $INSTALL_DIR"
        exit 1
    fi
    
    log_info "Updating Umlaut..."
    cd "$INSTALL_DIR"
    
    # Pull latest changes
    git pull
    
    # Update deps
    if command -v uv &> /dev/null; then
        uv sync
    else
        source .venv/bin/activate
        pip install -r requirements.txt --upgrade
    fi
    
    log_success "Umlaut updated"
    
    # Restart if running as systemd
    if systemctl is-active umlaut &>/dev/null; then
        log_info "Restarting systemd service..."
        sudo systemctl restart umlaut
        log_success "Service restarted"
    fi
}

# Main
main() {
    local ACTION="${1:-install}"
    
    case "$ACTION" in
        install)
            check_python
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
            echo "  $0 install /opt/umlaut        # Install to custom directory"
            echo "  $0 uninstall                  # Remove Umlaut"
            echo "  $0 update                     # Update to latest version"
            exit 1
            ;;
    esac
}

main "$@"
