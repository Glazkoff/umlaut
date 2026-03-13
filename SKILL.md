---
name: umlaut
description: Web interface for monitoring and controlling OpenClaw's self-evolution engine. Use for visual dashboard, project management, and thinking level configuration.
---

# Umlaut

Web UI for OpenClaw's self-evolution engine. Monitor, configure, and control evolution projects through a beautiful dashboard.

## Install

```bash
# Clone and run installer
git clone https://github.com/Glazkoff/umlaut.git ~/.openclaw/workspace/umlaut
cd ~/.openclaw/workspace/umlaut
./install.sh
```

## Start

```bash
cd ~/.openclaw/workspace/umlaut

# With uv
uv run uvicorn main:app --host 127.0.0.1 --port 8080

# Or with venv
source .venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 8080
```

Access: http://localhost:8080

## Update

```bash
cd ~/.openclaw/workspace/umlaut
./install.sh update
```

Or one-liner:
```bash
curl -fsSL https://raw.githubusercontent.com/Glazkoff/umlaut/main/install.sh | bash -s -- update
```

## Commands

| Command | Description |
|---------|-------------|
| `./install.sh install` | Install Umlaut |
| `./install.sh update` | Update existing installation |
| `./install.sh restart` | Restart systemd service |
| `./install.sh status` | Check installation status |
| `./install.sh logs` | View service logs |
