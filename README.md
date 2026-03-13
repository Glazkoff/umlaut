# Umlaut - OpenClaw Self-Evolution Engine Web Interface

<div align="center">

![Umlaut](https://img.shields.io/badge/Umlaut-Engine-purple?style=for-the-badge)
![OpenClaw](https://img.shields.io/badge/OpenClaw-Skill-green?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.11+-yellow?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-red?style=for-the-badge)

**A modern web interface for monitoring and controlling OpenClaw's self-evolution engine**

[Features](#-features) • [Installation](#-installation) • [Quick Start](#-quick-start) • [Documentation](#-documentation) • [API](#-api-reference)

</div>

---

## 📖 Overview

Umlaut provides a real-time, interactive dashboard for managing autonomous code evolution in OpenClaw projects. Monitor progress, configure thinking levels, manage tasks, and control the evolution lifecycle through an intuitive web interface.

### What is Self-Evolution?

OpenClaw's self-evolution engine autonomously improves codebases by:
- **Analyzing** code quality, test coverage, and technical debt
- **Planning** prioritized improvements based on impact/effort/risk
- **Executing** code changes with automated testing
- **Reviewing** results and learning from outcomes

Umlaut makes this process **visible** and **controllable**.

---

## ✨ Features

### 🎯 Core Capabilities

- **📊 Real-time Dashboard**
  - Project status and phase tracking
  - Cycle progress with live updates
  - Budget and duration monitoring
  - Test coverage and quality metrics

- **🧠 Thinking Level Configuration**
  - Phase-specific thinking levels (ANALYZE, PLAN, EXECUTE, REVIEW)
  - Balance speed vs. quality
  - Adaptive model selection

- **📋 Task Management**
  - Kanban-style board (Backlog, In Progress, Done, Blocked)
  - Priority scoring (impact/effort/risk)
  - Task details and acceptance criteria

- **⏰ Cron Job Management**
  - Schedule automatic evolution cycles
  - Custom intervals (15/30/60/120 minutes)
  - One-click enable/disable

- **🔧 Debug Mode**
  - Active process monitoring
  - Recent log viewer
  - Command output inspection

- **⚡ Quick Actions**
  - Force next cycle
  - Pause/Resume/Stop evolution
  - Rollback all changes

### 🚀 Performance Optimizations

- **Incremental Testing**: Only run tests for changed modules (15-30 sec saved)
- **Skip Simple Reviews**: Auto-skip REVIEW for simple changes (10-15 min saved)
- **Reduced Context**: 50% smaller context files (5-10 sec saved)
- **Adaptive Thinking**: Phase-dependent thinking levels (30-60 sec saved)
- **Auto-restart**: 10-second delays between cycles (20 sec saved)

**Result**: 40-50% faster evolution cycles

---

## 📦 Installation

### Option 1: Clone & Install

```bash
git clone https://github.com/Glazkoff/umlaut.git ~/.openclaw/workspace/umlaut
cd ~/.openclaw/workspace/umlaut
./install.sh
```

### Option 2: One-Liner (if repo is public)

```bash
curl -fsSL https://raw.githubusercontent.com/Glazkoff/umlaut/main/install.sh | bash
```

### Option 2: Manual Install

```bash
# Clone to workspace
git clone https://github.com/Glazkoff/umlaut.git ~/.openclaw/workspace/umlaut
cd ~/.openclaw/workspace/umlaut

# Install dependencies with uv (recommended)
uv sync

# Or with pip
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Option 3: Systemd Service (Linux)

```bash
# After installation, enable as service:
sudo cp ~/.openclaw/workspace/umlaut/umlaut.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable umlaut
sudo systemctl start umlaut
```

### Option 4: Docker

```bash
# Build and run
docker build -t umlaut https://github.com/Glazkoff/umlaut.git
docker run -d -p 8080:8080 -v ~/.openclaw:/root/.openclaw --name umlaut umlaut
```

---

## 🚀 Quick Start

### 1. Start Umlaut

```bash
# If installed as skill
umlaut start

# Or manually
cd umlaut
source .venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 8080
```

### 2. Access Dashboard

Open http://localhost:8080 in your browser

### 3. Create Your First Project

```bash
# Via API
curl -X POST http://localhost:8080/api/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-project",
    "budget_limit": 50,
    "duration_hours": 8,
    "config": {
      "repo_url": "https://github.com/user/repo"
    }
  }'

# Or via UI
# Click "+ New Project" button
```

### 4. Configure Thinking Levels

```bash
# Via UI
# Navigate to "🧠 Thinking Levels Configuration"
# Adjust levels for each phase

# Via API
curl -X PUT "http://localhost:8080/api/projects/my-project/config/thinking?phase=EXECUTE&level=medium"
```

### 5. Start Evolution

```bash
# Via UI
# Click "▶ Start Evolution"

# Via API
curl -X POST http://localhost:8080/api/projects/my-project/start
```

### 6. Monitor Progress

- Watch real-time updates in dashboard
- Enable Debug Mode (🔧) for detailed logs
- Check Recent Activity feed
- View metrics and coverage

---

## 📖 Documentation

### Architecture

```
umlaut/
├── main.py                    # FastAPI backend
├── static/
│   ├── index.html            # Main HTML
│   ├── app.js                # JavaScript logic
│   └── style.css             # Styles
├── requirements.txt          # Python dependencies
├── Dockerfile                # Docker image
├── scripts/
│   ├── install.sh            # Installation script
│   └── install-service.sh    # Systemd setup
└── README.md                 # This file
```

### Evolution Phases

| Phase | Description | Thinking Level | Timeout |
|-------|-------------|----------------|---------|
| **IDLE** | Waiting to start | - | - |
| **ANALYZE** | Deep codebase analysis | high | 10 min |
| **PLAN** | Task prioritization | medium | 5 min |
| **EXECUTE** | Code implementation | medium | 10 min |
| **REVIEW** | Quality validation | low | 3 min |
| **PAUSED** | Evolution paused | - | - |
| **FINAL_REPORT** | Summary generation | - | - |
| **ASK_USER** | Needs human input | - | - |

### Thinking Levels

| Level | Speed | Quality | Use Case |
|-------|-------|---------|----------|
| **low** | ⚡⚡⚡ Fast | ⭐⭐ Basic | Quick checks, simple reviews |
| **medium** | ⚡⚡ Balanced | ⭐⭐⭐ Good | Most tasks, execution |
| **high** | ⚡ Slow | ⭐⭐⭐⭐⭐ Best | Complex analysis, critical changes |

**Recommended Configuration:**
- ANALYZE: `high` (deep understanding needed)
- PLAN: `medium` (balanced prioritization)
- EXECUTE: `medium` (fast implementation)
- REVIEW: `low` (quick validation)

### Task Priority Scoring

```python
priority_score = impact / (effort * risk)

# Example:
# impact = 8/10, effort = 5/10, risk = 2/10
# priority = 8 / (5 * 2) = 0.8
```

**Impact** (1-10): How much improvement?
**Effort** (1-10): How complex to implement?
**Risk** (1-10): What could go wrong?

---

## 🔌 API Reference

### Projects

```bash
# List all projects
GET /api/projects

# Get project details
GET /api/projects/{name}

# Create project
POST /api/projects
{
  "name": "my-project",
  "budget_limit": 50,
  "duration_hours": 8,
  "config": {"repo_url": "..."}
}

# Delete project
DELETE /api/projects/{name}
```

### Evolution Control

```bash
# Start evolution
POST /api/projects/{name}/start

# Pause evolution
POST /api/projects/{name}/pause

# Resume evolution
POST /api/projects/{name}/resume

# Stop evolution
POST /api/projects/{name}/stop

# Force next cycle
POST /api/projects/{name}/force-cycle

# Rollback all changes
POST /api/projects/{name}/rollback
```

### Tasks

```bash
# Get all tasks
GET /api/projects/{name}/tasks

# Create task
POST /api/projects/{name}/tasks
{
  "id": "task-123",
  "title": "Add unit tests",
  "description": "...",
  "category": "test",
  "impact": 8,
  "effort": 5,
  "risk": 2
}

# Move task
PUT /api/projects/{name}/tasks/{id}/move
{
  "new_status": "done"
}

# Delete task
DELETE /api/projects/{name}/tasks/{id}
```

### Configuration

```bash
# Get thinking levels
GET /api/projects/{name}/config

# Update thinking level
PUT /api/projects/{name}/config/thinking?phase=EXECUTE&level=medium
```

### Cron Jobs

```bash
# Get cron status
GET /api/cron/status

# Setup cron job
POST /api/cron/setup?project_name=my-project&interval_minutes=60

# Remove cron job
DELETE /api/cron/{project_name}
```

### System

```bash
# System health check
GET /api/system/status

# Evolution history
GET /api/projects/{name}/history?limit=20&debug=true

# Evolution report
GET /api/projects/{name}/report
```

### WebSocket

```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:8080/ws');

// Receive real-time updates
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Update:', data);
};

// Message types:
// - project_created
// - task_created, task_updated, task_moved
// - evolution_started, evolution_paused, evolution_stopped
```

---

## ⚙️ Configuration

### Environment Variables

```bash
# Server configuration
export UMLAUT_HOST=0.0.0.0
export UMLAUT_PORT=8080
export UMLAUT_DEBUG=false

# OpenClaw paths
export OPENCLAW_WORKSPACE=~/.openclaw/workspace
export EVOLUTION_DIR=~/.openclaw/workspace/evolution

# Logging
export LOG_LEVEL=INFO
export LOG_FILE=/var/log/umlaut.log
```

### Nginx Configuration

```nginx
server {
    listen 80;
    listen 443 ssl;
    server_name evo.example.com;

    ssl_certificate /etc/ssl/evo.example.com.crt;
    ssl_certificate_key /etc/ssl/evo.example.com.key;

    # WebSocket support
    location /ws {
        proxy_pass http://127.0.0.1:8080/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Systemd Service

```ini
[Unit]
Description=Umlaut - OpenClaw Self-Evolution Engine
After=network.target

[Service]
Type=simple
User=openclaw
WorkingDirectory=/opt/umlaut
Environment="PATH=/opt/umlaut/.venv/bin"
ExecStart=/opt/umlaut/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8080
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## 🔧 Troubleshooting

### Common Issues

#### Port 8080 Already in Use

```bash
# Find process using port
lsof -i :8080

# Kill process
kill -9 <PID>

# Or use different port
uvicorn main:app --host 127.0.0.1 --port 8081
```

#### WebSocket Connection Failed

```bash
# Check if server is running
curl http://localhost:8080/

# Check nginx config (if using nginx)
nginx -t

# Check firewall
sudo ufw allow 8080/tcp
```

#### Evolution Not Starting

```bash
# Check project state
cat ~/.openclaw/workspace/evolution/my-project/STATE.json | jq .

# Check logs
tail -f /tmp/evolution-logs/my-project-*.log

# Check cron jobs
crontab -l | grep evolution
```

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
uvicorn main:app --host 127.0.0.1 --port 8080 --reload

# Check logs in real-time
tail -f /tmp/umlaut.log
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- UI inspired by modern dashboard designs
- Powered by OpenClaw's self-evolution engine

---

<div align="center">

**Made with ❤️ by Nikita Glazkov**

[⬆ Back to Top](#umlaut---openclaw-self-evolution-engine-web-interface)

</div>
