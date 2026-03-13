#!/usr/bin/env python3
"""
Evolution UI - Web interface for OpenClaw Self-Evolution Engine

A Kanban-style task management and monitoring interface for autonomous
project evolution with OpenClaw.
"""

import json
import asyncio
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Configuration
WORKSPACE = Path.home() / ".openclaw" / "workspace"
EVOLUTION_DIR = WORKSPACE / "evolution"
REPOS_DIR = WORKSPACE / "repos"

app = FastAPI(
    title="Evolution UI",
    description="Web interface for OpenClaw Self-Evolution Engine",
    version="1.0.0"
)

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()


# ============== Models ==============

class Task(BaseModel):
    id: str
    title: str
    description: str = ""
    category: str = "improvement"
    priority_score: float = 5.0
    impact: int = 5
    effort: int = 5
    risk: int = 5
    status: str = "backlog"  # backlog, in_progress, done, blocked
    dependencies: List[str] = []
    acceptance_criteria: List[str] = []
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    blocked_reason: Optional[str] = None
    commits: List[str] = []
    files_changed: List[str] = []


# Ralph PRD Models
class UserStory(BaseModel):
    id: str = "US-001"
    title: str
    description: str = ""
    acceptanceCriteria: List[str] = []
    priority: int = 1
    passes: bool = False
    notes: str = ""


class PRD(BaseModel):
    project: str
    branchName: str
    description: str
    userStories: List[UserStory] = []


class Project(BaseModel):
    name: str
    phase: str = "IDLE"
    cycle: int = 0
    started_at: Optional[str] = None
    budget_limit: float = 50.0
    budget_used: float = 0.0
    duration_hours: int = 8
    stuck_counter: int = 0
    config: Dict[str, Any] = {}

class ProjectSummary(BaseModel):
    name: str
    phase: str
    cycle: int
    tasks_backlog: int
    tasks_in_progress: int
    tasks_done: int
    tasks_blocked: int
    budget_used_pct: float
    status: str  # idle, running, paused, completed, error


# ============== Helpers ==============

def get_project_dir(project_name: str) -> Path:
    return EVOLUTION_DIR / project_name

def load_json(project_name: str, filename: str) -> dict:
    path = get_project_dir(project_name) / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{filename} not found")
    return json.loads(path.read_text())

def save_json(project_name: str, filename: str, data: dict):
    path = get_project_dir(project_name) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

def list_projects() -> List[str]:
    if not EVOLUTION_DIR.exists():
        return []
    return [d.name for d in EVOLUTION_DIR.iterdir() if d.is_dir() and (d / "STATE.json").exists()]


# ============== API Routes ==============

@app.get("/api/projects")
async def get_projects() -> List[ProjectSummary]:
    """List all evolution projects with summary."""
    summaries = []
    for name in list_projects():
        try:
            state = load_json(name, "STATE.json")
            tasks = load_json(name, "TASKS.json")
            
            budget_used = state.get("budget", {}).get("cost_usd", 0)
            budget_limit = state.get("budget", {}).get("limit_usd", 50)
            
            status = "idle"
            phase = state.get("phase", "IDLE")
            if phase == "IDLE":
                status = "idle"
            elif phase in ["ANALYZE", "PLAN", "EXECUTE", "REVIEW"]:
                status = "running"
            elif phase == "PAUSED":
                status = "paused"
            elif phase == "FINAL_REPORT":
                status = "completed"
            elif phase == "ASK_USER":
                status = "needs_attention"
            
            summaries.append(ProjectSummary(
                name=name,
                phase=phase,
                cycle=state.get("cycle", 0),
                tasks_backlog=len(tasks.get("backlog", [])),
                tasks_in_progress=len(tasks.get("in_progress", [])),
                tasks_done=len(tasks.get("done", [])),
                tasks_blocked=len(tasks.get("blocked", [])),
                budget_used_pct=round(budget_used / budget_limit * 100, 1) if budget_limit > 0 else 0,
                status=status
            ))
        except Exception as e:
            print(f"Error loading project {name}: {e}")
    
    return summaries


@app.get("/api/projects/{project_name}")
async def get_project(project_name: str) -> dict:
    """Get full project details."""
    state = load_json(project_name, "STATE.json")
    tasks = load_json(project_name, "TASKS.json")
    metrics = load_json(project_name, "METRICS.json")
    constitution = (get_project_dir(project_name) / "CONSTITUTION.md").read_text() if (get_project_dir(project_name) / "CONSTITUTION.md").exists() else ""
    learnings = (get_project_dir(project_name) / "LEARNINGS.md").read_text() if (get_project_dir(project_name) / "LEARNINGS.md").exists() else ""
    
    return {
        "state": state,
        "tasks": tasks,
        "metrics": metrics,
        "constitution": constitution,
        "learnings": learnings
    }


@app.post("/api/projects")
async def create_project(project: Project):
    """Create a new evolution project."""
    project_dir = get_project_dir(project.name)
    if project_dir.exists():
        raise HTTPException(status_code=400, detail="Project already exists")
    
    project_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize files
    state = {
        "project": project.name,
        "phase": "IDLE",
        "cycle": 0,
        "started_at": None,
        "budget": {
            "limit_usd": project.budget_limit,
            "cost_usd": 0.0
        },
        "duration_hours": project.duration_hours,
        "stuck_counter": 0,
        "config": project.config
    }
    save_json(project.name, "STATE.json", state)
    save_json(project.name, "TASKS.json", {"backlog": [], "in_progress": [], "done": [], "blocked": []})
    save_json(project.name, "METRICS.json", {"baseline": {}, "current": {}, "delta": {}, "timeline": []})
    (project_dir / "CONSTITUTION.md").write_text("# Evolution Constitution\n\n## Core Principles\n\n1. Quality over quantity\n2. Tests are mandatory\n3. No breaking changes\n")
    (project_dir / "LEARNINGS.md").write_text("# Evolution Learnings\n\n")
    (project_dir / "HISTORY.jsonl").write_text("")
    
    # Broadcast update
    await manager.broadcast({"type": "project_created", "project": project.name})
    
    return {"status": "created", "project": project.name}


@app.delete("/api/projects/{project_name}")
async def delete_project(project_name: str):
    """Delete an evolution project."""
    import shutil
    project_dir = get_project_dir(project_name)
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project not found")
    
    shutil.rmtree(project_dir)
    await manager.broadcast({"type": "project_deleted", "project": project_name})
    
    return {"status": "deleted"}


# ============== Task Routes ==============

@app.get("/api/projects/{project_name}/tasks")
async def get_tasks(project_name: str) -> dict:
    """Get all tasks for a project."""
    return load_json(project_name, "TASKS.json")


@app.post("/api/projects/{project_name}/tasks")
async def create_task(project_name: str, task: Task):
    """Create a new task."""
    tasks = load_json(project_name, "TASKS.json")
    task_dict = task.model_dump()
    task_dict["created_at"] = datetime.utcnow().isoformat()
    tasks["backlog"].append(task_dict)
    save_json(project_name, "TASKS.json", tasks)
    
    await manager.broadcast({
        "type": "task_created",
        "project": project_name,
        "task": task_dict
    })
    
    return task_dict


@app.put("/api/projects/{project_name}/tasks/{task_id}")
async def update_task(project_name: str, task_id: str, task: Task):
    """Update a task."""
    tasks = load_json(project_name, "TASKS.json")
    
    # Find and update task in all lists
    for status in ["backlog", "in_progress", "done", "blocked"]:
        for i, t in enumerate(tasks[status]):
            if t["id"] == task_id:
                task_dict = task.model_dump()
                tasks[status][i] = task_dict
                save_json(project_name, "TASKS.json", tasks)
                
                await manager.broadcast({
                    "type": "task_updated",
                    "project": project_name,
                    "task": task_dict
                })
                
                return task_dict
    
    raise HTTPException(status_code=404, detail="Task not found")


@app.put("/api/projects/{project_name}/tasks/{task_id}/move")
async def move_task(project_name: str, task_id: str, new_status: str):
    """Move a task to a different status (Kanban drag-and-drop)."""
    if new_status not in ["backlog", "in_progress", "done", "blocked"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    tasks = load_json(project_name, "TASKS.json")
    
    # Find and remove task from current status
    task = None
    for status in ["backlog", "in_progress", "done", "blocked"]:
        for i, t in enumerate(tasks[status]):
            if t["id"] == task_id:
                task = tasks[status].pop(i)
                break
        if task:
            break
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Update timestamps
    if new_status == "in_progress" and not task.get("started_at"):
        task["started_at"] = datetime.utcnow().isoformat()
    if new_status == "done":
        task["completed_at"] = datetime.utcnow().isoformat()
    
    # Add to new status
    tasks[new_status].append(task)
    save_json(project_name, "TASKS.json", tasks)
    
    await manager.broadcast({
        "type": "task_moved",
        "project": project_name,
        "task_id": task_id,
        "new_status": new_status,
        "task": task
    })
    
    return task


@app.delete("/api/projects/{project_name}/tasks/{task_id}")
async def delete_task(project_name: str, task_id: str):
    """Delete a task."""
    tasks = load_json(project_name, "TASKS.json")
    
    for status in ["backlog", "in_progress", "done", "blocked"]:
        for i, t in enumerate(tasks[status]):
            if t["id"] == task_id:
                tasks[status].pop(i)
                save_json(project_name, "TASKS.json", tasks)
                
                await manager.broadcast({
                    "type": "task_deleted",
                    "project": project_name,
                    "task_id": task_id
                })
                
                return {"status": "deleted"}
    
    raise HTTPException(status_code=404, detail="Task not found")


# ============== Evolution Control ==============

@app.post("/api/projects/{project_name}/start")
async def start_evolution(project_name: str, budget: Optional[float] = None, duration_hours: Optional[int] = None):
    """Start evolution for a project."""
    state = load_json(project_name, "STATE.json")
    
    if state["phase"] not in ["IDLE", "PAUSED"]:
        raise HTTPException(status_code=400, detail=f"Cannot start: phase is {state['phase']}")
    
    state["phase"] = "ANALYZE"
    state["started_at"] = datetime.utcnow().isoformat()
    if budget:
        state["budget"]["limit_usd"] = budget
    if duration_hours:
        state["duration_hours"] = duration_hours
    
    save_json(project_name, "STATE.json", state)
    
    # TODO: Create cron job via OpenClaw API
    
    await manager.broadcast({
        "type": "evolution_started",
        "project": project_name,
        "state": state
    })
    
    return state


@app.post("/api/projects/{project_name}/pause")
async def pause_evolution(project_name: str):
    """Pause evolution for a project."""
    state = load_json(project_name, "STATE.json")
    state["phase"] = "PAUSED"
    save_json(project_name, "STATE.json", state)
    
    await manager.broadcast({
        "type": "evolution_paused",
        "project": project_name
    })
    
    return state


@app.post("/api/projects/{project_name}/resume")
async def resume_evolution(project_name: str):
    """Resume paused evolution."""
    state = load_json(project_name, "STATE.json")
    if state["phase"] != "PAUSED":
        raise HTTPException(status_code=400, detail="Can only resume from PAUSED state")
    
    state["phase"] = "EXECUTE"  # Resume from where we left off
    save_json(project_name, "STATE.json", state)
    
    await manager.broadcast({
        "type": "evolution_resumed",
        "project": project_name
    })
    
    return state


@app.post("/api/projects/{project_name}/stop")
async def stop_evolution(project_name: str):
    """Stop evolution and generate final report."""
    state = load_json(project_name, "STATE.json")
    state["phase"] = "FINAL_REPORT"
    state["ended_at"] = datetime.utcnow().isoformat()
    save_json(project_name, "STATE.json", state)
    
    await manager.broadcast({
        "type": "evolution_stopped",
        "project": project_name
    })
    
    return state


@app.get("/api/projects/{project_name}/report")
async def get_report(project_name: str):
    """Get evolution report."""
    report_path = get_project_dir(project_name) / "REPORT.md"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    
    return {"report": report_path.read_text()}


@app.get("/api/projects/{project_name}/history")
async def get_history(project_name: str, limit: int = 100, debug: bool = False):
    """Get evolution history."""
    history_path = get_project_dir(project_name) / "HISTORY.jsonl"
    if not history_path.exists():
        return {"history": [], "debug_info": None}
    
    lines = history_path.read_text().strip().split("\n")
    history = []
    
    for line in lines[-limit*2:]:  # Get more to filter later
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            
            # Normalize timestamp format
            ts = entry.get("timestamp", "")
            if ts:
                # Remove milliseconds and normalize timezone
                # "2026-03-13T14:58:55.091242+00:00Z" -> "2026-03-13T14:58:55Z"
                if "." in ts:
                    ts = ts.split(".")[0]
                if ts.endswith("+00:00"):
                    ts = ts.replace("+00:00", "")
                if not ts.endswith("Z"):
                    ts = ts + "Z"
                entry["timestamp"] = ts
            
            # Skip uninformative entries
            msg = entry.get("message", "")
            skip_messages = [
                "Evolution cycle started",
                "Agent starting - reading context and analyzing...",
                "Invoking OpenClaw agent with thinking=medium",
                "Invoking OpenClaw agent with thinking=low",
                "Invoking OpenClaw agent with thinking=high",
                "Auto-restart scheduled",
            ]
            if msg in skip_messages:
                continue
            
            # Skip "Agent working..." progress messages
            if msg.startswith("Agent working") or msg.startswith("Agent timeout"):
                continue
            
            # Skip duplicate "preparing context" messages
            if "preparing context" in msg.lower():
                continue
            
            history.append(entry)
        except:
            continue
    
    # Sort by timestamp descending (newest first)
    history.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    
    # Limit after filtering
    history = history[:limit]
    
    # Add debug info if requested
    debug_info = None
    if debug:
        import subprocess
        debug_info = {
            "current_time": datetime.utcnow().isoformat(),
            "processes": [],
            "recent_logs": []
        }
        
        # Check running processes
        try:
            result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
            for line in result.stdout.split("\n"):
                if project_name in line.lower() or "evolution" in line.lower():
                    if "grep" not in line:
                        debug_info["processes"].append(line.strip())
        except:
            pass
        
        # Get recent logs
        log_dir = Path("/tmp/evolution-logs")
        if log_dir.exists():
            log_files = sorted(log_dir.glob(f"{project_name}-*.log"), reverse=True)[:3]
            for log_file in log_files:
                try:
                    content = log_file.read_text()
                    debug_info["recent_logs"].append({
                        "file": log_file.name,
                        "last_lines": content.strip().split("\n")[-20:]
                    })
                except:
                    pass
    
    return {"history": history, "debug_info": debug_info}


# ============== WebSocket ==============

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo back or handle commands
            await websocket.send_json({"type": "pong", "data": data})
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/api/cron/status")
async def get_cron_status():
    """Get cron job status for evolution."""
    import subprocess
    from pathlib import Path
    
    status = {
        "configured": False,
        "jobs": [],
        "error": None
    }
    
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        cron_output = result.stdout
        
        if result.returncode != 0 and "no crontab" in result.stderr.lower():
            status["error"] = "No crontab configured"
            return status
        
        # Parse cron jobs
        for line in cron_output.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            # Check if it's evolution-related
            if "evolution" in line.lower() or any(
                project in line for project in ["calendar-stats", "carl-experiments"]
            ):
                # Parse cron expression (simplified)
                parts = line.split()
                if len(parts) >= 6:
                    schedule = " ".join(parts[:5])
                    command = " ".join(parts[5:])
                    
                    # Extract project name
                    project = "unknown"
                    if "calendar-stats" in command:
                        project = "calendar-stats"
                    elif "carl-experiments" in command:
                        project = "carl-experiments"
                    
                    # Human-readable schedule
                    schedule_text = parse_cron_schedule(schedule)
                    
                    status["jobs"].append({
                        "schedule": schedule,
                        "schedule_text": schedule_text,
                        "command": command,
                        "project": project,
                        "enabled": True
                    })
        
        if status["jobs"]:
            status["configured"] = True
            
    except Exception as e:
        status["error"] = str(e)
    
    return status


@app.post("/api/cron/setup")
async def setup_cron_job(project_name: str, interval_minutes: int = 30):
    """Setup cron job for evolution project."""
    import subprocess
    from pathlib import Path
    
    script_path = Path.home() / ".openclaw" / "workspace" / "scripts" / "evolution_cycle.sh"
    if not script_path.exists():
        raise HTTPException(status_code=500, detail="Evolution script not found")
    
    # Build cron expression
    cron_expr = f"*/{interval_minutes} * * * *"
    cron_line = f"{cron_expr} {script_path} {project_name} >> /tmp/evolution-logs/{project_name}-cron.log 2>&1"
    
    try:
        # Get current crontab
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        current_cron = result.stdout if result.returncode == 0 else ""
        
        # Remove existing evolution job for this project
        lines = []
        for line in current_cron.split("\n"):
            if project_name not in line or "evolution" not in line.lower():
                lines.append(line)
        
        # Add new job
        lines.append(f"# Evolution: {project_name} (every {interval_minutes}min)")
        lines.append(cron_line)
        lines.append("")  # Ensure trailing newline
        
        # Install new crontab
        new_cron = "\n".join(lines)
        process = subprocess.Popen(
            ["crontab", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(input=new_cron + "\n")
        
        if process.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Failed to install crontab: {stderr}")
        
        # Add to history
        history_path = get_project_dir(project_name) / "HISTORY.jsonl"
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "type": "info",
            "message": f"⏰ Cron job configured: every {interval_minutes} minutes"
        }
        with open(history_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
        
        return {
            "status": "configured",
            "schedule": cron_expr,
            "interval_minutes": interval_minutes,
            "message": f"Cron job added: {cron_expr}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/cron/{project_name}")
async def remove_cron_job(project_name: str):
    """Remove cron job for evolution project."""
    import subprocess
    
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        current_cron = result.stdout if result.returncode == 0 else ""
        
        # Remove job for this project
        lines = []
        skip_next = False
        for line in current_cron.split("\n"):
            if skip_next:
                skip_next = False
                continue
            
            if f"# Evolution: {project_name}" in line:
                skip_next = True
                continue
            
            if project_name not in line or "evolution" not in line.lower():
                lines.append(line)
        
        # Install new crontab
        new_cron = "\n".join(lines)
        process = subprocess.Popen(
            ["crontab", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(input=new_cron + "\n")
        
        if process.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Failed to update crontab: {stderr}")
        
        return {"status": "removed", "message": f"Cron job removed for {project_name}"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def parse_cron_schedule(schedule: str) -> str:
    """Parse cron schedule to human-readable text."""
    parts = schedule.split()
    if len(parts) != 5:
        return schedule
    
    minute, hour, day, month, weekday = parts
    
    # Common patterns
    if minute.startswith("*/"):
        interval = minute[2:]
        return f"Every {interval} minutes"
    
    if hour.startswith("*/"):
        interval = hour[2:]
        return f"Every {interval} hours"
    
    if minute == "0" and hour == "*":
        return "Every hour"
    
    if minute == "0" and hour != "*":
        return f"Daily at {hour}:00"
    
    return schedule


# ============== System Status ==============

@app.get("/api/system/status")
async def get_system_status():
    """Get overall system status for self-check."""
    import subprocess
    
    status = {
        "ui_running": True,
        "ui_uptime": None,
        "evolution_enabled": False,
        "cron_configured": False,
        "last_evolution_run": None,
        "active_processes": 0,
        "warnings": [],
        "recommendations": []
    }
    
    # Check cron jobs
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        cron_output = result.stdout + result.stderr
        
        # Check for evolution cron jobs
        if "evolution" in cron_output.lower():
            status["cron_configured"] = True
        else:
            status["warnings"].append("No cron jobs configured for evolution")
            status["recommendations"].append("Add cron job: */30 * * * * /root/.openclaw/workspace/scripts/evolution_cycle.sh PROJECT_NAME")
    except Exception as e:
        status["warnings"].append(f"Failed to check cron: {str(e)}")
    
    # Check evolution processes
    try:
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
        processes = result.stdout
        
        # Count evolution-related processes
        evolution_procs = [line for line in processes.split("\n") if "evolution" in line.lower() and "grep" not in line]
        status["active_processes"] = len(evolution_procs)
        
        if status["active_processes"] == 0:
            status["warnings"].append("No active evolution processes detected")
    except Exception as e:
        status["warnings"].append(f"Failed to check processes: {str(e)}")
    
    # Check projects status
    projects_status = []
    for project_name in list_projects():
        try:
            state = load_json(project_name, "STATE.json")
            phase = state.get("phase", "IDLE")
            
            # Check if evolution should be running
            if phase in ["ANALYZE", "PLAN", "EXECUTE", "REVIEW"]:
                status["evolution_enabled"] = True
                
                # Check last activity
                history_path = get_project_dir(project_name) / "HISTORY.jsonl"
                if history_path.exists():
                    lines = history_path.read_text().strip().split("\n")
                    if lines:
                        last_entry = json.loads(lines[-1])
                        last_time = datetime.fromisoformat(last_entry.get("timestamp", "").replace("Z", "+00:00"))
                        minutes_ago = (datetime.now(last_time.tzinfo) - last_time).total_seconds() / 60
                        
                        status["last_evolution_run"] = {
                            "project": project_name,
                            "minutes_ago": int(minutes_ago),
                            "phase": phase
                        }
                        
                        if minutes_ago > 60:
                            status["warnings"].append(f"Project {project_name} in {phase} but no activity for {int(minutes_ago)} minutes")
            
            projects_status.append({
                "name": project_name,
                "phase": phase,
                "cycle": state.get("cycle", 0)
            })
        except Exception as e:
            pass
    
    status["projects"] = projects_status
    
    # Add recommendations
    if not status["cron_configured"] and status["evolution_enabled"]:
        status["recommendations"].append("Evolution is enabled but no cron jobs found. Set up periodic execution.")
    
    if status["active_processes"] == 0 and status["evolution_enabled"]:
        status["recommendations"].append("Evolution should be running but no active processes found. Check logs.")
    
    return status


@app.post("/api/projects/{project_name}/rollback")
async def rollback_project(project_name: str):
    """Rollback all changes, cleanup logs, reset to initial state."""
    import subprocess
    from pathlib import Path
    
    project_dir = get_project_dir(project_name)
    
    # 1. Reset STATE.json to IDLE
    state = load_json(project_name, "STATE.json")
    state["phase"] = "IDLE"
    state["cycle"] = 0
    state["stuck_counter"] = 0
    state["budget"]["cost_usd"] = 0.0
    state.pop("analysis", None)
    state["started_at"] = datetime.utcnow().isoformat()
    save_json(project_name, "STATE.json", state)
    
    # 2. Move all tasks to backlog
    tasks = load_json(project_name, "TASKS.json")
    all_tasks = []
    
    # Collect all tasks
    for status in ["in_progress", "done", "blocked", "backlog"]:
        for task in tasks.get(status, []):
            # Reset task state
            task["status"] = "backlog"
            task.pop("started_at", None)
            task.pop("completed_at", None)
            task.pop("blocked_reason", None)
            task.pop("commits", None)
            task.pop("files_changed", None)
            all_tasks.append(task)
    
    # Save tasks with all in backlog
    tasks = {
        "backlog": all_tasks,
        "in_progress": [],
        "done": [],
        "blocked": []
    }
    save_json(project_name, "TASKS.json", tasks)
    
    # 3. Clear history
    history_path = project_dir / "HISTORY.jsonl"
    if history_path.exists():
        history_path.unlink()
    
    # Add rollback entry
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "type": "warning",
        "message": "🔄 Rollback completed - all changes reverted"
    }
    with open(history_path, "a") as f:
        f.write(json.dumps(entry) + "\n")
    
    # 4. Clear logs
    log_dir = Path("/tmp/evolution-logs")
    if log_dir.exists():
        for log_file in log_dir.glob(f"{project_name}-*.log"):
            log_file.unlink()
        for log_file in log_dir.glob(f"{project_name}-*.md"):
            log_file.unlink()
    
    # 5. Git reset (optional, if repo exists)
    repo_dir = REPOS_DIR / project_name
    if repo_dir.exists() and (repo_dir / ".git").exists():
        try:
            # Reset to main
            subprocess.run(
                ["git", "fetch", "origin"],
                cwd=repo_dir,
                capture_output=True,
                timeout=30
            )
            subprocess.run(
                ["git", "reset", "--hard", "origin/main"],
                cwd=repo_dir,
                capture_output=True,
                timeout=30
            )
            subprocess.run(
                ["git", "clean", "-fd"],
                cwd=repo_dir,
                capture_output=True,
                timeout=30
            )
        except Exception as e:
            print(f"Git reset failed: {e}")
    
    return {
        "status": "rolled_back",
        "tasks_moved": len(all_tasks),
        "message": f"Rollback complete. {len(all_tasks)} tasks moved to backlog."
    }


@app.get("/api/projects/{project_name}/config")
async def get_project_config(project_name: str):
    """Get project configuration including thinking levels."""
    state = load_json(project_name, "STATE.json")
    
    config = state.get("config", {})
    
    # Default thinking levels
    default_thinking = {
        "ANALYZE": "high",
        "PLAN": "medium",
        "EXECUTE": "medium",
        "REVIEW": "low"
    }
    
    # Merge with custom config
    thinking_levels = config.get("thinking_levels", default_thinking)
    
    return {
        "thinking_levels": thinking_levels,
        "custom_config": config
    }


# ============== PRD Routes (Ralph Format) ==============

@app.get("/api/projects/{project_name}/prd")
async def get_prd(project_name: str) -> dict:
    """Get PRD for a project."""
    try:
        return load_json(project_name, "prd.json")
    except HTTPException:
        # Return empty PRD if not exists
        return {
            "project": project_name,
            "branchName": "",
            "description": "",
            "userStories": []
        }


@app.post("/api/projects/{project_name}/prd")
async def create_prd(project_name: str, prd: PRD):
    """Create or update PRD for a project."""
    prd_dict = prd.model_dump()
    save_json(project_name, "prd.json", prd_dict)
    
    await manager.broadcast({
        "type": "prd_updated",
        "project": project_name,
        "prd": prd_dict
    })
    
    return prd_dict


@app.post("/api/projects/{project_name}/prd/stories")
async def add_user_story(project_name: str, story: UserStory):
    """Add a user story to PRD."""
    try:
        prd = load_json(project_name, "prd.json")
    except HTTPException:
        prd = {
            "project": project_name,
            "branchName": f"feature/{project_name}",
            "description": "",
            "userStories": []
        }
    
    # Auto-generate ID if not provided
    if not story.id or story.id == "US-001":
        existing_ids = [s["id"] for s in prd["userStories"]]
        next_num = len(prd["userStories"]) + 1
        story.id = f"US-{next_num:03d}"
        while story.id in existing_ids:
            next_num += 1
            story.id = f"US-{next_num:03d}"
    
    prd["userStories"].append(story.model_dump())
    save_json(project_name, "prd.json", prd)
    
    await manager.broadcast({
        "type": "story_added",
        "project": project_name,
        "story": story.model_dump()
    })
    
    return story.model_dump()


@app.put("/api/projects/{project_name}/prd/stories/{story_id}")
async def update_user_story(project_name: str, story_id: str, story: UserStory):
    """Update a user story."""
    prd = load_json(project_name, "prd.json")
    
    for i, s in enumerate(prd["userStories"]):
        if s["id"] == story_id:
            prd["userStories"][i] = story.model_dump()
            save_json(project_name, "prd.json", prd)
            
            await manager.broadcast({
                "type": "story_updated",
                "project": project_name,
                "story": story.model_dump()
            })
            
            return story.model_dump()
    
    raise HTTPException(status_code=404, detail="Story not found")


@app.put("/api/projects/{project_name}/prd/stories/{story_id}/passes")
async def mark_story_passes(project_name: str, story_id: str, passes: bool = True):
    """Mark a user story as passing or not."""
    prd = load_json(project_name, "prd.json")
    
    for i, s in enumerate(prd["userStories"]):
        if s["id"] == story_id:
            prd["userStories"][i]["passes"] = passes
            save_json(project_name, "prd.json", prd)
            
            await manager.broadcast({
                "type": "story_updated",
                "project": project_name,
                "story": prd["userStories"][i]
            })
            
            return prd["userStories"][i]
    
    raise HTTPException(status_code=404, detail="Story not found")


@app.delete("/api/projects/{project_name}/prd/stories/{story_id}")
async def delete_user_story(project_name: str, story_id: str):
    """Delete a user story."""
    prd = load_json(project_name, "prd.json")
    
    for i, s in enumerate(prd["userStories"]):
        if s["id"] == story_id:
            deleted = prd["userStories"].pop(i)
            save_json(project_name, "prd.json", prd)
            
            await manager.broadcast({
                "type": "story_deleted",
                "project": project_name,
                "story_id": story_id
            })
            
            return {"status": "deleted", "story": deleted}
    
    raise HTTPException(status_code=404, detail="Story not found")


@app.get("/api/projects/{project_name}/prd/next")
async def get_next_story(project_name: str):
    """Get the next incomplete story (highest priority, passes=false)."""
    try:
        prd = load_json(project_name, "prd.json")
    except HTTPException:
        return {"story": None, "remaining": 0, "total": 0}
    
    incomplete = [s for s in prd["userStories"] if not s.get("passes", False)]
    
    if not incomplete:
        return {"story": None, "remaining": 0, "total": len(prd["userStories"])}
    
    # Sort by priority (lowest number = highest priority)
    incomplete.sort(key=lambda s: s.get("priority", 999))
    next_story = incomplete[0]
    
    return {
        "story": next_story,
        "remaining": len(incomplete),
        "total": len(prd["userStories"])
    }


@app.post("/api/projects/{project_name}/prd/convert")
async def convert_prd_to_tasks(project_name: str):
    """Convert PRD user stories to evolution tasks."""
    prd = load_json(project_name, "prd.json")
    tasks = load_json(project_name, "TASKS.json")
    
    converted = 0
    for story in prd["userStories"]:
        # Check if task already exists
        existing_ids = [t["id"] for t in tasks["backlog"] + tasks["in_progress"] + tasks["done"] + tasks["blocked"]]
        if story["id"] in existing_ids:
            continue
        
        # Convert to task
        task = {
            "id": story["id"],
            "title": story["title"],
            "description": story.get("description", ""),
            "category": "feature",
            "priority_score": 10 - story.get("priority", 5),
            "impact": 5,
            "effort": 5,
            "risk": 3,
            "status": "done" if story.get("passes", False) else "backlog",
            "dependencies": [],
            "acceptance_criteria": story.get("acceptanceCriteria", []),
            "created_at": datetime.utcnow().isoformat(),
            "started_at": None,
            "completed_at": datetime.utcnow().isoformat() if story.get("passes", False) else None,
            "blocked_reason": None,
            "commits": [],
            "files_changed": []
        }
        
        if story.get("passes", False):
            tasks["done"].append(task)
        else:
            tasks["backlog"].append(task)
        
        converted += 1
    
    save_json(project_name, "TASKS.json", tasks)
    
    await manager.broadcast({
        "type": "tasks_updated",
        "project": project_name,
        "converted": converted
    })
    
    return {
        "status": "converted",
        "stories_converted": converted,
        "total_stories": len(prd["userStories"])
    }


@app.put("/api/projects/{project_name}/config/thinking")
async def update_thinking_config(
    project_name: str,
    phase: str,
    level: str
):
    """Update thinking level for a specific phase."""
    if phase not in ["ANALYZE", "PLAN", "EXECUTE", "REVIEW"]:
        raise HTTPException(status_code=400, detail="Invalid phase")
    
    if level not in ["low", "medium", "high"]:
        raise HTTPException(status_code=400, detail="Invalid thinking level")
    
    state = load_json(project_name, "STATE.json")
    
    # Initialize config if not exists
    if "config" not in state:
        state["config"] = {}
    
    if "thinking_levels" not in state["config"]:
        state["config"]["thinking_levels"] = {
            "ANALYZE": "high",
            "PLAN": "medium",
            "EXECUTE": "medium",
            "REVIEW": "low"
        }
    
    # Update thinking level
    state["config"]["thinking_levels"][phase] = level
    
    save_json(project_name, "STATE.json", state)
    
    # Add to history
    history_path = get_project_dir(project_name) / "HISTORY.jsonl"
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "type": "info",
        "message": f"Thinking level updated: {phase} → {level}"
    }
    with open(history_path, "a") as f:
        f.write(json.dumps(entry) + "\n")
    
    return {
        "status": "updated",
        "phase": phase,
        "level": level,
        "message": f"Thinking level for {phase} updated to {level}"
    }


@app.post("/api/projects/{project_name}/force-cycle")
async def force_evolution_cycle(project_name: str):
    """Force run next evolution cycle immediately."""
    import subprocess
    
    state = load_json(project_name, "STATE.json")
    phase = state.get("phase", "IDLE")
    
    if phase in ["IDLE", "PAUSED", "FINAL_REPORT", "ASK_USER"]:
        raise HTTPException(status_code=400, detail=f"Cannot force cycle in {phase} phase")
    
    # Run evolution cycle script in background
    script_path = WORKSPACE / "scripts" / "evolution_cycle.sh"
    if not script_path.exists():
        raise HTTPException(status_code=500, detail="Evolution script not found")
    
    # Start in background
    log_file = f"/tmp/evolution-logs/{project_name}-forced-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.log"
    subprocess.Popen(
        ["bash", str(script_path), project_name],
        stdout=open(log_file, 'w'),
        stderr=subprocess.STDOUT,
        start_new_session=True
    )
    
    # Add to history
    history_path = get_project_dir(project_name) / "HISTORY.jsonl"
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "phase": phase,
        "cycle": state.get("cycle", 0),
        "type": "info",
        "message": f"⚠️ FORCED cycle started (phase: {phase})",
        "forced": True
    }
    with open(history_path, "a") as f:
        f.write(json.dumps(entry) + "\n")
    
    return {
        "status": "started",
        "phase": phase,
        "log_file": log_file,
        "message": f"Forced {phase} cycle started. Check logs in ~30 seconds."
    }


# ============== Ralph Loop Evolution ==============

import subprocess
import signal

# Track running evolution processes
EVOLUTION_PROCESSES: Dict[str, subprocess.Popen] = {}


@app.post("/api/projects/{project_name}/evolution/start")
async def start_evolution(
    project_name: str, 
    budget: float = 50.0, 
    max_cycles: int = 100,
    mode: str = "autonomous",  # "autonomous" or "prd"
    create_branch: bool = True
):
    """Start Ralph Loop evolution for a project.
    
    Args:
        project_name: Project to evolve
        budget: Budget limit in USD
        max_cycles: Maximum number of evolution cycles
        mode: "autonomous" (agent plans tasks) or "prd" (use PRD user stories)
        create_branch: Create evolution branch at start
    """
    global EVOLUTION_PROCESSES
    
    project_dir = get_project_dir(project_name)
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check if already running
    if project_name in EVOLUTION_PROCESSES:
        proc = EVOLUTION_PROCESSES[project_name]
        if proc.poll() is None:  # Still running
            return {
                "status": "already_running",
                "pid": proc.pid,
                "message": "Evolution already running for this project"
            }
    
    # Create evolution branch if requested
    repo_dir = REPOS_DIR / project_name
    if create_branch and repo_dir.exists():
        try:
            # Check if evolution branch exists
            result = subprocess.run(
                ["git", "branch", "--list", "evolution"],
                cwd=repo_dir, capture_output=True, text=True
            )
            
            if result.stdout.strip():
                # Checkout existing evolution branch
                subprocess.run(
                    ["git", "checkout", "evolution"],
                    cwd=repo_dir, capture_output=True, text=True
                )
            else:
                # Create new evolution branch
                subprocess.run(
                    ["git", "checkout", "-B", "evolution"],
                    cwd=repo_dir, capture_output=True, text=True
                )
                # Push to remote
                subprocess.run(
                    ["git", "push", "-u", "origin", "evolution"],
                    cwd=repo_dir, capture_output=True, text=True
                )
        except Exception as e:
            print(f"Warning: Failed to create evolution branch: {e}")
    
    # Update state with mode
    state = load_json(project_name, "STATE.json")
    state["phase"] = "RUNNING"
    state["started_at"] = datetime.utcnow().isoformat() + "Z"
    state["mode"] = mode
    state["budget"]["limit_usd"] = budget
    save_json(project_name, "STATE.json", state)
    
    # Start evolution runner
    script_path = Path(__file__).parent / "scripts" / "run-evolution.sh"
    if not script_path.exists():
        raise HTTPException(status_code=500, detail="Evolution runner script not found")
    
    log_file = project_dir / "evolution.log"
    
    with open(log_file, "w") as log:
        proc = subprocess.Popen(
            ["bash", str(script_path), project_name, "--budget", str(budget), "--max-cycles", str(max_cycles)],
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env={**os.environ, "BUDGET": str(budget), "MAX_CYCLES": str(max_cycles), "MODE": mode}
        )
    
    EVOLUTION_PROCESSES[project_name] = proc
    
    # Broadcast
    await manager.broadcast({
        "type": "evolution_started",
        "project": project_name,
        "pid": proc.pid,
        "budget": budget,
        "max_cycles": max_cycles,
        "mode": mode
    })
    
    return {
        "status": "started",
        "pid": proc.pid,
        "budget": budget,
        "max_cycles": max_cycles,
        "mode": mode,
        "log_file": str(log_file),
        "message": "Evolution started. Monitor via /api/projects/{project}/evolution/status"
    }


@app.post("/api/projects/{project_name}/evolution/stop")
async def stop_evolution(project_name: str):
    """Stop running evolution."""
    global EVOLUTION_PROCESSES
    
    if project_name not in EVOLUTION_PROCESSES:
        return {"status": "not_running", "message": "No evolution running for this project"}
    
    proc = EVOLUTION_PROCESSES[project_name]
    
    if proc.poll() is not None:
        # Already stopped
        del EVOLUTION_PROCESSES[project_name]
        return {"status": "already_stopped", "message": "Evolution already stopped"}
    
    # Send SIGTERM
    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        # Force kill
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        proc.wait()
    
    del EVOLUTION_PROCESSES[project_name]
    
    # Update state
    state = load_json(project_name, "STATE.json")
    state["phase"] = "PAUSED"
    save_json(project_name, "STATE.json", state)
    
    await manager.broadcast({
        "type": "evolution_stopped",
        "project": project_name
    })
    
    return {"status": "stopped", "message": "Evolution stopped"}


@app.get("/api/projects/{project_name}/evolution/status")
async def get_evolution_status(project_name: str):
    """Get evolution status."""
    global EVOLUTION_PROCESSES
    
    project_dir = get_project_dir(project_name)
    
    # Check process
    running = False
    pid = None
    if project_name in EVOLUTION_PROCESSES:
        proc = EVOLUTION_PROCESSES[project_name]
        if proc.poll() is None:
            running = True
            pid = proc.pid
    
    # Load state
    try:
        state = load_json(project_name, "STATE.json")
    except HTTPException:
        state = {"phase": "IDLE", "cycle": 0}
    
    # Get task counts
    try:
        prd = load_json(project_name, "prd.json")
        total_stories = len(prd.get("userStories", []))
        completed_stories = len([s for s in prd.get("userStories", []) if s.get("passes", False)])
    except HTTPException:
        total_stories = 0
        completed_stories = 0
    
    try:
        tasks = load_json(project_name, "TASKS.json")
        backlog = len(tasks.get("backlog", []))
        done = len(tasks.get("done", []))
    except HTTPException:
        backlog = 0
        done = 0
    
    # Get log tail
    log_file = project_dir / "evolution.log"
    log_tail = ""
    if log_file.exists():
        try:
            log_tail = subprocess.run(
                ["tail", "-20", str(log_file)],
                capture_output=True,
                text=True,
                timeout=5
            ).stdout
        except:
            pass
    
    return {
        "running": running,
        "pid": pid,
        "phase": state.get("phase", "IDLE"),
        "cycle": state.get("cycle", 0),
        "budget": state.get("budget", {}),
        "progress": {
            "prd": {
                "total": total_stories,
                "completed": completed_stories,
                "remaining": total_stories - completed_stories
            },
            "tasks": {
                "backlog": backlog,
                "done": done
            }
        },
        "log_tail": log_tail
    }


@app.get("/api/projects/{project_name}/evolution/logs")
async def get_evolution_logs(project_name: str, lines: int = 100):
    """Get evolution logs."""
    log_file = get_project_dir(project_name) / "evolution.log"
    
    if not log_file.exists():
        return {"logs": "", "message": "No logs yet"}
    
    try:
        result = subprocess.run(
            ["tail", f"-{lines}", str(log_file)],
            capture_output=True,
            text=True,
            timeout=10
        )
        return {"logs": result.stdout, "lines": lines}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read logs: {e}")


# ============== Pull Request Management ==============

@app.get("/api/projects/{project_name}/evolution/branch-status")
async def get_evolution_branch_status(project_name: str):
    """Get status of the evolution branch."""
    repo_dir = REPOS_DIR / project_name
    
    if not repo_dir.exists():
        raise HTTPException(status_code=404, detail="Repository not found")
    
    try:
        # Get current branch
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=repo_dir, capture_output=True, text=True
        )
        current_branch = result.stdout.strip()
        
        # Check if evolution branch exists
        result = subprocess.run(
            ["git", "branch", "--list", "evolution"],
            cwd=repo_dir, capture_output=True, text=True
        )
        evolution_branch_exists = bool(result.stdout.strip())
        
        # Get commits ahead of main
        if evolution_branch_exists:
            result = subprocess.run(
                ["git", "log", "main..evolution", "--oneline"],
                cwd=repo_dir, capture_output=True, text=True
            )
            commits_ahead = result.stdout.strip().split('\n') if result.stdout.strip() else []
            commits_ahead = [c for c in commits_ahead if c]
        else:
            commits_ahead = []
        
        # Get files changed
        if evolution_branch_exists and commits_ahead:
            result = subprocess.run(
                ["git", "diff", "main...evolution", "--stat"],
                cwd=repo_dir, capture_output=True, text=True
            )
            diff_stat = result.stdout.strip()
        else:
            diff_stat = ""
        
        # Get last commit info
        if evolution_branch_exists:
            result = subprocess.run(
                ["git", "log", "evolution", "-1", "--format=%H|%s|%an|%ad"],
                cwd=repo_dir, capture_output=True, text=True
            )
            last_commit = result.stdout.strip().split('|') if result.stdout.strip() else None
        else:
            last_commit = None
        
        return {
            "current_branch": current_branch,
            "evolution_branch_exists": evolution_branch_exists,
            "commits_ahead": len(commits_ahead),
            "commit_list": commits_ahead,
            "diff_stat": diff_stat,
            "last_commit": {
                "hash": last_commit[0][:7] if last_commit else None,
                "message": last_commit[1] if last_commit else None,
                "author": last_commit[2] if last_commit else None,
                "date": last_commit[3] if last_commit else None
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Git error: {str(e)}")


@app.post("/api/projects/{project_name}/evolution/create-pr")
async def create_evolution_pr(project_name: str, target_branch: str = "main", pr_title: str = None):
    """Create a PR from evolution branch to target branch."""
    repo_dir = REPOS_DIR / project_name
    
    if not repo_dir.exists():
        raise HTTPException(status_code=404, detail="Repository not found")
    
    try:
        # Check if evolution branch exists
        result = subprocess.run(
            ["git", "branch", "--list", "evolution"],
            cwd=repo_dir, capture_output=True, text=True
        )
        if not result.stdout.strip():
            raise HTTPException(status_code=400, detail="Evolution branch does not exist")
        
        # Get commits for PR description
        result = subprocess.run(
            ["git", "log", f"{target_branch}..evolution", "--oneline"],
            cwd=repo_dir, capture_output=True, text=True
        )
        commits = result.stdout.strip().split('\n') if result.stdout.strip() else []
        commits = [c for c in commits if c]
        
        if not commits:
            raise HTTPException(status_code=400, detail="No commits to create PR for")
        
        # Load task info from STATE.json
        state = load_json(project_name, "STATE.json")
        
        # Build PR description
        pr_body = f"""## Evolution Changes

**Cycle:** {state.get('cycle', 'unknown')}
**Tasks Completed:** {len(commits)} commits

### Commits
"""
        for commit in commits:
            pr_body += f"- {commit}\n"
        
        pr_body += f"""

### Metrics
- **Test Coverage:** {state.get('review_details', {}).get('coverage_pct', 'N/A')}%
- **Tests Passing:** {state.get('review_details', {}).get('tests_passing', 'N/A')}
- **Lint Errors:** {state.get('review_details', {}).get('lint_errors', 'N/A')}

### Tasks Completed in This Evolution
"""
        # Add task info
        tasks = load_json(project_name, "TASKS.json")
        for task in tasks.get("done", [])[-10:]:  # Last 10 tasks
            pr_body += f"- **{task.get('id', 'unknown')}:** {task.get('title', 'N/A')}\n"
        
        pr_body += """

---
*This PR was generated by Ümlaut Evolution Engine* 🚀
"""
        
        # Generate PR title if not provided
        if not pr_title:
            pr_title = f"🚀 Evolution Cycle {state.get('cycle', 'unknown')} - {len(commits)} tasks completed"
        
        # Create PR using gh CLI
        result = subprocess.run(
            ["gh", "pr", "create", 
             "--base", target_branch,
             "--head", "evolution",
             "--title", pr_title,
             "--body", pr_body],
            cwd=repo_dir, capture_output=True, text=True
        )
        
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Failed to create PR: {result.stderr}")
        
        pr_url = result.stdout.strip()
        
        # Update STATE with PR info
        state["last_pr_url"] = pr_url
        state["last_pr_created"] = datetime.utcnow().isoformat() + "Z"
        save_json(project_name, "STATE.json", state)
        
        await manager.broadcast({
            "type": "pr_created",
            "project": project_name,
            "pr_url": pr_url
        })
        
        return {
            "status": "created",
            "pr_url": pr_url,
            "title": pr_title,
            "commits": len(commits)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create PR: {str(e)}")


@app.get("/api/projects/{project_name}/evolution/prs")
async def list_evolution_prs(project_name: str, limit: int = 10):
    """List PRs created from evolution branch."""
    repo_dir = REPOS_DIR / project_name
    
    if not repo_dir.exists():
        raise HTTPException(status_code=404, detail="Repository not found")
    
    try:
        result = subprocess.run(
            ["gh", "pr", "list", "--head", "evolution", "--limit", str(limit), "--json", 
             "number,title,url,state,createdAt,mergedAt,commits"],
            cwd=repo_dir, capture_output=True, text=True
        )
        
        if result.returncode != 0:
            return {"prs": []}
        
        prs = json.loads(result.stdout)
        return {"prs": prs}
    except Exception as e:
        return {"prs": [], "error": str(e)}


# ============== Static Files ==============

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main UI."""
    return (Path(__file__).parent / "static" / "index.html").read_text()


# Mount static files
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


def run_server():
    """Entry point for running the server."""
    import uvicorn
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    run_server()
