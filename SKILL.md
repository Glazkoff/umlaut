---
name: umlaut
description: Web interface for monitoring and controlling OpenClaw's self-evolution engine. Use for visual dashboard, project management, and thinking level configuration.
---

# Umlaut

Web UI for OpenClaw's self-evolution engine. Monitor, configure, and control evolution projects through a beautiful dashboard.

## Install

One command:

```bash
curl -fsSL https://raw.githubusercontent.com/Glazkoff/umlaut/main/scripts/install.sh | bash
```

Or clone manually:

```bash
git clone https://github.com/Glazkoff/umlaut.git ~/.openclaw/workspace/umlaut
cd ~/.openclaw/workspace/umlaut
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Start

```bash
cd ~/.openclaw/workspace/umlaut
source .venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 8080
```

Access: http://localhost:8080

## Commands

| Command | Description |
|---------|-------------|
| `umlaut start` | Start server on port 8080 |
| `umlaut stop` | Stop server |
| `umlaut restart` | Restart server |
| `umlaut status` | Check server status |
| `umlaut logs` | View logs |

## Features

- **Dashboard**: Real-time evolution monitoring
- **Projects**: Create and manage evolution projects
- **Thinking Levels**: Configure per-phase thinking (LOW/MEDIUM/HIGH)
- **Logs**: View evolution execution logs
- **API**: REST API + WebSocket for real-time updates

## Requirements

- Python 3.11+
- OpenClaw (optional, for full integration)

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
