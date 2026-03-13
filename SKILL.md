---
name: umlaut
description: Web interface for monitoring and controlling OpenClaw's self-evolution engine. Use for visual dashboard, project management, and thinking level configuration.
---

# Umlaut

Web UI for OpenClaw's self-evolution engine. Monitor, configure, and control evolution projects through a beautiful dashboard.

## Install

```bash
# Clone to workspace
git clone https://github.com/Glazkoff/umlaut.git ~/.openclaw/workspace/umlaut
cd ~/.openclaw/workspace/umlaut

# Install dependencies (uv recommended)
uv sync

# Or with pip
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
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

## Systemd (Linux)

```bash
# Install as service
sudo cp ~/.openclaw/workspace/umlaut/umlaut.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable umlaut
sudo systemctl start umlaut

# Commands
sudo systemctl status umlaut
sudo systemctl restart umlaut
journalctl -u umlaut -f
```

## Features

- **Dashboard**: Real-time evolution monitoring
- **Projects**: Create and manage evolution projects
- **Thinking Levels**: Configure per-phase thinking (LOW/MEDIUM/HIGH)
- **Logs**: View evolution execution logs
- **API**: REST API + WebSocket for real-time updates

## Requirements

- Python 3.10+
- uv or pip

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `UMLAUT_HOST` | `127.0.0.1` | Server host |
| `UMLAUT_PORT` | `8080` | Server port |
| `UMLAUT_DEBUG` | `false` | Debug mode |
| `LOG_LEVEL` | `INFO` | Logging level |

## When to Use

- Monitor evolution progress visually
- Configure thinking levels per phase
- Manage multiple evolution projects
- Debug evolution execution
- View real-time logs and metrics
