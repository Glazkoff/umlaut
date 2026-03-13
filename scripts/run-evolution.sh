#!/bin/bash
# Umlaut Evolution Runner - Ralph Loop Style
# Runs continuously until all tasks are done or budget exhausted
#
# Usage:
#   ./run-evolution.sh <project_name> [--budget 50] [--max-cycles 100]
#
# Based on Ralph Wiggum technique: https://ghuntley.com/ralph/

set -e

PROJECT="${1:-}"
BUDGET="${BUDGET:-50}"
MAX_CYCLES="${MAX_CYCLES:-100}"
CYCLE=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

EVOLUTION_DIR="$HOME/.openclaw/workspace/evolution"
PROJECT_DIR="$EVOLUTION_DIR/$PROJECT"

log() { echo -e "${PURPLE}[Ümlaut]${NC} $1"; }
log_cycle() { echo -e "${CYAN}[Cycle $CYCLE]${NC} $1"; }
log_analyze() { echo -e "${BLUE}[ANALYZE]${NC} $1"; }
log_plan() { echo -e "${YELLOW}[PLAN]${NC} $1"; }
log_execute() { echo -e "${GREEN}[EXECUTE]${NC} $1"; }
log_review() { echo -e "${RED}[REVIEW]${NC} $1"; }

# Check prerequisites
check_prereqs() {
    if [ -z "$PROJECT" ]; then
        echo "Usage: $0 <project_name> [--budget 50] [--max-cycles 100]"
        exit 1
    fi
    
    if [ ! -d "$PROJECT_DIR" ]; then
        log "Project not found: $PROJECT_DIR"
        log "Create it first via Umlaut UI or API"
        exit 1
    fi
    
    # Use full path to openclaw (not in PATH when running from cron)
    OPENCLAW_CMD="/root/.nvm/versions/node/v24.14.0/bin/openclaw"
    
    if [ ! -f "$OPENCLAW_CMD" ]; then
        log "OpenClaw CLI not found at $OPENCLAW_CMD"
        log "Install: npm install -g openclaw"
        exit 1
    fi
}

# Load state
load_state() {
    STATE_FILE="$PROJECT_DIR/STATE.json"
    if [ -f "$STATE_FILE" ]; then
        PHASE=$(cat "$STATE_FILE" | jq -r '.phase // "IDLE"')
        CYCLE=$(cat "$STATE_FILE" | jq -r '.cycle // 0')
        COST=$(cat "$STATE_FILE" | jq -r '.budget.cost_usd // 0')
    else
        PHASE="IDLE"
        CYCLE=0
        COST=0
    fi
}

# Save state
save_state() {
    local phase="$1"
    local cost="$2"
    local task="$3"
    
    cat > "$PROJECT_DIR/STATE.json" << EOF
{
  "project": "$PROJECT",
  "phase": "$phase",
  "cycle": $CYCLE,
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "budget": {
    "limit_usd": $BUDGET,
    "cost_usd": $cost
  },
  "current_task": $task,
  "stuck_counter": 0,
  "config": {}
}
EOF
}

# Get next task from PRD or TASKS
get_next_task() {
    # First check PRD
    if [ -f "$PROJECT_DIR/prd.json" ]; then
        TASK=$(cat "$PROJECT_DIR/prd.json" | jq -r '
            .userStories | 
            map(select(.passes == false)) | 
            sort_by(.priority) | 
            .[0] // empty
        ')
        if [ -n "$TASK" ] && [ "$TASK" != "null" ]; then
            echo "$TASK"
            return
        fi
    fi
    
    # Fall back to TASKS.json
    if [ -f "$PROJECT_DIR/TASKS.json" ]; then
        TASK=$(cat "$PROJECT_DIR/TASKS.json" | jq -r '
            .backlog | 
            sort_by(-.priority_score) | 
            .[0] // empty
        ')
        if [ -n "$TASK" ] && [ "$TASK" != "null" ]; then
            echo "$TASK"
            return
        fi
    fi
    
    echo ""
}

# Check if all tasks done
all_tasks_done() {
    local remaining=0
    
    # Check PRD
    if [ -f "$PROJECT_DIR/prd.json" ]; then
        remaining=$(cat "$PROJECT_DIR/prd.json" | jq '[.userStories[] | select(.passes == false)] | length')
    fi
    
    # Check TASKS
    if [ -f "$PROJECT_DIR/TASKS.json" ]; then
        local backlog=$(cat "$PROJECT_DIR/TASKS.json" | jq '.backlog | length')
        remaining=$((remaining + backlog))
    fi
    
    [ "$remaining" -eq 0 ]
}

# Append to history
append_history() {
    local type="$1"
    local message="$2"
    local timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    
    echo "{\"timestamp\": \"$timestamp\", \"type\": \"$type\", \"message\": \"$message\", \"cycle\": $CYCLE}" >> "$PROJECT_DIR/HISTORY.jsonl"
}

# Append to progress (learnings)
append_progress() {
    local learning="$1"
    local timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    
    echo -e "\n## Cycle $CYCLE - $timestamp\n$learning" >> "$PROJECT_DIR/progress.txt"
}

# Run ANALYZE phase
run_analyze() {
    log_analyze "Starting analysis..."
    save_state "ANALYZE" "$COST" "{}"
    append_history "phase" "Starting ANALYZE phase"
    
    # Call OpenClaw with analyze prompt
    PROMPT="You are in ANALYZE phase for project: $PROJECT

Project directory: $PROJECT_DIR

Your task:
1. Read the existing STATE.json, TASKS.json, and prd.json (if exists)
2. Analyze the codebase at $(cat "$PROJECT_DIR/STATE.json" 2>/dev/null | jq -r '.config.repo_url // "unknown"' 2>/dev/null || echo "unknown repo")
3. Identify any new tasks or improvements needed
4. Update TASKS.json with any new findings
5. Write a brief summary to progress.txt

Focus on:
- Code quality issues
- Missing tests
- Documentation gaps
- Security concerns
- Performance bottlenecks

Output a JSON summary of your findings."
    
    $OPENCLAW_CMD agent --message "$PROMPT" --thinking high 2>&1 | tee -a "$PROJECT_DIR/agent.log" || true
    
    log_analyze "Analysis complete"
    append_history "phase" "ANALYZE phase complete"
}

# Run PLAN phase
run_plan() {
    log_plan "Planning next task..."
    save_state "PLAN" "$COST" "{}"
    append_history "phase" "Starting PLAN phase"
    
    TASK=$(get_next_task)
    
    if [ -z "$TASK" ]; then
        log_plan "No tasks to plan"
        echo "COMPLETE"
        return
    fi
    
    TASK_ID=$(echo "$TASK" | jq -r '.id')
    TASK_TITLE=$(echo "$TASK" | jq -r '.title')
    
    log_plan "Selected task: $TASK_ID - $TASK_TITLE"
    
    # Call OpenClaw with plan prompt
    PROMPT="You are in PLAN phase for project: $PROJECT

Task to implement:
$(echo "$TASK" | jq '.')

Your task:
1. Read the task details and acceptance criteria
2. Plan the implementation step by step
3. Identify any dependencies or risks
4. Write the plan to progress.txt

Be specific about:
- Files to modify
- Functions to add/change
- Tests to write
- How to verify the implementation works

Output a JSON plan with steps."
    
    $OPENCLAW_CMD agent --message "$PROMPT" --thinking medium 2>&1 | tee -a "$PROJECT_DIR/agent.log" || true
    
    # Save current task to state
    save_state "EXECUTE" "$COST" "$TASK"
    
    log_plan "Plan complete for: $TASK_TITLE"
    append_history "phase" "PLAN phase complete for $TASK_ID"
    
    echo "$TASK"
}

# Run EXECUTE phase
run_execute() {
    local task="$1"
    
    TASK_ID=$(echo "$task" | jq -r '.id')
    TASK_TITLE=$(echo "$task" | jq -r '.title')
    
    log_execute "Executing: $TASK_TITLE"
    append_history "phase" "Starting EXECUTE phase for $TASK_ID"
    
    # Call OpenClaw with execute prompt
    PROMPT="You are in EXECUTE phase for project: $PROJECT

Task to implement:
$(echo "$task" | jq '.')

CRITICAL RULES:
1. Implement ONLY this task - do not work on other tasks
2. Do NOT implement placeholder code - write FULL implementations
3. Do NOT assume code doesn't exist - SEARCH first with ripgrep
4. Write tests for your changes
5. Run the tests to verify your changes work
6. Commit your changes with a descriptive message

Your task:
1. Search the codebase to understand the current state
2. Implement the required changes
3. Write/update tests
4. Run tests and fix any failures
5. Commit changes

After implementing, output:
- Files changed
- Tests written/updated
- Test results
- Commit hash"
    
    $OPENCLAW_CMD agent --message "$PROMPT" --thinking medium 2>&1 | tee -a "$PROJECT_DIR/agent.log" || true
    
    log_execute "Execution complete"
    append_history "phase" "EXECUTE phase complete for $TASK_ID"
}

# Run REVIEW phase  
run_review() {
    local task="$1"
    
    TASK_ID=$(echo "$task" | jq -r '.id')
    TASK_TITLE=$(echo "$task" | jq -r '.title')
    
    log_review "Reviewing: $TASK_TITLE"
    append_history "phase" "Starting REVIEW phase for $TASK_ID"
    
    # Call OpenClaw with review prompt
    PROMPT="You are in REVIEW phase for project: $PROJECT

Task that was implemented:
$(echo "$task" | jq '.')

Your task:
1. Review the changes made in the EXECUTE phase
2. Run all tests to verify nothing is broken
3. Check code quality (linting, type checking)
4. Verify acceptance criteria are met
5. Update prd.json or TASKS.json to mark task as passes: true if successful
6. Write learnings to progress.txt

If tests fail or criteria not met:
- Mark task as blocked with reason
- Do NOT mark as passes: true

Output:
- Test results
- Quality check results
- Whether task passes (true/false)
- Any learnings or gotchas discovered"
    
    $OPENCLAW_CMD agent --message "$PROMPT" --thinking high 2>&1 | tee -a "$PROJECT_DIR/agent.log" || true
    
    log_review "Review complete"
    append_history "phase" "REVIEW phase complete for $TASK_ID"
}

# Main loop
main() {
    check_prereqs
    
    log "Starting evolution for: $PROJECT"
    log "Budget: \$$BUDGET | Max cycles: $MAX_CYCLES"
    log "Project dir: $PROJECT_DIR"
    echo ""
    
    # Initialize progress.txt if not exists
    touch "$PROJECT_DIR/progress.txt"
    
    while true; do
        CYCLE=$((CYCLE + 1))
        
        # Check budget
        if (( $(echo "$COST >= $BUDGET" | bc -l) )); then
            log "Budget exhausted: \$$COST / \$$BUDGET"
            append_history "stop" "Budget exhausted"
            break
        fi
        
        # Check max cycles
        if [ "$CYCLE" -gt "$MAX_CYCLES" ]; then
            log "Max cycles reached: $CYCLE"
            append_history "stop" "Max cycles reached"
            break
        fi
        
        # Check if all done
        if all_tasks_done; then
            log "All tasks complete!"
            append_history "complete" "All tasks passed"
            echo ""
            log "=========================================="
            log "  EVOLUTION COMPLETE!"
            log "=========================================="
            log "Cycles: $CYCLE"
            log "Cost: \$$COST / \$$BUDGET"
            break
        fi
        
        log_cycle "Starting iteration..."
        
        # ANALYZE phase (every 10 cycles)
        if [ $((CYCLE % 10)) -eq 1 ]; then
            run_analyze
        fi
        
        # PLAN phase
        TASK=$(run_plan)
        
        if [ "$TASK" = "COMPLETE" ] || [ -z "$TASK" ]; then
            log "No more tasks to execute"
            break
        fi
        
        # EXECUTE phase
        run_execute "$TASK"
        
        # REVIEW phase
        run_review "$TASK"
        
        # Update cost (rough estimate: $0.10 per cycle)
        COST=$(echo "$COST + 0.10" | bc)
        
        log_cycle "Complete. Cost: \$$COST / \$$BUDGET"
        echo ""
        
        # Small delay between cycles
        sleep 2
    done
    
    log "Evolution finished after $CYCLE cycles"
}

main "$@"
