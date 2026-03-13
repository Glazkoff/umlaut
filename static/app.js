// Umlaut - JavaScript

const API_BASE = '';
let ws = null;
let currentProject = null;
let projectData = null;
let refreshInterval = null;
let debugMode = false;

// Phase descriptions
const PHASE_INFO = {
    IDLE: { icon: '💤', text: 'Evolution not started', color: 'secondary' },
    ANALYZE: { icon: '🔍', text: 'Analyzing codebase...', color: 'purple' },
    PLAN: { icon: '📋', text: 'Planning improvements...', color: 'warning' },
    EXECUTE: { icon: '⚡', text: 'Executing tasks...', color: 'primary' },
    REVIEW: { icon: '✅', text: 'Reviewing changes...', color: 'success' },
    PAUSED: { icon: '⏸️', text: 'Evolution paused', color: 'warning' },
    FINAL_REPORT: { icon: '📊', text: 'Evolution completed', color: 'success' },
    ASK_USER: { icon: '❓', text: 'Waiting for user input', color: 'danger' }
};

const CATEGORY_ICONS = {
    bug: '🐛',
    quality: '💎',
    test: '🧪',
    docs: '📚',
    perf: '⚡',
    security: '🔒',
    improvement: '✨'
};

// ============== Initialization ==============

document.addEventListener('DOMContentLoaded', () => {
    initWebSocket();
    loadProjects().then(() => {
        // Restore last selected project from localStorage
        const lastProject = localStorage.getItem('evolution_last_project');
        if (lastProject) {
            selectProject(lastProject);
        }
    });
    
    // Auto-refresh every 10 seconds when project is selected
    refreshInterval = setInterval(() => {
        if (currentProject) {
            loadProject(currentProject);
        }
    }, 10000);
});

// ============== WebSocket ==============

function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
    
    ws.onopen = () => updateConnectionStatus(true);
    ws.onmessage = (event) => handleWebSocketMessage(JSON.parse(event.data));
    ws.onclose = () => {
        updateConnectionStatus(false);
        setTimeout(initWebSocket, 3000);
    };
    ws.onerror = () => updateConnectionStatus(false);
}

function updateConnectionStatus(connected) {
    const indicator = document.getElementById('connectionStatus');
    const dot = indicator.querySelector('.dot');
    const text = indicator.querySelector('.text');
    
    dot.style.background = connected ? 'var(--accent-success)' : 'var(--accent-danger)';
    text.textContent = connected ? 'Connected' : 'Disconnected';
}

function handleWebSocketMessage(data) {
    switch (data.type) {
        case 'project_created':
            loadProjects();
            showNotification(`Project "${data.project}" created`, 'success');
            break;
        case 'project_deleted':
            loadProjects();
            if (currentProject === data.project) {
                currentProject = null;
                showEmptyState();
            }
            break;
        case 'task_created':
        case 'task_updated':
        case 'task_moved':
        case 'task_deleted':
            if (currentProject === data.project) {
                loadProject(currentProject);
            }
            break;
        case 'evolution_started':
        case 'evolution_paused':
        case 'evolution_resumed':
        case 'evolution_stopped':
            if (currentProject === data.project) {
                loadProject(currentProject);
            }
            showNotification(`Evolution: ${data.type.replace('evolution_', '')}`, 'info');
            break;
    }
}

// ============== API Calls ==============

async function apiCall(method, path, data = null) {
    const options = {
        method,
        headers: { 'Content-Type': 'application/json' }
    };
    
    if (data) options.body = JSON.stringify(data);
    
    const response = await fetch(`${API_BASE}${path}`, options);
    if (!response.ok) throw new Error((await response.json()).detail || 'API request failed');
    return response.status === 204 ? null : response.json();
}

// ============== Projects ==============

async function loadProjects() {
    try {
        const projects = await apiCall('GET', '/api/projects');
        updateProjectSelector(projects);
        return projects;
    } catch (error) {
        console.error('Failed to load projects:', error);
        return [];
    }
}

function updateProjectSelector(projects) {
    const select = document.getElementById('projectSelect');
    const lastProject = localStorage.getItem('evolution_last_project');
    select.innerHTML = '<option value="">Select Project...</option>';
    
    projects.forEach(project => {
        const option = document.createElement('option');
        option.value = project.name;
        const info = PHASE_INFO[project.phase] || PHASE_INFO.IDLE;
        option.textContent = `${project.name} ${info.icon}`;
        if (lastProject === project.name || currentProject === project.name) {
            option.selected = true;
        }
        select.appendChild(option);
    });
}

function selectProject(projectName) {
    if (!projectName) {
        currentProject = null;
        localStorage.removeItem('evolution_last_project');
        showEmptyState();
        return;
    }
    currentProject = projectName;
    localStorage.setItem('evolution_last_project', projectName);
    loadProject(projectName);
}

async function loadProject(projectName) {
    try {
        projectData = await apiCall('GET', `/api/projects/${projectName}`);
        renderProject(projectData);
        document.getElementById('emptyState').style.display = 'none';
        document.getElementById('projectView').style.display = 'flex';
        
        // Load history, cron status, and thinking config
        loadHistory();
        loadCronStatus();
        loadThinkingConfig();
    } catch (error) {
        console.error('Failed to load project:', error);
        showNotification('Failed to load project', 'error');
    }
}

function renderProject(data) {
    const { state, tasks, metrics } = data;
    
    // Header
    document.getElementById('projectName').textContent = state.project;
    const phaseInfo = PHASE_INFO[state.phase] || PHASE_INFO.IDLE;
    const phaseEl = document.getElementById('projectPhase');
    phaseEl.textContent = `${phaseInfo.icon} ${state.phase}`;
    phaseEl.className = `badge ${phaseInfo.color}`;
    
    // Update buttons
    updatePhaseButtons(state.phase);
    
    // Stats
    const budgetUsed = state.budget?.cost_usd || 0;
    const budgetLimit = state.budget?.limit_usd || 50;
    const budgetPct = (budgetUsed / budgetLimit * 100).toFixed(0);
    
    document.getElementById('statCycle').textContent = state.cycle || 0;
    document.getElementById('statBudget').textContent = `$${budgetUsed.toFixed(2)} / $${budgetLimit}`;
    document.getElementById('statDuration').textContent = `${state.duration_hours || 8}h`;
    document.getElementById('statTasksDone').textContent = tasks.done?.length || 0;
    
    const budgetProgress = document.getElementById('budgetProgress');
    budgetProgress.style.width = `${budgetPct}%`;
    budgetProgress.className = 'progress-fill' + (budgetPct > 80 ? ' danger' : budgetPct > 50 ? ' warning' : '');
    
    // Tests/Coverage from metrics
    if (metrics?.current) {
        const testsTotal = metrics.current.tests_total || 0;
        const testsPassing = metrics.current.tests_passing || 0;
        document.getElementById('statTests').textContent = testsTotal ? `${testsPassing}/${testsTotal}` : '-';
        document.getElementById('statCoverage').textContent = metrics.current.coverage_pct ? `${metrics.current.coverage_pct}%` : '-';
    } else {
        document.getElementById('statTests').textContent = '-';
        document.getElementById('statCoverage').textContent = '-';
    }
    
    // Current Activity
    renderCurrentActivity(state, tasks);
    
    // Tasks Summary
    renderTasksSummary(tasks);
    
    // Metrics
    renderMetrics(metrics);
}

function renderCurrentActivity(state, tasks) {
    const container = document.getElementById('currentActivity');
    const content = document.getElementById('activityContent');
    const phaseInfo = PHASE_INFO[state.phase] || PHASE_INFO.IDLE;
    
    const isRunning = ['ANALYZE', 'PLAN', 'EXECUTE', 'REVIEW'].includes(state.phase);
    
    if (!isRunning) {
        container.style.display = 'none';
        return;
    }
    
    container.style.display = 'block';
    
    // Find current task (first in progress)
    const currentTask = tasks.in_progress?.[0];
    
    let html = `
        <div class="activity-step">
            <span class="step-icon">${phaseInfo.icon}</span>
            <div class="step-text">
                <strong>${phaseInfo.text}</strong>
                ${currentTask ? `<br><span style="color: var(--text-secondary)">Task: ${currentTask.title}</span>` : ''}
            </div>
            <span class="step-time">Cycle ${state.cycle || 1}</span>
        </div>
    `;
    
    // Show last completed task if any
    const lastDone = tasks.done?.slice(-1)[0];
    if (lastDone) {
        html += `
            <div class="activity-step" style="opacity: 0.7">
                <span class="step-icon">✅</span>
                <div class="step-text">
                    <span style="color: var(--text-secondary)">Last completed:</span> ${lastDone.title}
                </div>
            </div>
        `;
    }
    
    content.innerHTML = html;
}

function renderTasksSummary(tasks) {
    const container = document.getElementById('tasksSummary');
    
    const groups = [
        { key: 'in_progress', title: '🔄 In Progress', icon: '⚡' },
        { key: 'backlog', title: '📋 Backlog', icon: '📝' },
        { key: 'blocked', title: '🚧 Blocked', icon: '⚠️' },
        { key: 'done', title: '✅ Done', icon: '🎉' }
    ];
    
    let html = '';
    
    groups.forEach(group => {
        const taskList = tasks[group.key] || [];
        if (taskList.length === 0 && group.key !== 'in_progress') return;
        
        html += `
            <div class="task-group">
                <div class="task-group-header">
                    <span class="task-group-title">${group.title}</span>
                    <span class="task-group-count">${taskList.length}</span>
                </div>
        `;
        
        taskList.slice(0, 5).forEach(task => {
            const catIcon = CATEGORY_ICONS[task.category] || '📋';
            const priorityClass = task.priority_score >= 7 ? 'priority-high' : task.priority_score >= 4 ? 'priority-medium' : 'priority-low';
            
            html += `
                <div class="task-item ${group.key}" onclick="showTaskDetail(${JSON.stringify(task).replace(/"/g, '&quot;')})">
                    <span class="task-icon">${catIcon}</span>
                    <div class="task-content">
                        <div class="task-title">${task.title}</div>
                        <div class="task-meta">
                            <span>I:${task.impact || 5} E:${task.effort || 5} R:${task.risk || 5}</span>
                        </div>
                    </div>
                    <span class="task-priority ${priorityClass}">${(task.priority_score || 5).toFixed(1)}</span>
                </div>
            `;
        });
        
        if (taskList.length > 5) {
            html += `<div style="text-align: center; color: var(--text-muted); font-size: 12px; padding: 8px;">+${taskList.length - 5} more</div>`;
        }
        
        html += '</div>';
    });
    
    container.innerHTML = html || '<div class="empty-activity">No tasks yet</div>';
}

function renderMetrics(metrics) {
    const container = document.getElementById('metricsGrid');
    
    if (!metrics?.current) {
        document.getElementById('metricsSection').style.display = 'none';
        return;
    }
    
    document.getElementById('metricsSection').style.display = 'block';
    
    const current = metrics.current || {};
    const baseline = metrics.baseline || {};
    
    const metricDefs = [
        { key: 'tests_total', label: 'Total Tests', format: v => v || '-' },
        { key: 'tests_passing', label: 'Passing Tests', format: v => v || '-' },
        { key: 'coverage_pct', label: 'Coverage', format: v => v ? `${v}%` : '-' },
        { key: 'lint_errors', label: 'Lint Errors', format: v => v || '0' },
        { key: 'lines_of_code', label: 'Lines of Code', format: v => v ? v.toLocaleString() : '-' },
        { key: 'complexity_score', label: 'Complexity', format: v => v || '-' }
    ];
    
    let html = '';
    metricDefs.forEach(def => {
        const value = current[def.key];
        const baseValue = baseline[def.key];
        const delta = value !== undefined && baseValue !== undefined ? value - baseValue : null;
        
        html += `
            <div class="metric-card">
                <div class="metric-value">${def.format(value)}</div>
                <div class="metric-label">${def.label}</div>
                ${delta !== null && delta !== 0 ? `
                    <div class="metric-delta ${delta > 0 ? 'positive' : delta < 0 ? 'negative' : 'neutral'}">
                        ${delta > 0 ? '+' : ''}${delta}
                    </div>
                ` : ''}
            </div>
        `;
    });
    
    container.innerHTML = html;
}

async function loadHistory() {
    if (!currentProject) return;
    
    try {
        const result = await apiCall('GET', `/api/projects/${currentProject}/history?limit=20&debug=${debugMode}`);
        renderHistory(result.history || []);
        
        // Show debug info if available
        if (debugMode && result.debug_info) {
            renderDebugInfo(result.debug_info);
        } else {
            document.getElementById('debugInfo').style.display = 'none';
        }
    } catch (error) {
        console.error('Failed to load history:', error);
    }
}

function renderHistory(history) {
    const container = document.getElementById('activityFeed');
    
    if (!history.length) {
        container.innerHTML = '<div class="empty-activity">No recent activity</div>';
        return;
    }
    
    let html = '';
    history.forEach(item => {
        const time = item.timestamp ? new Date(item.timestamp).toLocaleTimeString() : '';
        const type = item.type || 'info';
        const forced = item.forced ? ' ⚡' : '';
        
        html += `
            <div class="activity-item ${type}">
                <span class="activity-time">${time}</span>
                <span class="activity-text">${item.message || item.action || JSON.stringify(item)}${forced}</span>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

function renderDebugInfo(debugInfo) {
    const container = document.getElementById('debugInfo');
    container.style.display = 'block';
    
    let html = `
        <div class="debug-header">
            <h4>🔧 Debug Mode</h4>
            <span class="debug-time">${new Date(debugInfo.current_time).toLocaleString()}</span>
        </div>
    `;
    
    // Processes
    if (debugInfo.processes && debugInfo.processes.length > 0) {
        html += `
            <div class="debug-section">
                <h5>⚡ Active Processes (${debugInfo.processes.length})</h5>
                <div class="debug-processes">
                    ${debugInfo.processes.map(p => `<div class="debug-process">${escapeHtml(p)}</div>`).join('')}
                </div>
            </div>
        `;
    } else {
        html += `
            <div class="debug-section">
                <h5>⚡ Active Processes</h5>
                <div class="debug-empty">No evolution processes running</div>
            </div>
        `;
    }
    
    // Recent Logs
    if (debugInfo.recent_logs && debugInfo.recent_logs.length > 0) {
        html += `<div class="debug-section"><h5>📜 Recent Logs</h5>`;
        debugInfo.recent_logs.forEach(log => {
            html += `
                <div class="debug-log">
                    <div class="debug-log-file">${log.file}</div>
                    <div class="debug-log-content">
                        ${log.last_lines.map(line => `<div class="log-line">${escapeHtml(line)}</div>`).join('')}
                    </div>
                </div>
            `;
        });
        html += `</div>`;
    }
    
    container.innerHTML = html;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function forceEvolutionCycle() {
    if (!currentProject) return;
    
    if (!confirm('Force run next evolution cycle now?\n\nThis will start a new cycle immediately.')) {
        return;
    }
    
    try {
        const result = await apiCall('POST', `/api/projects/${currentProject}/force-cycle`);
        showNotification(result.message, 'success');
        
        // Refresh after a short delay
        setTimeout(() => {
            loadProject(currentProject);
            loadHistory();
        }, 2000);
    } catch (error) {
        showNotification('Failed to force cycle: ' + error.message, 'error');
    }
}

async function rollbackProject() {
    if (!currentProject) return;
    
    if (!confirm('⚠️ ROLLBACK WARNING\n\nThis will:\n• Reset project to IDLE state\n• Move ALL tasks to backlog\n• Clear history and logs\n• Reset git repository to origin/main\n\nThis action CANNOT be undone!\n\nAre you sure?')) {
        return;
    }
    
    try {
        const result = await apiCall('POST', `/api/projects/${currentProject}/rollback`);
        showNotification(result.message, 'warning');
        
        // Refresh after a short delay
        setTimeout(() => {
            loadProject(currentProject);
            loadHistory();
            loadCronStatus();
        }, 1000);
    } catch (error) {
        showNotification('Failed to rollback: ' + error.message, 'error');
    }
}

function toggleDebugMode() {
    debugMode = !debugMode;
    const btn = document.getElementById('btnDebug');
    if (btn) {
        btn.textContent = debugMode ? '🔧 Debug: ON' : '🔧 Debug';
        btn.className = debugMode ? 'btn btn-sm btn-warning' : 'btn btn-sm btn-secondary';
    }
    loadHistory();
}

// ============== Cron Management ==============

async function loadCronStatus() {
    try {
        const status = await apiCall('GET', '/api/cron/status');
        renderCronStatus(status);
    } catch (error) {
        console.error('Failed to load cron status:', error);
        document.getElementById('cronContent').innerHTML = 
            '<div class="cron-error">Failed to load cron status</div>';
    }
}

function renderCronStatus(status) {
    const container = document.getElementById('cronContent');
    
    if (!status.configured || status.jobs.length === 0) {
        container.innerHTML = `
            <div class="cron-empty">
                <span class="cron-icon">⏰</span>
                <span class="cron-text">No scheduled jobs configured</span>
                <button onclick="showCronModal()" class="btn btn-sm btn-primary">Setup Now</button>
            </div>
        `;
        return;
    }
    
    let html = '<div class="cron-jobs">';
    status.jobs.forEach(job => {
        html += `
            <div class="cron-job">
                <div class="cron-job-info">
                    <span class="cron-project">${job.project}</span>
                    <span class="cron-schedule">${job.schedule_text}</span>
                </div>
                <div class="cron-job-actions">
                    <span class="cron-badge ${job.enabled ? 'enabled' : 'disabled'}">
                        ${job.enabled ? '✓ Active' : '✗ Disabled'}
                    </span>
                    <button onclick="removeCronJob('${job.project}')" class="btn btn-sm btn-danger">Remove</button>
                </div>
            </div>
        `;
    });
    html += '</div>';
    
    container.innerHTML = html;
}

function showCronModal() {
    // Populate project dropdown
    const select = document.getElementById('cronProject');
    select.innerHTML = '';
    
    // Get all projects
    apiCall('GET', '/api/projects').then(projects => {
        projects.forEach(project => {
            const option = document.createElement('option');
            option.value = project.name;
            option.textContent = project.name;
            if (currentProject === project.name) {
                option.selected = true;
            }
            select.appendChild(option);
        });
    });
    
    document.getElementById('cronModal').classList.add('active');
}

async function setupCronJob() {
    const project = document.getElementById('cronProject').value;
    const interval = parseInt(document.getElementById('cronInterval').value);
    
    if (!project) {
        showNotification('Please select a project', 'error');
        return;
    }
    
    try {
        const result = await apiCall('POST', `/api/cron/setup?project_name=${project}&interval_minutes=${interval}`);
        showNotification(result.message, 'success');
        closeModal('cronModal');
        loadCronStatus();
    } catch (error) {
        showNotification('Failed to setup cron: ' + error.message, 'error');
    }
}

async function removeCronJob(projectName) {
    if (!confirm(`Remove scheduled job for ${projectName}?`)) return;
    
    try {
        await apiCall('DELETE', `/api/cron/${projectName}`);
        showNotification('Cron job removed', 'info');
        loadCronStatus();
    } catch (error) {
        showNotification('Failed to remove cron: ' + error.message, 'error');
    }
}

// ============== Thinking Configuration ==============

async function loadThinkingConfig() {
    if (!currentProject) return;
    
    try {
        const config = await apiCall('GET', `/api/projects/${currentProject}/config`);
        const thinkingLevels = config.thinking_levels || {
            ANALYZE: 'high',
            PLAN: 'medium',
            EXECUTE: 'medium',
            REVIEW: 'low'
        };
        
        // Update select elements
        document.getElementById('thinkingAnalyze').value = thinkingLevels.ANALYZE || 'high';
        document.getElementById('thinkingPlan').value = thinkingLevels.PLAN || 'medium';
        document.getElementById('thinkingExecute').value = thinkingLevels.EXECUTE || 'medium';
        document.getElementById('thinkingReview').value = thinkingLevels.REVIEW || 'low';
        
        // Show thinking section
        document.getElementById('thinkingSection').style.display = 'block';
    } catch (error) {
        console.error('Failed to load thinking config:', error);
    }
}

async function saveThinkingConfig() {
    if (!currentProject) return;
    
    const thinkingLevels = {
        ANALYZE: document.getElementById('thinkingAnalyze').value,
        PLAN: document.getElementById('thinkingPlan').value,
        EXECUTE: document.getElementById('thinkingExecute').value,
        REVIEW: document.getElementById('thinkingReview').value
    };
    
    try {
        // Update each phase
        for (const [phase, level] of Object.entries(thinkingLevels)) {
            await apiCall('PUT', `/api/projects/${currentProject}/config/thinking?phase=${phase}&level=${level}`);
        }
        
        showNotification('Thinking levels saved successfully!', 'success');
    } catch (error) {
        showNotification('Failed to save thinking config: ' + error.message, 'error');
    }
}

function updatePhaseButtons(phase) {
    const btnStart = document.getElementById('btnStart');
    const btnPause = document.getElementById('btnPause');
    const btnResume = document.getElementById('btnResume');
    const btnStop = document.getElementById('btnStop');
    
    [btnStart, btnPause, btnResume, btnStop].forEach(btn => btn.style.display = 'none');
    
    switch (phase) {
        case 'IDLE':
        case 'FINAL_REPORT':
            btnStart.style.display = 'inline-flex';
            break;
        case 'PAUSED':
            btnResume.style.display = 'inline-flex';
            btnStop.style.display = 'inline-flex';
            break;
        default:
            if (['ANALYZE', 'PLAN', 'EXECUTE', 'REVIEW'].includes(phase)) {
                btnPause.style.display = 'inline-flex';
                btnStop.style.display = 'inline-flex';
            }
    }
}

// ============== Evolution Controls ==============

async function startEvolution() {
    try {
        await apiCall('POST', `/api/projects/${currentProject}/start`);
        showNotification('Evolution started!', 'success');
    } catch (error) {
        showNotification('Failed to start evolution', 'error');
    }
}

async function pauseEvolution() {
    try {
        await apiCall('POST', `/api/projects/${currentProject}/pause`);
        showNotification('Evolution paused', 'warning');
    } catch (error) {
        showNotification('Failed to pause evolution', 'error');
    }
}

async function resumeEvolution() {
    try {
        await apiCall('POST', `/api/projects/${currentProject}/resume`);
        showNotification('Evolution resumed', 'success');
    } catch (error) {
        showNotification('Failed to resume evolution', 'error');
    }
}

async function stopEvolution() {
    if (!confirm('Stop evolution and generate final report?')) return;
    try {
        await apiCall('POST', `/api/projects/${currentProject}/stop`);
        showNotification('Evolution stopped', 'info');
    } catch (error) {
        showNotification('Failed to stop evolution', 'error');
    }
}

// ============== Modal Functions ==============

function showNewProjectModal() {
    document.getElementById('newProjectModal').classList.add('active');
}

function showAddTaskModal(status) {
    document.getElementById('addTaskModal').classList.add('active');
}

function showTaskDetail(task) {
    const modal = document.getElementById('taskDetailModal');
    document.getElementById('taskDetailTitle').textContent = task.title;
    
    const body = document.getElementById('taskDetailBody');
    body.innerHTML = `
        <div class="form-group">
            <label>Description</label>
            <p>${task.description || 'No description'}</p>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label>Impact</label>
                <p>${task.impact || 5}/10</p>
            </div>
            <div class="form-group">
                <label>Effort</label>
                <p>${task.effort || 5}/10</p>
            </div>
            <div class="form-group">
                <label>Risk</label>
                <p>${task.risk || 5}/10</p>
            </div>
        </div>
        <div class="form-group">
            <label>Priority Score</label>
            <p>${(task.priority_score || 5).toFixed(2)}</p>
        </div>
        ${task.acceptance_criteria?.length ? `
            <div class="form-group">
                <label>Acceptance Criteria</label>
                <ul>${task.acceptance_criteria.map(c => `<li>${c}</li>`).join('')}</ul>
            </div>
        ` : ''}
        ${task.commits?.length ? `
            <div class="form-group">
                <label>Commits</label>
                <ul>${task.commits.map(c => `<li><code>${c}</code></li>`).join('')}</ul>
            </div>
        ` : ''}
    `;
    
    const footer = document.getElementById('taskDetailFooter');
    footer.innerHTML = `
        <button class="btn btn-danger" onclick="deleteTask('${task.id}')">🗑 Delete</button>
        <button class="btn btn-secondary" onclick="closeModal('taskDetailModal')">Close</button>
    `;
    
    modal.classList.add('active');
}

function showReport() {
    loadReport();
    document.getElementById('reportModal').classList.add('active');
}

async function loadReport() {
    try {
        const result = await apiCall('GET', `/api/projects/${currentProject}/report`);
        document.getElementById('reportContent').innerHTML = parseMarkdown(result.report || 'No report available');
    } catch (error) {
        document.getElementById('reportContent').textContent = 'Report not available yet.';
    }
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

// ============== CRUD Operations ==============

async function createProject() {
    const name = document.getElementById('newProjectName').value.trim();
    const budget = parseFloat(document.getElementById('newProjectBudget').value) || 50;
    const duration = parseInt(document.getElementById('newProjectDuration').value) || 8;
    const repoUrl = document.getElementById('newProjectRepo').value.trim();
    
    if (!name) {
        showNotification('Project name is required', 'error');
        return;
    }
    
    try {
        await apiCall('POST', '/api/projects', {
            name,
            budget_limit: budget,
            duration_hours: duration,
            config: { repo_url: repoUrl }
        });
        
        closeModal('newProjectModal');
        showNotification(`Project "${name}" created`, 'success');
        setTimeout(() => selectProject(name), 500);
    } catch (error) {
        showNotification('Failed to create project', 'error');
    }
}

async function addTask() {
    const title = document.getElementById('taskTitle').value.trim();
    const description = document.getElementById('taskDescription').value.trim();
    const category = document.getElementById('taskCategory').value;
    const impact = parseInt(document.getElementById('taskImpact').value) || 5;
    const effort = parseInt(document.getElementById('taskEffort').value) || 5;
    const risk = parseInt(document.getElementById('taskRisk').value) || 5;
    
    if (!title) {
        showNotification('Task title is required', 'error');
        return;
    }
    
    const priority_score = impact / (effort * risk);
    
    try {
        await apiCall('POST', `/api/projects/${currentProject}/tasks`, {
            id: `task-${Date.now()}`,
            title,
            description,
            category,
            impact,
            effort,
            risk,
            priority_score,
            status: 'backlog',
            dependencies: [],
            acceptance_criteria: [],
            created_at: new Date().toISOString()
        });
        
        closeModal('addTaskModal');
        showNotification('Task added', 'success');
        
        document.getElementById('taskTitle').value = '';
        document.getElementById('taskDescription').value = '';
    } catch (error) {
        showNotification('Failed to add task', 'error');
    }
}

async function deleteTask(taskId) {
    if (!confirm('Delete this task?')) return;
    
    try {
        await apiCall('DELETE', `/api/projects/${currentProject}/tasks/${taskId}`);
        closeModal('taskDetailModal');
        showNotification('Task deleted', 'info');
    } catch (error) {
        showNotification('Failed to delete task', 'error');
    }
}

function downloadReport() {
    const content = document.getElementById('reportContent').innerText;
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `evolution-report-${currentProject}.md`;
    a.click();
    URL.revokeObjectURL(url);
}

// ============== Helpers ==============

function showEmptyState() {
    document.getElementById('emptyState').style.display = 'flex';
    document.getElementById('projectView').style.display = 'none';
}

function showNotification(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function parseMarkdown(text) {
    return text
        .replace(/^### (.*$)/gim, '<h3>$1</h3>')
        .replace(/^## (.*$)/gim, '<h2>$1</h2>')
        .replace(/^# (.*$)/gim, '<h1>$1</h1>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`(.*?)`/g, '<code>$1</code>')
        .replace(/^- (.*$)/gim, '<li>$1</li>')
        .replace(/\n/g, '<br>');
}
