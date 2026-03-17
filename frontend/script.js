const API_BASE = window.location.origin;
let currentAnalysisId = null;
let pollInterval = null;
let logsInterval = null;

// Auth Check
if (!localStorage.getItem('auth_token') && !window.location.pathname.endsWith('login.html')) {
    window.location.href = 'login.html';
}

async function apiFetch(endpoint, options = {}) {
    const token = localStorage.getItem('auth_token');
    const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
        ...options.headers
    };
    
    const res = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
    if (res.status === 401 && !window.location.pathname.endsWith('login.html')) {
        localStorage.removeItem('auth_token');
        window.location.href = 'login.html';
    }
    return res;
}

// Selectors
const historyList = document.getElementById("historyList");
const welcomeView = document.getElementById("welcomeView");
const reportView = document.getElementById("reportView");
const reportAccordion = document.getElementById("reportAccordion");
const urlInput = document.getElementById("urlInput");
const limitInput = document.getElementById("limitInput");
const btnAnalyze = document.getElementById("btnAnalyze");
const btnNew = document.getElementById("btnNew");
const btnToggleLogs = document.getElementById("btnToggleLogs");
const btnCloseLogs = document.getElementById("btnCloseLogs");
const logsPanel = document.getElementById("logsPanel");
const logsContainer = document.getElementById("logsContainer");

// Init
window.addEventListener("DOMContentLoaded", () => {
    if (localStorage.getItem('auth_token')) {
        loadHistory();
        setupLogs();
    }
});

function setupLogs() {
    btnToggleLogs.onclick = () => {
        logsPanel.classList.toggle("active");
        if (logsPanel.classList.contains("active")) {
            startLogsPolling();
        } else {
            stopLogsPolling();
        }
    };
    
    btnCloseLogs.onclick = () => {
        logsPanel.classList.remove("active");
        stopLogsPolling();
    };
}

async function startLogsPolling() {
    if (logsInterval) return;
    fetchLogs(); // Initial
    logsInterval = setInterval(fetchLogs, 3000);
}

function stopLogsPolling() {
    clearInterval(logsInterval);
    logsInterval = null;
}

async function fetchLogs() {
    try {
        const res = await apiFetch(`/logs`);
        const data = await res.json();
        renderLogs(data.logs);
    } catch (err) {
        console.error("Error fetching logs:", err);
    }
}

function renderLogs(logs) {
    const isAtBottom = logsContainer.scrollHeight - logsContainer.scrollTop <= logsContainer.clientHeight + 50;
    
    logsContainer.innerHTML = logs.map(log => {
        let levelClass = "log-level-info";
        if (log.includes(" - WARNING - ")) levelClass = "log-level-warning";
        if (log.includes(" - ERROR - ")) levelClass = "log-level-error";
        if (log.includes(" - CRITICAL - ")) levelClass = "log-level-critical";
        
        return `<div class="log-line ${levelClass}">${escapeHtml(log)}</div>`;
    }).join("");
    
    if (isAtBottom) {
        logsContainer.scrollTop = logsContainer.scrollHeight;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function loadHistory() {
    try {
        const res = await apiFetch(`/history`);
        const history = await res.json();
        
        historyList.innerHTML = "";
        history.forEach(item => {
            const el = document.createElement("div");
            el.className = `history-item ${currentAnalysisId === item.id ? 'active' : ''}`;
            el.innerHTML = `
                <div class="item-info" onclick="viewAnalysis(${item.id})">
                    <div class="item-name" title="${item.name}">${item.name}</div>
                    <div class="item-date">${new Date(item.created_at).toLocaleDateString()}</div>
                </div>
                <div class="item-actions">
                    <button class="action-btn" onclick="editName(${item.id}, '${item.name}')"><i class="fas fa-ellipsis-v"></i></button>
                    <button class="action-btn" onclick="deleteAnalysis(${item.id})"><i class="fas fa-trash"></i></button>
                </div>
            `;
            historyList.appendChild(el);
        });
    } catch (err) {
        console.error("Error loading history:", err);
    }
}

async function viewAnalysis(id) {
    currentAnalysisId = id;
    welcomeView.style.display = "none";
    reportView.style.display = "block";
    
    // Clear previous polling
    if (pollInterval) clearInterval(pollInterval);
    
    await fetchAndRenderAnalysis(id);
    loadHistory(); // To update active state
}

async function fetchAndRenderAnalysis(id) {
    try {
        const res = await apiFetch(`/analysis/${id}`);
        const data = await res.json();
        
        const { analysis, reports } = data;
        
        document.getElementById("currentName").innerText = analysis.name;
        document.getElementById("currentUrl").innerText = analysis.main_url;
        
        const statusEl = document.getElementById("currentStatus");
        statusEl.innerText = analysis.status.toUpperCase();
        statusEl.className = `status-badge status-${analysis.status}`;
        
        renderAccordions(analysis, reports);
        
        // Poll if still processing
        if (analysis.status === "processing" || analysis.status === "pending") {
            if (!pollInterval) {
                pollInterval = setInterval(() => fetchAndRenderAnalysis(id), 5000);
            }
        } else {
            if (pollInterval) {
                clearInterval(pollInterval);
                pollInterval = null;
            }
        }
    } catch (err) {
        console.error("Error fetching analysis:", err);
    }
}

function renderAccordions(analysis, reports) {
    reportAccordion.innerHTML = "";
    
    // General Summary Accordion
    if (analysis.global_summary || analysis.status === "processing") {
        const genItem = document.createElement("div");
        genItem.className = "accordion-item general-summary active";
        genItem.innerHTML = `
            <div class="accordion-header" onclick="toggleAccordion(this)">
                <span><i class="fas fa-globe"></i> Resumen General</span>
                <i class="fas fa-chevron-down"></i>
            </div>
            <div class="accordion-content">
                <div class="markdown-content">
                    ${analysis.global_summary ? marked.parse(analysis.global_summary) : '<p>Generando resumen global con IA...</p>'}
                </div>
            </div>
        `;
        reportAccordion.appendChild(genItem);
    }
    
    // Individual Page Accordions
    reports.forEach(report => {
        const item = document.createElement("div");
        item.className = "accordion-item";
        item.innerHTML = `
            <div class="accordion-header" onclick="toggleAccordion(this)">
                <span><i class="fas fa-file-alt"></i> ${report.url}</span>
                <i class="fas fa-chevron-down"></i>
            </div>
            <div class="accordion-content">
                <div class="report-grid">
                    <div>
                        <div class="col-header">Hallazgos (Críticos, Warnings, Buenos)</div>
                        <div class="markdown-content">${marked.parse(report.summary_left)}</div>
                    </div>
                    <div>
                        <div class="col-header">Plan de Acción</div>
                        <div class="markdown-content">${marked.parse(report.action_plan_right)}</div>
                    </div>
                </div>
            </div>
        `;
        reportAccordion.appendChild(item);
    });
}

function toggleAccordion(header) {
    const item = header.parentElement;
    item.classList.toggle("active");
}

btnAnalyze.onclick = async () => {
    const url = urlInput.value;
    const limit = limitInput.value;
    if (!url) return alert("Por favor ingresa una URL");
    
    try {
        const res = await apiFetch(`/analyze?url=${encodeURIComponent(url)}&limit=${limit}`, { method: "POST" });
        const data = await res.json();
        viewAnalysis(data.id);
    } catch (err) {
        alert("Error al iniciar análisis");
    }
};

btnNew.onclick = () => {
    currentAnalysisId = null;
    welcomeView.style.display = "block";
    reportView.style.display = "none";
    loadHistory();
};

async function deleteAnalysis(id) {
    if (!confirm("¿Eliminar este análisis?")) return;
    await apiFetch(`/analysis/${id}`, { method: "DELETE" });
    if (currentAnalysisId === id) btnNew.onclick();
    loadHistory();
}

async function editName(id, currentName) {
    const newName = prompt("Nuevo nombre del sitio:", currentName);
    if (newName && newName !== currentName) {
        await apiFetch(`/analysis/${id}?name=${encodeURIComponent(newName)}`, { method: "PUT" });
        loadHistory();
        if (currentAnalysisId === id) document.getElementById("currentName").innerText = newName;
    }
}
