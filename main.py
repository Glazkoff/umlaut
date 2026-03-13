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
    history = [json.loads(line) for line in lines[-limit:]]
    
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
            # Reset to main/master
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
