// ── State ───────────────────────────────────────────────
const API_BASE = window.location.origin;
let currentAnalysisId = null;
let pollInterval = null;
let activeTabIndex = 'global';
let criteriaData = null; // cached criteria response
let currentAnalysisUrl = null;
let currentAnalysisLimit = 10;
let _renderPageUrl = '';
let _renderReportId = 0;

// ── Auth guard ──────────────────────────────────────────
if (!localStorage.getItem('auth_token') && !window.location.pathname.endsWith('login.html')) {
    window.location.href = 'login.html';
}

async function apiFetch(endpoint, options = {}) {
    const token = localStorage.getItem('auth_token');
    const res = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
            ...(options.headers || {}),
        },
    });
    if (res.status === 401) {
        localStorage.removeItem('auth_token');
        window.location.href = 'login.html';
    }
    return res;
}

// ── DOM refs ────────────────────────────────────────────
const welcomeView  = document.getElementById('welcomeView');
const reportView   = document.getElementById('reportView');
const historyList  = document.getElementById('historyList');
const urlInput     = document.getElementById('urlInput');
const limitInput   = document.getElementById('limitInput');
const allPagesCheck = document.getElementById('allPagesCheck');
const btnAnalyze   = document.getElementById('btnAnalyze');
const btnNew       = document.getElementById('btnNew');
const tabNav       = document.getElementById('tabNav');
const tabPanels    = document.getElementById('tabPanels');
const tabEmpty     = document.getElementById('tabEmpty');
const scanLine     = document.getElementById('scanLine');
const statErrors   = document.getElementById('statErrors');
const statWarnings = document.getElementById('statWarnings');
const statNotices  = document.getElementById('statNotices');
const statusPill   = document.getElementById('currentStatus');
const btnReanalyze = document.getElementById('btnReanalyze');

// ── Init ────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
    if (localStorage.getItem('auth_token')) loadHistory();
});

// ── Navigation ──────────────────────────────────────────
function showView(name) {
    welcomeView.classList.toggle('active', name === 'welcome');
    reportView.classList.toggle('active', name === 'report');
}

btnNew.onclick = () => {
    stopPolling();
    currentAnalysisId = null;
    showView('welcome');
    loadHistory();
};

btnReanalyze.onclick = async () => {
    if (!currentAnalysisUrl) return;
    btnReanalyze.disabled = true;
    try {
        const res = await apiFetch(`/analyze?url=${encodeURIComponent(currentAnalysisUrl)}&limit=${currentAnalysisLimit}`, { method: 'POST' });
        const data = await res.json();
        viewAnalysis(data.id);
    } catch (e) { console.error(e); }
    finally { btnReanalyze.disabled = false; }
};

// ── History ─────────────────────────────────────────────
async function loadHistory() {
    try {
        const res = await apiFetch('/history');
        const items = await res.json();
        historyList.innerHTML = '';
        items.forEach(item => {
            const el = document.createElement('div');
            el.className = 'history-item' + (item.id === currentAnalysisId ? ' active' : '');
            el.innerHTML = `
                <div class="item-info" style="cursor:pointer" onclick="viewAnalysis(${item.id})">
                    <div class="item-name" title="${esc(item.name)}">${esc(item.name)}</div>
                    <div class="item-date">${fmtDate(item.created_at)}</div>
                </div>
                <div class="item-actions">
                    <button class="action-btn" title="Renombrar" onclick="renameAnalysis(${item.id},'${esc(item.name)}')">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                    </button>
                    <button class="action-btn delete" title="Eliminar" onclick="deleteAnalysis(${item.id})">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/></svg>
                    </button>
                </div>
            `;
            historyList.appendChild(el);
        });
    } catch (e) { console.error(e); }
}

// ── Start analysis ───────────────────────────────────────
// Toggle limit input when "Todas" checkbox changes
if (allPagesCheck) {
    allPagesCheck.addEventListener('change', () => {
        limitInput.disabled = allPagesCheck.checked;
        if (allPagesCheck.checked) limitInput.value = '9999';
        else limitInput.value = '10';
    });
}

btnAnalyze.onclick = async () => {
    let url = urlInput.value.trim();
    const limit = allPagesCheck && allPagesCheck.checked ? 9999 : (parseInt(limitInput.value) || 10);
    if (!url) { urlInput.focus(); return; }
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
        url = 'https://' + url;
        urlInput.value = url;
    }
    btnAnalyze.disabled = true;
    btnAnalyze.textContent = 'Iniciando…';
    try {
        const res = await apiFetch(`/analyze?url=${encodeURIComponent(url)}&limit=${limit}`, { method: 'POST' });
        const data = await res.json();
        viewAnalysis(data.id);
    } catch (e) {
        console.error(e);
    } finally {
        btnAnalyze.disabled = false;
        btnAnalyze.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg> Iniciar auditoría`;
    }
};

// ── View an analysis ─────────────────────────────────────
async function viewAnalysis(id) {
    stopPolling();
    currentAnalysisId = id;
    showView('report');
    resetReportUI();
    await fetchAndRender(id);
    loadHistory();
}

function resetReportUI() {
    activeTabIndex = 'global';
    document.getElementById('currentName').textContent = '—';
    document.getElementById('currentUrl').textContent = '';
    setStatBadge(statErrors, '—');
    setStatBadge(statWarnings, '—');
    setStatBadge(statNotices, '—');
    statusPill.textContent = '—';
    statusPill.className = 'status-pill status-pending';
    // Clear tabs except label
    const label = tabNav.querySelector('.tab-nav-label');
    tabNav.innerHTML = '';
    tabNav.appendChild(label);
    tabPanels.innerHTML = '';
    tabPanels.appendChild(tabEmpty);
    tabEmpty.style.display = 'flex';
    scanLine.classList.remove('scanning');
}

// ── Fetch & render ────────────────────────────────────────
async function fetchAndRender(id) {
    try {
        // Always fetch base analysis for status/counters
        const baseRes = await apiFetch(`/analysis/${id}`);
        const baseData = await baseRes.json();
        const { analysis, reports } = baseData;

        document.getElementById('currentName').textContent = analysis.name;
        document.getElementById('currentUrl').textContent = analysis.main_url;
        currentAnalysisUrl = analysis.main_url;
        currentAnalysisLimit = analysis.max_pages || 10;

        setStatBadge(statErrors,   analysis.total_errors   ?? '—');
        setStatBadge(statWarnings, analysis.total_warnings ?? '—');
        setStatBadge(statNotices,  analysis.total_notices  ?? '—');

        const isRunning = analysis.status === 'pending' || analysis.status === 'processing';
        statusPill.textContent = statusLabel(analysis.status);
        statusPill.className = `status-pill status-${analysis.status}`;
        scanLine.classList.toggle('scanning', isRunning);

        if (reports.length > 0) {
            // Fetch criteria-mapped data
            const critRes = await apiFetch(`/analysis/${id}/criteria`);
            const newCriteriaData = await critRes.json();
            // Only re-render if data actually changed (new pages or status change)
            const prevCount = criteriaData ? (criteriaData.pages || []).length : 0;
            const newCount = (newCriteriaData.pages || []).length;
            if (!criteriaData || newCount !== prevCount || !isRunning) {
                criteriaData = newCriteriaData;
                tabEmpty.style.display = 'none';
                renderTabs(criteriaData.pages);
            }
        } else if (isRunning) {
            tabEmpty.style.display = 'flex';
        }

        if (isRunning) {
            if (!pollInterval) pollInterval = setInterval(() => fetchAndRender(id), 4000);
        } else {
            stopPolling();
        }
    } catch (e) {
        if (e && e.message) console.warn('fetchAndRender:', e.message);
    }
}

function stopPolling() {
    clearInterval(pollInterval);
    pollInterval = null;
}

// ── Tabs ──────────────────────────────────────────────────
function titleFromPath(path) {
    if (!path || path === '/') return 'Inicio';
    const parts = path.replace(/\/$/, '').split('/').filter(Boolean);
    const last = parts[parts.length - 1] || 'Página';
    return last.replace(/[-_]/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function renderTabs(pages) {
    const label = tabNav.querySelector('.tab-nav-label');
    tabNav.innerHTML = '';
    tabNav.appendChild(label);
    tabPanels.innerHTML = '';
    tabPanels.appendChild(tabEmpty);

    // ── Global issues tab (first) ────────────────────────
    const globalIssues = buildGlobalIssuesData(pages);
    const globalErrors = globalIssues.filter(i => i.type === 'error').length;
    const globalBtn = document.createElement('button');
    globalBtn.className = 'tab-btn tab-btn-global' + (activeTabIndex === 'global' ? ' active' : '');
    globalBtn.dataset.index = 'global';
    globalBtn.innerHTML = `
        <div class="tab-btn-row">
            <span class="tab-btn-title">Visión Global</span>
        </div>
        <span class="tab-btn-slug">Errores comunes del sitio</span>
        <span class="tab-btn-counts">
            ${globalErrors > 0 ? `<span class="tab-count e">${globalErrors}</span>` : ''}
        </span>
    `;
    globalBtn.onclick = () => selectTab('global');
    tabNav.appendChild(globalBtn);

    const globalPanel = document.createElement('div');
    globalPanel.className = 'tab-panel' + (activeTabIndex === 'global' ? ' active' : '');
    globalPanel.dataset.index = 'global';
    globalPanel.innerHTML = buildGlobalIssuesPanelHTML(pages, globalIssues);
    tabPanels.appendChild(globalPanel);

    // ── Per-page tabs ────────────────────────────────────
    pages.forEach((page, i) => {
        const path = urlPath(page.url);
        const pageTitle = page.page_title || titleFromPath(path);
        const failCount = countCriteriaStatus(page, 'fail');
        const manualCount = countCriteriaStatus(page, 'manual');
        const idx = String(i);

        const btn = document.createElement('button');
        btn.className = 'tab-btn' + (activeTabIndex === idx ? ' active' : '');
        btn.dataset.index = idx;
        btn.innerHTML = `
            <div class="tab-btn-row">
                <span class="tab-btn-title" title="${esc(page.url)}">${esc(pageTitle)}</span>
                <a class="tab-btn-link" href="${esc(page.url)}" target="_blank" rel="noopener"
                   onclick="event.stopPropagation()" title="Abrir página en nueva pestaña">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                        <polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
                    </svg>
                </a>
            </div>
            <span class="tab-btn-slug" title="${esc(page.url)}">${esc(path)}</span>
            <span class="tab-btn-counts">
                ${failCount   > 0 ? `<span class="tab-count e">${failCount}F</span>`   : ''}
                ${manualCount > 0 ? `<span class="tab-count m">${manualCount}M</span>` : ''}
            </span>
        `;
        btn.onclick = () => selectTab(idx);
        tabNav.appendChild(btn);

        const panel = document.createElement('div');
        panel.className = 'tab-panel' + (activeTabIndex === idx ? ' active' : '');
        panel.dataset.index = idx;
        panel.innerHTML = buildCriteriaPanelHTML(page);
        tabPanels.appendChild(panel);
    });
}

function countCriteriaStatus(page, status) {
    let count = 0;
    Object.values(page.sections || {}).forEach(criteria => {
        criteria.forEach(c => { if (c.status === status) count++; });
    });
    return count;
}

function selectTab(index) {
    activeTabIndex = index;
    const idx = String(index);
    tabNav.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.index === idx));
    tabPanels.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.dataset.index === idx));
}

const SECTION_ICONS = {
    'Perceptibilidad': `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`,
    'Operabilidad':    `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg>`,
    'Comprensibilidad':`<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`,
    'Robustez':        `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`,
};

function buildCriteriaPanelHTML(page) {
    _renderPageUrl = page.url || '';
    _renderReportId = page.id || 0;
    const sections = page.sections || {};
    const sectionOrder = ['Perceptibilidad', 'Operabilidad', 'Comprensibilidad', 'Robustez'];

    const failTotal   = countCriteriaStatus(page, 'fail');
    const manualTotal = countCriteriaStatus(page, 'manual');
    const passTotal   = countCriteriaStatus(page, 'pass');

    let html = `
        <div class="panel-header">
            <div class="panel-url">
                <a class="panel-url-link" href="${esc(page.url)}" target="_blank" rel="noopener" title="Abrir página en nueva pestaña">
                    ${esc(page.url)}
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                </a>
            </div>
            <div class="panel-summary">
                <span class="panel-stat e"><strong>${failTotal}</strong> fallos automáticos</span>
                <span class="panel-stat m"><strong>${manualTotal}</strong> verificación manual</span>
                <span class="panel-stat p"><strong>${passTotal}</strong> superados</span>
            </div>
        </div>
    `;

    if (page.status === 'error' && page.error_msg) {
        html += `<div class="panel-error-msg">${esc(page.error_msg)}</div>`;
    }

    sectionOrder.forEach(sectionName => {
        const criteria = sections[sectionName];
        if (!criteria || !criteria.length) return;

        const sectionFails   = criteria.filter(c => c.status === 'fail').length;
        const sectionManuals = criteria.filter(c => c.status === 'manual').length;
        const sectionPasses  = criteria.filter(c => c.status === 'pass').length;
        const sectionIcon = SECTION_ICONS[sectionName] || '';

        html += `
        <details class="criteria-section" open>
            <summary class="criteria-section-header">
                <span class="cs-icon">${sectionIcon}</span>
                <span class="cs-name">${sectionName}</span>
                <span class="cs-counts">
                    ${sectionFails   > 0 ? `<span class="cs-count e">${sectionFails} fallos</span>`   : ''}
                    ${sectionManuals > 0 ? `<span class="cs-count m">${sectionManuals} manuales</span>` : ''}
                    ${sectionPasses  > 0 ? `<span class="cs-count p">${sectionPasses} OK</span>`     : ''}
                </span>
                <svg class="cs-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>
            </summary>
            <div class="criteria-list">
                ${criteria.map(c => buildCriterionHTML(c)).join('')}
            </div>
        </details>`;
    });

    return html;
}

function buildCriterionHTML(c) {
    const statusIcons = {
        fail:   `<svg class="crit-icon fail"   width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`,
        pass:   `<svg class="crit-icon pass"   width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><polyline points="9 12 11 14 15 10"/></svg>`,
        manual: `<svg class="crit-icon manual" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
    };

    const filteredIssues = (c.issues || []).filter(i => !shouldSkipIssue(i, c.label));
    const hasIssues = filteredIssues.length > 0;
    const issuesHTML = hasIssues ? filteredIssues.map(issue => buildIssueHTML(issue)).join('') : '';
    const effectiveStatus = (c.status === 'fail' && !hasIssues) ? 'pass' : c.status;

    return `
    <div class="criterion criterion-${effectiveStatus}">
        <div class="criterion-header${hasIssues ? ' criterion-header-clickable' : ''}" ${hasIssues ? 'onclick="toggleCriterion(this)"' : ''}>
            ${statusIcons[effectiveStatus] || ''}
            <span class="criterion-label">${esc(c.label)}</span>
            <span class="criterion-badges">
                ${c.manual && c.status === 'manual' ? '<span class="badge-manual">Verificar manualmente</span>' : ''}
                ${hasIssues ? `<span class="badge-count">${filteredIssues.length} problema${filteredIssues.length > 1 ? 's' : ''}</span>` : ''}
                ${hasIssues ? '<svg class="crit-chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>' : ''}
            </span>
        </div>
        ${hasIssues ? `<div class="criterion-issues" hidden>${issuesHTML}</div>` : ''}
    </div>`;
}

function toggleCriterion(header) {
    const issuesEl = header.nextElementSibling;
    if (!issuesEl) return;
    const hidden = issuesEl.hasAttribute('hidden');
    issuesEl.toggleAttribute('hidden', !hidden);
    header.querySelector('.crit-chevron')?.classList.toggle('open', hidden);
}

// ── CRUD ──────────────────────────────────────────────────
async function deleteAnalysis(id) {
    if (!confirm('¿Eliminar este análisis?')) return;
    await apiFetch(`/analysis/${id}`, { method: 'DELETE' });
    if (currentAnalysisId === id) btnNew.onclick();
    else loadHistory();
}

async function renameAnalysis(id, current) {
    const name = prompt('Nuevo nombre:', current);
    if (!name || name === current) return;
    await apiFetch(`/analysis/${id}?name=${encodeURIComponent(name)}`, { method: 'PUT' });
    loadHistory();
    if (currentAnalysisId === id) document.getElementById('currentName').textContent = name;
}

// ── Helpers ───────────────────────────────────────────────
function esc(str) {
    if (!str) return '';
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function urlPath(url) {
    try {
        const u = new URL(url);
        return u.pathname || '/';
    } catch { return url; }
}

function fmtDate(iso) {
    const d = new Date(iso);
    return d.toLocaleDateString('es', { day: '2-digit', month: 'short', year: 'numeric' });
}

function setStatBadge(el, value) {
    el.querySelector('.stat-num').textContent = value;
}

function statusLabel(s) {
    return { pending: 'Pendiente', processing: 'Analizando', completed: 'Completado', failed: 'Error' }[s] || s;
}

// ── Issue filter helpers ─────────────────────────────
function shouldSkipIssue(issue, criterionLabel) {
    // Skip smooth-scroll anchor links (domain/#text)
    const ctx = (issue.context || '').toLowerCase();
    const sel = (issue.selector || '').toLowerCase();
    if (/href=["'][^"']*\/#[a-z]/.test(ctx)) return true;

    if (!/encabezado|heading/i.test(criterionLabel)) return false;
    const combined = (sel + ' ' + ctx);
    return /\.e-n-menu|\.menu-item|\.nav-menu|nav-link|\.main-navigation|\.primary-menu|\.site-navigation|footer|\.site-footer|\.footer-widget|\.wp-menu/.test(combined);
}

function extractImageSrc(html) {
    if (!html) return null;
    const m = html.match(/\bsrc=["']([^"']+)["']/i);
    if (!m) return null;
    const src = m[1];
    if (src.startsWith('data:') || src.startsWith('blob:')) return null;
    return src;
}

function buildElementPreview(issue, pageUrl) {
    const html = issue.context || '';
    if (!html || html.length < 5) return '';

    const resources = issue.resources || [];
    let out = '';

    // Resource URLs from backend enrichment (fully resolved by Puppeteer)
    const imgResources = resources.filter(r => r.type === 'img' || r.type === 'video' || r.type === 'poster' || r.type === 'bg' || r.type === 'source');
    const linkResources = resources.filter(r => r.type === 'link' || r.type === 'iframe');
    const allRes = [...imgResources, ...linkResources];

    if (allRes.length > 0) {
        out += `<div class="issue-resource-urls">`;
        for (const r of allRes.slice(0, 8)) {
            const u = r.url || '';
            const isImg = r.type === 'img' || r.type === 'poster' || r.type === 'bg' || /\.(png|jpe?g|gif|webp|svg|avif|ico|bmp)/i.test(u);
            const typeIcon = {img:'\uD83D\uDDBC\uFE0F',video:'\uD83C\uDFA5',poster:'\uD83C\uDFA8',bg:'\uD83C\uDF04',link:'\uD83D\uDD17',iframe:'\uD83D\uDDA5\uFE0F',source:'\uD83C\uDFA7'}[r.type] || '\uD83D\uDD17';
            out += `<div class="issue-resource-url">`;
            if (isImg) {
                out += `<img src="${esc(u)}" alt="" class="issue-resource-thumb" loading="lazy" onerror="this.style.display='none'" />`;
            }
            out += `<span class="issue-resource-type">${typeIcon}</span>`;
            out += `<a href="${esc(u)}" target="_blank" rel="noopener" class="issue-resource-link" title="${esc(u)}">${esc(u.length > 90 ? u.slice(0, 87) + '\u2026' : u)}</a></div>`;
        }
        out += `</div>`;
    }

    return out;
}

// ── Platform & fix helpers ─────────────────────────────
const PLATFORM_LABELS = {
    elementor: { icon: '⚡', label: 'Elementor', color: '#e2a03f' },
    wordpress: { icon: '🟦', label: 'WordPress', color: '#3858e9' },
    html:      { icon: '🔷', label: 'HTML',      color: '#4da6ff' },
};

function detectPlatform(context, selector) {
    const c = ((context || '') + ' ' + (selector || '')).toLowerCase();
    if (/elementor-|e-n-|e-con-|e-flex-|eael-|jet-element|jem-|e-loop/.test(c)) return 'elementor';
    if (/wp-block-|woocommerce|wc-product|yoast|rankmath|et_pb_|wpforms/.test(c)) return 'wordpress';
    return 'html';
}

function extractVisibleText(html) {
    if (!html) return '';
    const t = html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
    return t.length > 55 ? t.slice(0, 52) + '\u2026' : t;
}

function selectorToReadablePath(selector) {
    if (!selector) return '';
    const MAP = [
        { re: /header|\.site-header|#header|masthead|\.elementor-location-header/,  label: '🏠 Cabecera' },
        { re: /footer|\.site-footer|#footer|\.elementor-location-footer/,           label: '📋 Pie de p\u00e1gina' },
        { re: /\.nav|navigation|#nav|\.menu|\.nav-menu|\.e-n-menu|mega-menu/,      label: '\ud83e\uddedMen\u00fa de navegaci\u00f3n' },
        { re: /main|#main|\.main-content|\.entry-content|\.post-content/,           label: '\ud83d\udcc4 Contenido principal' },
        { re: /sidebar|\.widget-area|#sidebar|\.elementor-location-sidebar/,        label: '\ud83d\udccc Barra lateral' },
        { re: /form|\.wpcf7|\.gf_form|\.wpforms|#contact/,                          label: '\ud83d\udcdd Formulario' },
        { re: /hero|\.hero|#hero|\.banner|\.e-n-carousel/,                          label: '\ud83d\uddbc\ufe0f Banner / Hero' },
        { re: /slider|carousel|swiper|\.owl|\.slick/,                               label: '\ud83c\udfa0 Slider' },
        { re: /section|\.elementor-section|\.e-con/,                                label: '\ud83d\udce6 Secci\u00f3n' },
        { re: /article|\.post|\.entry-/,                                             label: '\ud83d\udcf0 Art\u00edculo' },
    ];
    const lower = selector.toLowerCase();
    for (const { re, label } of MAP) { if (re.test(lower)) return label; }
    const parts = selector.split(/[\s>+~]+/);
    for (let i = parts.length - 1; i >= 0; i--) {
        const p = parts[i];
        const id  = p.match(/#([\w-]+)/)?.[1];
        const cls = p.match(/\.([\w-]+)/)?.[1];
        if (id  && id.length  > 2 && !/nth|child|type/i.test(id))  return '\ud83d\udccc #' + id;
        if (cls && cls.length > 3 && !/nth|child|type/i.test(cls)) return '\ud83d\udccc .' + cls;
    }
    return '';
}

function getAffectedUsers(code) {
    if (!code) return ['\ud83e\uddb6 Tecnolog\u00edas de asistencia'];
    if (/Guideline1_1/.test(code)) return ['\ud83d\udd0a Lectores de pantalla', '\ud83e\uddae Baja visi\u00f3n'];
    if (/Guideline1_2/.test(code)) return ['\ud83d\udd07 Usuarios sordos / baja audici\u00f3n'];
    if (/Guideline1_3/.test(code)) return ['\ud83d\udd0a Lectores de pantalla', '\u2328\ufe0f Navegaci\u00f3n por teclado'];
    if (/Guideline1_4/.test(code)) return ['\ud83d\udc41\ufe0f Baja visi\u00f3n', '\ud83c\udfa8 Daltonismo'];
    if (/Guideline2_1/.test(code)) return ['\u2328\ufe0f Usuarios sin rat\u00f3n', '\ud83e\uddb6 Tecnolog\u00edas de asistencia'];
    if (/Guideline2_4/.test(code)) return ['\u2328\ufe0f Navegaci\u00f3n por teclado', '\ud83d\udd0a Lectores de pantalla'];
    if (/Guideline3/.test(code))   return ['\ud83e\udde0 Discapacidad cognitiva', '\ud83d\udd0a Lectores de pantalla'];
    return ['\ud83e\uddb6 Tecnolog\u00edas de asistencia'];
}

function getDifficulty(code) {
    if (!code) return { label: 'Requiere dev', cls: 'diff-dev' };
    if (/Guideline1_1/.test(code))                   return { label: 'F\u00e1cil', cls: 'diff-easy' };
    if (/H25|dom-checker-lang|dom-checker-title/.test(code)) return { label: 'F\u00e1cil', cls: 'diff-easy' };
    if (/Guideline1_3|Guideline2_4|Guideline3_1/.test(code)) return { label: 'Medio', cls: 'diff-med' };
    if (/Guideline1_4|Guideline2_1|Guideline4/.test(code))   return { label: 'Requiere dev', cls: 'diff-dev' };
    return { label: 'Medio', cls: 'diff-med' };
}

const FIX_DB = [
    {
        match: /Guideline1_1/,
        title: 'Texto alternativo (alt)',
        steps: {
            html:      ['A\u00f1ade alt="descripci\u00f3n breve" a la etiqueta <img>', 'Si es decorativa usa alt=""'],
            wordpress: ['Biblioteca de medios \u2192 clic en imagen \u2192 campo "Texto alternativo"', 'Bloque Imagen \u2192 panel derecho \u2192 campo "Texto alternativo"'],
            elementor: ['Widget Imagen \u2192 panel izquierdo \u2192 campo "Alt. Text"', 'Imagen dentro de enlace: Avanzado \u2192 "Atributos personalizados" \u2192 key: alt, value: tu descripci\u00f3n'],
        },
    },
    {
        match: /semantic-heading|H42|fake.?heading|simula.*encabezado|usa etiquetas.*h[1-6]|no usa.*h[1-6]/i,
        title: 'Encabezado real (H1\u2013H6)',
        steps: {
            html:      ['Reemplaza el <div> o <span> por <h2>, <h3>\u2026 seg\u00fan jerarqu\u00eda del contenido'],
            wordpress: ['Bloque texto \u2192 clic en "P\u00e1rrafo" en la barra flotante \u2192 "Encabezado" \u2192 elige H2, H3\u2026'],
            elementor: ['Usa el widget "Titular" (Heading) en vez de widget Texto o HTML personalizado', 'Widget Titular \u2192 panel izquierdo \u2192 campo "HTML Tag" \u2192 selecciona H2, H3\u2026'],
        },
    },
    {
        match: /Guideline1_3_1/,
        title: 'Estructura sem\u00e1ntica HTML',
        steps: {
            html:      ['Usa <nav>, <main>, <article>, <section>, <aside> en vez de <div> gen\u00e9ricos'],
            wordpress: ['Evita bloques "HTML personalizado" para contenido con sem\u00e1ntica propia'],
            elementor: ['Widget \u2192 pesta\u00f1a "Avanzado" \u2192 campo "HTML Tag" \u2192 elige el elemento sem\u00e1ntico correcto', 'Usa nav para men\u00fas, section para secciones, article para posts'],
        },
    },
    {
        match: /Guideline1_4_3|contraste|contrast/i,
        title: 'Contraste de texto',
        steps: {
            html:      ['Comprueba el ratio en webaim.org/resources/contrastchecker', 'Texto normal: ratio \u2265 4.5:1 \u2014 texto grande (18px+): ratio \u2265 3:1'],
            wordpress: ['Personalizar \u2192 Colores \u2192 ajusta color de texto y fondo', 'Bloque \u2192 columna derecha \u2192 "Color" \u2192 usa una combinaci\u00f3n con suficiente contraste'],
            elementor: ['Widget \u2192 pesta\u00f1a "Estilo" \u2192 "Color de tipograf\u00eda" \u2192 elige tono m\u00e1s oscuro/claro', 'Recomendado: texto #1a1a1a sobre fondo blanco, o #f0f0f0 sobre fondo oscuro'],
        },
    },
    {
        match: /Guideline2_4_2|H25|t\u00edtulo de p\u00e1gina/i,
        title: 'T\u00edtulo de p\u00e1gina (<title>)',
        steps: {
            html:      ['A\u00f1ade <title>Nombre descriptivo</title> en el <head> de cada p\u00e1gina'],
            wordpress: ['Plugin Yoast SEO o RankMath \u2192 edita la p\u00e1gina \u2192 pesta\u00f1a "SEO" \u2192 campo "T\u00edtulo SEO"'],
            elementor: ['El t\u00edtulo lo gestiona WordPress, no Elementor directamente', 'Instala Yoast SEO (gratis) \u2192 cada p\u00e1gina \u2192 pesta\u00f1a "SEO" \u2192 campo "T\u00edtulo SEO"'],
        },
    },
    {
        match: /form.*field.*label|This form field|etiqueta.*campo|campo.*sin etiqueta/i,
        title: 'Etiqueta de campo de formulario',
        steps: {
            html:      ['Asocia cada <input> con un <label for="id-del-campo">', 'O usa aria-label="Nombre del campo" en el propio input'],
            wordpress: ['Contact Form 7: aseg\u00farate de que cada campo tiene texto de etiqueta visible', 'WPForms / Gravity Forms: clic en el campo \u2192 panel derecho \u2192 campo "Etiqueta"'],
            elementor: ['Widget Formulario \u2192 clic en el campo \u2192 panel izquierdo \u2192 "Etiqueta" \u2192 escribe el texto', '"Mostrar etiqueta" debe estar activado'],
        },
    },
    {
        match: /Guideline2_1|keyboard|focus|teclado/i,
        title: 'Accesibilidad por teclado',
        steps: {
            html:      ['Verifica con Tab que todos los elementos interactivos reciben foco', 'No uses tabindex=-1 ni CSS outline:none salvo excepciones justificadas'],
            wordpress: ['Evita plugins de slider/galer\u00eda que bloqueen el foco del teclado', 'Plugin "WP Accessibility" ayuda a detectar problemas de foco'],
            elementor: ['Actualiza Elementor Pro (las versiones recientes mejoran el foco en Tabs y Acorde\u00f3n)', 'Widget \u2192 "Avanzado" \u2192 verifica que no haya tabindex=-1 en atributos personalizados'],
        },
    },
];

function getFixInstructions(code, msgEs, platform) {
    const combined = (code || '') + ' ' + (msgEs || '');
    for (const entry of FIX_DB) {
        if (entry.match.test(combined)) {
            return { title: entry.title, steps: entry.steps[platform] || entry.steps.html };
        }
    }
    return null;
}

function contextToElementDesc(context, selector) {
    const elements = {
        img: { icon: '🖼️', label: 'Imagen' },
        a: { icon: '🔗', label: 'Enlace' },
        button: { icon: '🔘', label: 'Botón' },
        input: { icon: '✏️', label: 'Campo de entrada' },
        select: { icon: '📋', label: 'Lista desplegable' },
        textarea: { icon: '📝', label: 'Área de texto' },
        h1: { icon: '🔤', label: 'Título H1' }, h2: { icon: '🔤', label: 'Título H2' },
        h3: { icon: '🔤', label: 'Título H3' }, h4: { icon: '🔤', label: 'Título H4' },
        h5: { icon: '🔤', label: 'Título H5' }, h6: { icon: '🔤', label: 'Título H6' },
        iframe: { icon: '🖥️', label: 'Marco incrustado' },
        video: { icon: '🎥', label: 'Video' },
        audio: { icon: '🔊', label: 'Audio' },
        svg: { icon: '🎨', label: 'Ícono SVG' },
        table: { icon: '📊', label: 'Tabla' },
        form: { icon: '📝', label: 'Formulario' },
        label: { icon: '🏷️', label: 'Etiqueta de campo' },
        nav: { icon: '🧭', label: 'Navegación' },
        div: { icon: '📦', label: 'Contenedor' },
        span: { icon: '🔲', label: 'Texto' },
    };
    if (context) {
        const m = context.match(/^<(\w+)/);
        if (m) {
            const tag = m[1].toLowerCase();
            return elements[tag] || { icon: '🔲', label: `<${tag}>` };
        }
    }
    if (selector) {
        const parts = selector.split(/[\s>+~]+/);
        const last = parts[parts.length - 1];
        const tag = (last.match(/^[a-z]+/i)?.[0] || '').toLowerCase();
        if (tag) return elements[tag] || { icon: '🔲', label: `<${tag}>` };
    }
    return { icon: '🔲', label: 'Elemento' };
}

function escHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function buildIssueHTML(issue) {
    const isResolved = issue.resolved || false;
    const issueIdx = issue._idx;
    const code     = (issue.code || '').split('.').slice(0, 4).join('.');
    const msgEs    = translateIssueMessage(issue.message, issue.runner);
    const platform = detectPlatform(issue.context, issue.selector);
    const pInfo    = PLATFORM_LABELS[platform] || PLATFORM_LABELS.html;
    const elemInfo = contextToElementDesc(issue.context, issue.selector);
    const readPath = selectorToReadablePath(issue.selector);
    const visText  = issue.textContent || extractVisibleText(issue.context);
    const affected = getAffectedUsers(code);
    const diff     = getDifficulty(code);
    const elPreview = buildElementPreview(issue, _renderPageUrl);
    const sel      = issue.selector || '';

    return `<div class="crit-issue${isResolved ? ' crit-issue-resolved' : ''}">
        <div class="issue-meta-row">
            <span class="issue-platform-badge" style="background:${pInfo.color}22;color:${pInfo.color};border-color:${pInfo.color}44">${pInfo.icon} ${pInfo.label}</span>
            <span class="issue-badge issue-elem">${elemInfo.icon} ${esc(elemInfo.label)}</span>
            ${readPath ? `<span class="issue-badge issue-section">${esc(readPath)}</span>` : ''}
            <span class="issue-diff-badge ${diff.cls}">${diff.label}</span>
        </div>
        ${elPreview}
        ${visText ? `<div class="issue-visible-text">\uD83D\uDD0E Texto visible: \u201C<em>${esc(visText)}</em>\u201D</div>` : ''}
        <div class="crit-issue-msg">${esc(msgEs)}</div>
        ${affected.length ? `<div class="issue-affects"><span class="issue-affects-label">Afecta a:</span>${affected.map(u => `<span class="issue-affects-item">${esc(u)}</span>`).join('')}</div>` : ''}
        ${issue.fix_advice ? `
        <details class="issue-fix-ai-details">
            <summary class="issue-fix-ai-btn">\uD83E\uDD16 \u00BFC\u00F3mo lo arreglo?</summary>
            <div class="issue-fix-ai-result">
                <div class="fix-ai-body"><div class="fix-ai-content">${simpleMarkdown(issue.fix_advice)}</div></div>
            </div>
        </details>` : `
        <button class="issue-fix-ai-btn" onclick="requestFixAdvice(this)"
            data-url="${esc(_renderPageUrl)}"
            data-code="${esc(code)}"
            data-msg="${esc((issue.message || '').slice(0,500))}"
            data-ctx="${esc((issue.context || '').slice(0,2000))}"
            data-sel="${esc(sel)}">
            \uD83E\uDD16 \u00BFC\u00F3mo lo arreglo?
        </button>
        <div class="issue-fix-ai-result" hidden></div>`}
        ${issue.context ? `
        <details class="issue-ctx">
            <summary class="issue-ctx-toggle">Ver c\u00F3digo HTML del elemento</summary>
            <pre class="issue-ctx-code">${escHtml(issue.context)}</pre>
        </details>` : ''}
        <div class="crit-issue-meta">
            ${code ? `<span class="issue-tag">${esc(code)}</span>` : ''}
            ${sel ? `<button class="issue-copy-sel" onclick="copySelector(this)" data-sel="${esc(sel)}">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                Copiar selector
            </button>` : ''}
            <button class="issue-resolve-btn${isResolved ? ' resolved' : ''}" onclick="toggleIssueResolved(this)"
                data-report="${_renderReportId}" data-idx="${issueIdx != null ? issueIdx : ''}">
                ${isResolved ? '\u2705 Superado' : '\u2B1C Marcar superado'}
            </button>
        </div>
    </div>`;
}

function copySelector(btn) {
    const sel = btn.dataset.sel || '';
    if (!sel) return;
    navigator.clipboard.writeText(sel).then(() => {
        const orig = btn.innerHTML;
        btn.textContent = '\u2713 Copiado';
        btn.style.color = 'var(--cyan)';
        setTimeout(() => { btn.innerHTML = orig; btn.style.color = ''; }, 1800);
    }).catch(() => {});
}

async function toggleIssueResolved(btn) {
    const reportId = btn.dataset.report;
    const idx = btn.dataset.idx;
    if (!reportId || idx === '') return;
    const wasResolved = btn.classList.contains('resolved');
    const nowResolved = !wasResolved;

    btn.disabled = true;
    try {
        const params = new URLSearchParams({
            report_id: reportId,
            issue_index: idx,
            resolved: nowResolved,
        });
        const res = await apiFetch(`/analysis/${currentAnalysisId}/issue?${params}`, { method: 'PATCH' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        // Update button
        btn.classList.toggle('resolved', nowResolved);
        btn.innerHTML = nowResolved ? '\u2705 Superado' : '\u2B1C Marcar superado';

        // Update card visual
        const card = btn.closest('.crit-issue');
        if (card) card.classList.toggle('crit-issue-resolved', nowResolved);

        // Update top-bar stat badges
        setStatBadge(statErrors, data.errors);
        setStatBadge(statWarnings, data.warnings);
        setStatBadge(statNotices, data.notices);

        // Update criterion-level: if all issues resolved, mark criterion as pass
        const criterion = btn.closest('.criterion');
        if (criterion) {
            const allIssues = criterion.querySelectorAll('.crit-issue');
            const allResolved = [...allIssues].every(c => c.classList.contains('crit-issue-resolved'));
            const someResolved = [...allIssues].some(c => c.classList.contains('crit-issue-resolved'));
            if (allResolved) {
                criterion.className = criterion.className.replace(/criterion-(fail|manual)/, 'criterion-pass');
                const icon = criterion.querySelector('.crit-icon');
                if (icon) {
                    icon.outerHTML = `<svg class="crit-icon pass" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><polyline points="9 12 11 14 15 10"/></svg>`;
                }
            } else if (!allResolved && criterion.className.includes('criterion-pass') && someResolved) {
                criterion.className = criterion.className.replace(/criterion-pass/, 'criterion-fail');
                const icon = criterion.querySelector('.crit-icon');
                if (icon) {
                    icon.outerHTML = `<svg class="crit-icon fail" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`;
                }
            }
        }

        // Update panel summary counts (criteria-level)
        const panel = btn.closest('.tab-panel');
        if (panel) {
            const allCriteria = panel.querySelectorAll('.criterion');
            let failC = 0, manualC = 0, passC = 0;
            allCriteria.forEach(c => {
                if (c.classList.contains('criterion-fail')) failC++;
                else if (c.classList.contains('criterion-manual')) manualC++;
                else if (c.classList.contains('criterion-pass')) passC++;
            });
            const summary = panel.querySelector('.panel-summary');
            if (summary) {
                const stats = summary.querySelectorAll('.panel-stat');
                stats.forEach(s => {
                    if (s.classList.contains('e')) s.innerHTML = `<strong>${failC}</strong> fallos automáticos`;
                    if (s.classList.contains('m')) s.innerHTML = `<strong>${manualC}</strong> verificación manual`;
                    if (s.classList.contains('p')) s.innerHTML = `<strong>${passC}</strong> superados`;
                });
            }

            // Update section header counts
            panel.querySelectorAll('.criteria-section').forEach(section => {
                const sectionCriteria = section.querySelectorAll('.criterion');
                let sf = 0, sm = 0, sp = 0;
                sectionCriteria.forEach(c => {
                    if (c.classList.contains('criterion-fail')) sf++;
                    else if (c.classList.contains('criterion-manual')) sm++;
                    else if (c.classList.contains('criterion-pass')) sp++;
                });
                const countsEl = section.querySelector('.cs-counts');
                if (countsEl) {
                    countsEl.innerHTML =
                        (sf > 0 ? `<span class="cs-count e">${sf} fallos</span>` : '') +
                        (sm > 0 ? `<span class="cs-count m">${sm} manuales</span>` : '') +
                        (sp > 0 ? `<span class="cs-count p">${sp} OK</span>` : '');
                }
            });
        }
    } catch (e) {
        console.warn('toggleIssueResolved:', e.message);
    } finally {
        btn.disabled = false;
    }
}

async function requestFixAdvice(btn) {
    const card   = btn.closest('.crit-issue');
    const result = card.querySelector('.issue-fix-ai-result');

    btn.disabled = true;
    btn.classList.add('loading');
    result.hidden   = false;
    result.innerHTML = '<div class="fix-ai-loading"><span class="fix-ai-spinner"></span> Detectando WordPress y consultando Gemini\u2026</div>';

    try {
        const params = new URLSearchParams({
            site_url:       btn.dataset.url  || currentAnalysisUrl || '',
            issue_code:     btn.dataset.code || '',
            issue_message:  btn.dataset.msg  || '',
            issue_context:  btn.dataset.ctx  || '',
            issue_selector: btn.dataset.sel  || '',
            analysis_id:    currentAnalysisId || 0,
        });

        const res = await apiFetch(`/fix-advice?${params}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        const wpLine = data.wp?.theme
            ? `<div class="fix-ai-wp-info">\uD83D\uDD0D Detectado: <strong>${esc(
                typeof data.wp.theme === 'object' ? (data.wp.theme.slug || 'tema') : String(data.wp.theme)
              )}</strong> \u00B7 ${data.wp.plugins_count || 0} plugin(s)</div>`
            : '';

        result.innerHTML = `<div class="fix-ai-body">${wpLine}<div class="fix-ai-content">${simpleMarkdown(data.advice || '')}</div></div>`;

        btn.textContent = '\u2713 Ver instrucciones IA';
        btn.classList.remove('loading');
        btn.disabled = false;
        btn.onclick = () => { result.hidden = !result.hidden; };

    } catch(e) {
        result.innerHTML = `<div class="fix-ai-error">\u274C Error: ${esc(String(e))}. Revisa los logs y GEMINI_API_KEY.</div>`;
        btn.disabled = false;
        btn.classList.remove('loading');
    }
}

function simpleMarkdown(text) {
    if (!text) return '';
    let s = text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    s = s.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/\*([^*\n]+)\*/g, '<em>$1</em>');
    s = s.replace(/`([^`\n]+)`/g, '<code>$1</code>');
    s = s.replace(/^#{1,3} (.+)$/gm, '<strong>$1</strong>');
    s = s.replace(/^[-\u2022\u2023\u25B8] (.+)$/gm, '<li>$1</li>');
    s = s.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');
    s = s.replace(/((?:<li>[\s\S]*?<\/li>\n?)+)/g, '<ul class="fix-ai-list">$1</ul>');
    s = s.replace(/\n{2,}/g, '<br><br>');
    s = s.replace(/\n/g, '<br>');
    return s;
}

// \u2500\u2500 Global issues aggregation ────────────────────────────
function buildGlobalIssuesData(pages) {
    const map = new Map();
    for (const page of pages) {
        for (const criteria of Object.values(page.sections || {})) {
            for (const criterion of criteria) {
                for (const issue of (criterion.issues || [])) {
                    const key = issue.code || (issue.message || '').substring(0, 80);
                    if (!map.has(key)) {
                        map.set(key, {
                            code: issue.code || '',
                            message: issue.message || '',
                            translatedMsg: translateIssueMessage(issue.message, issue.runner),
                            type: issue.type || 'error',
                            runner: issue.runner || '',
                            pagesMap: new Map(),
                            totalCount: 0,
                        });
                    }
                    const entry = map.get(key);
                    entry.totalCount++;
                    entry.pagesMap.set(page.url, (entry.pagesMap.get(page.url) || 0) + 1);
                }
            }
        }
    }
    const typeOrder = { error: 0, warning: 1, notice: 2 };
    return Array.from(map.values())
        .map(item => ({
            ...item,
            pagesCount: item.pagesMap.size,
            pages: Array.from(item.pagesMap.entries())
                .map(([url, count]) => {
                    const p = pages.find(pg => pg.url === url);
                    return { url, count, title: p?.page_title || titleFromPath(urlPath(url)) };
                })
                .sort((a, b) => b.count - a.count),
        }))
        .filter(item => item.pagesCount >= (pages.length > 1 ? 2 : 1))
        .sort((a, b) => {
            const t = (typeOrder[a.type] || 0) - (typeOrder[b.type] || 0);
            if (t !== 0) return t;
            const p = b.pagesCount - a.pagesCount;
            if (p !== 0) return p;
            return b.totalCount - a.totalCount;
        });
}

function buildGlobalIssuesPanelHTML(pages, globalIssues) {
    const totalPages = pages.length;
    const typeLabel = { error: 'Error', warning: 'Advertencia', notice: 'Aviso' };
    const typeClass = { error: 'e', warning: 'w', notice: 'n' };

    if (globalIssues.length === 0) {
        return `<div class="global-empty"><div class="global-empty-icon">✅</div><p>No se encontraron problemas repetidos en múltiples páginas.</p></div>`;
    }

    let html = `
        <div class="global-panel-header">
            <div class="global-panel-title">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                Patrones comunes en todo el sitio
            </div>
            <p class="global-panel-desc">Estos problemas se repiten en varias páginas. Corregirlos de forma centralizada resuelve múltiples páginas a la vez.</p>
            <div class="global-panel-stats">
                <span class="gstat"><strong>${totalPages}</strong> páginas analizadas</span>
                <span class="gstat e"><strong>${globalIssues.filter(i => i.type === 'error').length}</strong> tipos de error repetidos</span>
                <span class="gstat"><strong>${globalIssues.length}</strong> problemas comunes</span>
            </div>
        </div>
        <div class="global-issues-list">`;

    for (const item of globalIssues) {
        const tc = typeClass[item.type] || 'n';
        const tl = typeLabel[item.type] || 'Aviso';
        const codeShort = item.code.split('.').slice(0, 4).join('.');
        html += `
        <div class="global-issue-card global-${item.type}">
            <div class="global-issue-top">
                <span class="global-type-badge ${tc}">${tl}</span>
                <div class="global-issue-msg">${esc(item.translatedMsg || item.message)}</div>
            </div>
            <div class="global-issue-stats">
                <span class="gstat e"><strong>${item.pagesCount}</strong> página${item.pagesCount > 1 ? 's' : ''} afectada${item.pagesCount > 1 ? 's' : ''}</span>
                <span class="gstat"><strong>${item.totalCount}</strong> ocurrencia${item.totalCount > 1 ? 's' : ''}</span>
                ${codeShort ? `<span class="issue-tag">${esc(codeShort)}</span>` : ''}
            </div>
            <details class="global-pages-details">
                <summary>Ver páginas afectadas (${item.pagesCount})</summary>
                <ul class="global-pages-list">
                    ${item.pages.map(p => `
                    <li class="global-page-item">
                        <a href="${esc(p.url)}" target="_blank" rel="noopener" class="global-page-link">${esc(p.title)}</a>
                        <span class="global-page-count">${p.count} occ.</span>
                    </li>`).join('')}
                </ul>
            </details>
        </div>`;
    }
    html += `</div>`;
    return html;
}

// ── Traducción de mensajes pa11y (inglés → español) ────
const PA11Y_TRANSLATIONS = [

    // ── Principio 1.1 – Texto alternativo ───────────────────────────────────
    [/Img element is the only content of the link, but is missing alt text/i,
     () => 'La imagen es el único contenido del enlace pero falta el atributo alt. El alt debe describir el propósito del enlace.'],
    [/Img element with empty alt text must have absent or empty title attribute/i,
     () => 'Una imagen con alt vacío (decorativa) no debe tener atributo title, o debe estar vacío.'],
    [/Img element is marked so that it is ignored by Assistive Technology/i,
     () => 'Esta imagen está marcada para ser ignorada por tecnologías de asistencia.'],
    [/Img element missing an alt attribute/i,
     () => 'La imagen no tiene atributo alt. Añade un texto alternativo breve y descriptivo.'],
    [/Ensure that the img element.?s alt text serves the same purpose/i,
     () => 'Comprueba que el texto alternativo de la imagen transmite la misma información que la imagen.'],
    [/Image submit button missing an alt attribute/i,
     () => 'El botón de envío de imagen no tiene atributo alt. Describe la función del botón.'],
    [/Ensure that the image submit button.?s alt text identifies the purpose/i,
     () => 'Comprueba que el alt del botón de imagen describe su propósito.'],
    [/Area element in an image map missing an alt attribute/i,
     () => 'El elemento <area> del mapa de imagen no tiene atributo alt. Describe la función de esa zona.'],
    [/image cannot be fully described in a short text alternative/i,
     () => 'Si esta imagen no puede describirse con un alt breve, proporciona también una descripción larga en el cuerpo o mediante un enlace.'],
    [/Img element inside a link must not use alt text that duplicates the text content of the link/i,
     () => 'El alt de la imagen dentro del enlace no debe duplicar el texto visible del enlace.'],
    [/Img element inside a link has empty or missing alt text when a link beside it contains link text/i,
     () => 'La imagen dentro del enlace tiene alt vacío o ausente, pero hay un enlace contiguo con texto. Considera combinar ambos enlaces.'],
    [/Img element inside a link must not use alt text that duplicates the content of a text link beside it/i,
     () => 'El alt de la imagen duplica el texto del enlace contiguo. Usa alt vacío para la imagen o combina los enlaces.'],
    [/Object elements must contain a text alternative/i,
     () => 'Los elementos <object> deben incluir un texto alternativo cuando no hay otras alternativas disponibles.'],
    [/Check that short.*long.*text alternatives are available for non-text content/i,
     () => 'Comprueba que existen alternativas textuales (corta y, si procede, larga) para este contenido no textual.'],

    // ── Principio 1.2 – Medios temporizados ─────────────────────────────────
    [/contains pre-recorded audio only.*check that an alternative text version is available/i,
     () => 'Si este objeto contiene solo audio pregrabado, verifica que existe una versión alternativa en texto.'],
    [/contains pre-recorded video only.*check that an alternative text version/i,
     () => 'Si este objeto contiene solo vídeo pregrabado, verifica que existe una alternativa en texto o una pista de audio equivalente.'],
    [/contains pre-recorded synchronised media.*check that captions are provided/i,
     () => 'Si este objeto contiene medios sincronizados pregrabados, verifica que se proporcionan subtítulos para el audio.'],
    [/check that an audio description.*alternative text version.*is provided/i,
     () => 'Comprueba que se proporciona audiodescripción o una versión alternativa en texto para el vídeo pregrabado.'],
    [/check that captions are provided for live audio/i,
     () => 'Comprueba que se proporcionan subtítulos para el audio en directo de este objeto.'],
    [/check that an audio description is provided for its video content/i,
     () => 'Comprueba que se proporciona audiodescripción para el contenido de vídeo pregrabado.'],
    [/check that a sign language interpretation is provided/i,
     () => 'Comprueba que se proporciona interpretación en lengua de signos para el audio de este medio sincronizado.'],
    [/check that an extended audio description is provided/i,
     () => 'Comprueba que se proporciona audiodescripción extendida para este medio sincronizado cuando las pausas no son suficientes.'],
    [/check that an alternative text version of the content is provided/i,
     () => 'Comprueba que existe una versión alternativa en texto para este contenido de medios pregrabado.'],
    [/check that an alternative text version is provided.*live audio/i,
     () => 'Comprueba que existe una versión alternativa en texto para este contenido de audio en directo.'],

    // ── Principio 1.3 – Adaptable ────────────────────────────────────────────
    [/element.?s role is .presentation. but contains child elements with semantic meaning/i,
     () => 'El rol "presentation" de este elemento entra en conflicto con elementos hijos que tienen significado semántico.'],
    [/This label.?s .for. attribute contains an ID that does not exist in the document fragment/i,
     () => 'El atributo "for" de esta etiqueta apunta a un ID que no existe en el fragmento del documento.'],
    [/This label.?s .for. attribute contains an ID that does not exist/i,
     () => 'El atributo "for" de esta etiqueta apunta a un ID que no existe en el documento.'],
    [/This label.?s .for. attribute contains an ID for an element that is not a form control/i,
     () => 'El atributo "for" de esta etiqueta apunta a un elemento que no es un control de formulario.'],
    [/This form control has a .title. attribute that is empty or contains only spaces/i,
     () => 'Este control de formulario tiene un atributo title vacío; será ignorado para etiquetar el campo.'],
    [/This form control has an .aria-label. attribute that is empty or contains only spaces/i,
     () => 'Este control de formulario tiene un atributo aria-label vacío; será ignorado para etiquetar el campo.'],
    [/aria-labelledby attribute.*ID.*does not exist/i,
     () => 'El atributo aria-labelledby referencia un ID que no existe en el documento y será ignorado.'],
    [/This hidden form field is labelled in some way/i,
     () => 'Este campo oculto tiene etiqueta, lo cual no es necesario para campos de tipo hidden.'],
    [/This form field is intended to be hidden.*but is also labelled/i,
     () => 'Este campo está marcado como hidden pero también tiene etiqueta. No es necesario etiquetar campos ocultos.'],
    [/This form field should be labelled in some way/i,
     () => 'Este campo de formulario no tiene etiqueta. Usa <label for="...">, title, aria-label o aria-labelledby.'],
    [/Presentational markup used that has become obsolete in HTML5/i,
     () => 'Se usa marcado presentacional obsoleto en HTML5. Utiliza CSS en su lugar.'],
    [/Semantic markup should be used to mark emphasised or special text/i,
     () => 'Usa marcado semántico (<em>, <strong>, etc.) para enfatizar texto, no atributos de presentación.'],
    [/Heading markup should be used if this content is intended as a heading/i,
     () => 'Si este contenido es un encabezado, usa la etiqueta de encabezado apropiada (<h1>–<h6>).'],
    [/Table cell has an invalid scope attribute/i,
     () => 'La celda de tabla tiene un atributo scope no válido. Los valores correctos son: row, col, rowgroup o colgroup.'],
    [/Scope attributes on td elements that act as headings.*are obsolete in HTML5/i,
     () => 'El atributo scope en celdas <td> que actúan como encabezados es obsoleto en HTML5. Usa <th>.'],
    [/Scope attributes on th elements are ambiguous in a table with multiple levels/i,
     () => 'El atributo scope en tablas con múltiples niveles de encabezados es ambiguo. Usa el atributo headers en las celdas <td>.'],
    [/Incorrect headers attribute on this td element/i,
     () => 'El atributo headers de esta celda <td> es incorrecto. Verifica que referencia los IDs correctos de los encabezados.'],
    [/table has multiple levels of th elements, you must use the headers attribute/i,
     () => 'Esta tabla tiene múltiples niveles de encabezados. Debes usar el atributo headers en las celdas <td>.'],
    [/Not all th elements in this table contain an id attribute/i,
     () => 'No todos los elementos <th> tienen atributo id. Los encabezados necesitan id para ser referenciados por headers.'],
    [/Not all td elements in this table contain a headers attribute/i,
     () => 'No todas las celdas <td> tienen atributo headers. Cada celda debe listar los IDs de sus encabezados asociados.'],
    [/relationship between td elements and their associated th elements is not defined/i,
     () => 'La relación entre celdas <td> y sus encabezados <th> no está definida. Usa scope en <th> o headers en <td>.'],
    [/Not all th elements in this table have a scope attribute/i,
     () => 'No todos los elementos <th> tienen atributo scope. Añade scope para indicar su asociación con las celdas.'],
    [/layout table.*contains a summary attribute/i,
     () => 'Esta tabla de maquetación no debe tener atributo summary, o debe estar vacío.'],
    [/summary attribute and a caption element are present, the summary should not duplicate/i,
     () => 'El atributo summary y el elemento <caption> no deben contener el mismo texto.'],
    [/If this table is a data table, check that the summary attribute describes/i,
     () => 'Si esta tabla contiene datos, comprueba que el atributo summary describe su organización o cómo usarla.'],
    [/If this table is a data table, consider using the summary attribute/i,
     () => 'Si esta tabla contiene datos, considera usar el atributo summary para dar una descripción general.'],
    [/layout table.*contains a caption element/i,
     () => 'Esta tabla de maquetación no debe contener un elemento <caption>.'],
    [/If this table is a data table, check that the caption element accurately describes/i,
     () => 'Si esta tabla contiene datos, comprueba que el elemento <caption> la describe con precisión.'],
    [/If this table is a data table, consider using a caption element/i,
     () => 'Si esta tabla contiene datos, considera usar <caption> para identificarla.'],
    [/Fieldset does not contain a legend element/i,
     () => 'El elemento <fieldset> no contiene un elemento <legend>. Añade un <legend> que describa el grupo de campos.'],
    [/selection list contains groups of related options.*grouped with optgroup/i,
     () => 'Si esta lista de selección contiene grupos de opciones relacionadas, agrúpalas con <optgroup>.'],
    [/radio buttons or check boxes require a further group-level description.*fieldset/i,
     () => 'Si este grupo de radio buttons o checkboxes necesita una descripción de grupo, envuélvelo en un <fieldset> con <legend>.'],
    [/simulating an unordered list using plain text/i,
     () => 'Este contenido parece simular una lista no ordenada con texto plano. Usa <ul> y <li> para una estructura correcta.'],
    [/simulating an ordered list using plain text/i,
     () => 'Este contenido parece simular una lista ordenada con texto plano. Usa <ol> y <li> para una estructura correcta.'],
    [/heading structure is not logically nested.*primary document heading.*should be an h1/i,
     (m) => 'La estructura de encabezados no está bien anidada. Este encabezado parece el principal del documento y debería ser <h1>.'],
    [/heading structure is not logically nested.*should be an h(\d+) to be properly nested/i,
     (m) => `La estructura de encabezados no está bien anidada. Este encabezado debería ser <h${m[1]}> para seguir la jerarquía correcta.`],
    [/heading structure is not logically nested/i,
     () => 'La estructura de encabezados no está anidada de forma lógica (ej. H1 → H2 → H3).'],
    [/Heading tag found with no content/i,
     () => 'Se encontró una etiqueta de encabezado vacía. El texto que no sea encabezado no debe usar etiquetas <h1>–<h6>.'],
    [/navigation section.*recommended.*marked up as a list/i,
     () => 'Si este elemento contiene una sección de navegación, se recomienda marcarlo como lista.'],
    [/appears to be a layout table.*meant to.*be a data table.*ensure header cells/i,
     () => 'Esta tabla parece de maquetación. Si en realidad es de datos, asegúrate de identificar las celdas de encabezado con <th>.'],
    [/appears to be a data table.*meant to.*be a layout table.*ensure there are no th/i,
     () => 'Esta tabla parece de datos. Si en realidad es de maquetación, elimina los elementos <th>, summary y caption.'],
    [/content is ordered in a meaningful sequence when linearised/i,
     () => 'Comprueba que el contenido mantiene un orden con sentido cuando se linealiza (por ejemplo, sin hojas de estilo).'],
    [/do not rely on sensory characteristics alone.*shape, size or location/i,
     () => 'No uses solo características sensoriales (forma, tamaño, posición) para describir elementos. Añade texto complementario.'],

    // ── Principio 1.4 – Distinguible ─────────────────────────────────────────
    [/information conveyed using colour alone/i,
     () => 'Comprueba que la información transmitida solo mediante color también está disponible en texto u otras señales visuales.'],
    [/audio.*plays automatically.*longer than 3 seconds/i,
     () => 'Si este audio se reproduce automáticamente más de 3 segundos, debe existir la opción de pausarlo, detenerlo o silenciarlo.'],
    [/has an inherited foreground colour to complement.*inline background/i,
     () => 'Comprueba que este elemento tiene un color de texto heredado que complemente el color o imagen de fondo inline.'],
    [/has an inherited background colour.*to complement.*inline foreground/i,
     () => 'Comprueba que este elemento tiene un color de fondo heredado que complemente el color de texto inline.'],
    [/absolutely positioned and the background color can not be determined.*at least ([\d.]+):1/i,
     (m) => `Este elemento está posicionado de forma absoluta y no se puede determinar el color de fondo. Asegura un contraste mínimo de ${m[1]}:1.`],
    [/text is placed on a background image.*at least ([\d.]+):1/i,
     (m) => `El texto está sobre una imagen de fondo. Asegura un contraste mínimo de ${m[1]}:1 entre el texto y todas las partes de la imagen.`],
    [/text or background contains transparency.*at least ([\d.]+):1/i,
     (m) => `El texto o el fondo contiene transparencia. Asegura un contraste mínimo de ${m[1]}:1.`],
    [/insufficient contrast.*at least ([\d.]+):1.*contrast ratio of ([\d.]+):1.*change text colou?r to (#[\w]+)/i,
     (m) => `Contraste insuficiente: se requiere ${m[1]}:1 mínimo, pero hay ${m[2]}:1. Recomendación: cambia el color del texto a ${m[3]}.`],
    [/insufficient contrast.*at least ([\d.]+):1.*contrast ratio of ([\d.]+):1.*change background to (#[\w]+)/i,
     (m) => `Contraste insuficiente: se requiere ${m[1]}:1 mínimo, pero hay ${m[2]}:1. Recomendación: cambia el fondo a ${m[3]}.`],
    [/insufficient contrast.*at least ([\d.]+):1.*contrast ratio of ([\d.]+):1/i,
     (m) => `Contraste insuficiente: se requiere ${m[1]}:1 mínimo, pero hay ${m[2]}:1.`],
    [/text can be resized without assistive technology up to 200 percent without loss/i,
     () => 'Comprueba que el texto puede redimensionarse hasta el 200 % sin pérdida de contenido ni funcionalidad.'],
    [/text is used to convey information rather than images of text/i,
     () => 'Comprueba que se usa texto real en lugar de imágenes de texto, salvo cuando la imagen es esencial o personalizable.'],
    [/images of text are only used for pure decoration/i,
     () => 'Las imágenes de texto solo deben usarse como decoración pura o cuando la presentación visual es esencial.'],
    [/foreground and background colours.*for blocks of text/i,
     () => 'Comprueba que existe un mecanismo para que el usuario seleccione los colores de texto y fondo en bloques de texto.'],
    [/width of a block of text to no more than 80 characters/i,
     () => 'Comprueba que existe un mecanismo para reducir el ancho de los bloques de texto a 80 caracteres como máximo.'],
    [/blocks of text are not fully justified/i,
     () => 'Los bloques de texto no deben justificarse a ambos lados, o debe existir un mecanismo para eliminar esa justificación.'],
    [/line spacing in blocks of text are at least 150%/i,
     () => 'El interlineado en bloques de texto debe ser al menos del 150 % y el espaciado entre párrafos al menos 1,5 veces el interlineado.'],
    [/text can be resized.*without requiring the user to scroll horizontally/i,
     () => 'Comprueba que el texto puede redimensionarse hasta el 200 % sin necesidad de desplazamiento horizontal en pantalla completa.'],

    // ── Principio 2.1 – Teclado ──────────────────────────────────────────────
    [/functionality provided by.*double-clicking.*available through the keyboard/i,
     () => 'La función del doble clic en este elemento debe estar también disponible mediante teclado.'],
    [/functionality provided by mousing over.*available through the keyboard/i,
     () => 'La función del mouseover en este elemento debe estar disponible mediante teclado (p. ej. con el evento focus).'],
    [/functionality provided by mousing out.*available through the keyboard/i,
     () => 'La función del mouseout en este elemento debe estar disponible mediante teclado (p. ej. con el evento blur).'],
    [/functionality provided by moving the mouse.*available through the keyboard/i,
     () => 'La función del movimiento del ratón sobre este elemento debe estar disponible mediante teclado.'],
    [/functionality provided by mousing down.*available through the keyboard/i,
     () => 'La función del mousedown debe estar disponible mediante teclado (p. ej. con el evento keydown).'],
    [/functionality provided by mousing up.*available through the keyboard/i,
     () => 'La función del mouseup debe estar disponible mediante teclado (p. ej. con el evento keyup).'],
    [/functionality provided by an event handler.*available through the keyboard/i,
     () => 'La funcionalidad de este manejador de eventos debe estar también disponible mediante teclado.'],
    [/applet or plugin provides the ability to move the focus away/i,
     () => 'Comprueba que este applet o plugin permite mover el foco fuera de él usando el teclado.'],

    // ── Principio 2.2 – Tiempo suficiente ───────────────────────────────────
    [/Meta refresh tag used to redirect.*time limit that is not zero/i,
     () => 'La etiqueta meta refresh redirige a otra página con un límite de tiempo que los usuarios no pueden controlar.'],
    [/Meta refresh tag used to refresh the current page/i,
     () => 'La etiqueta meta refresh recarga la página. Los usuarios no pueden controlar este límite de tiempo.'],
    [/moves, scrolls or blinks for more than 5 seconds.*mechanism.*to pause/i,
     () => 'Si el contenido se mueve, desplaza o parpadea más de 5 segundos, debe existir un mecanismo para pausarlo, detenerlo u ocultarlo.'],
    [/mechanism.*to stop this blinking element in less than five seconds/i,
     () => 'Debe haber un mecanismo para detener este elemento parpadeante en menos de 5 segundos.'],
    [/Blink elements cannot satisfy the requirement/i,
     () => 'Los elementos <blink> no pueden satisfacer el requisito de detener el parpadeo en 5 segundos. Elimínalo.'],
    [/timing is not an essential part of the event or activity/i,
     () => 'Comprueba que el tiempo límite no es esencial para el evento o actividad presentado, salvo para medios sincronizados y eventos en tiempo real.'],
    [/interruptions.*can be postponed or suppressed by the user/i,
     () => 'Comprueba que todas las interrupciones (incluyendo actualizaciones de contenido) pueden posponerse o suprimirse, excepto las de emergencia.'],
    [/authenticated user can continue the activity without loss of data after re-authenticating/i,
     () => 'Si esta página tiene límite de inactividad, comprueba que el usuario autenticado puede continuar sin perder datos al volver a autenticarse.'],

    // ── Principio 2.3 – Convulsiones ─────────────────────────────────────────
    [/no component.*flashes more than three times.*1-second period.*size.*sufficiently small/i,
     () => 'Comprueba que ningún componente destella más de tres veces por segundo, o que el área destellante es suficientemente pequeña.'],
    [/no component.*flashes more than three times.*1-second period/i,
     () => 'Comprueba que ningún componente destella más de tres veces en ningún período de 1 segundo.'],

    // ── Principio 2.4 – Navegable ────────────────────────────────────────────
    [/Iframe element requires a non-empty title attribute that identifies the frame/i,
     () => 'El elemento <iframe> requiere un atributo title no vacío que identifique el marco.'],
    [/Check that the title attribute of this.*frame.*identifies the frame/i,
     () => 'Comprueba que el atributo title de este marco contiene texto que lo identifica.'],
    [/common navigation elements can be bypassed.*skip links/i,
     () => 'Comprueba que los elementos de navegación comunes pueden saltarse (por ejemplo, con enlaces de salto, encabezados o roles ARIA landmark).'],
    [/link points to a named anchor.*but no anchor exists with that name in the fragment/i,
     (m) => `Este enlace apunta a un ancla "${(m||[])[0]?.match(/["#]([^"#]+)/)?.[1] || '?'}" que no existe en el fragmento evaluado.`],
    [/link points to a named anchor.*but no anchor exists with that name/i,
     () => 'Este enlace apunta a un ancla dentro del documento que no existe.'],
    [/There is no head section.*descriptive title/i,
     () => 'No hay sección <head> en la que colocar el elemento <title> descriptivo.'],
    [/A title should be provided for the document.*non-empty title element/i,
     () => 'El documento debe tener un elemento <title> no vacío en la sección <head>.'],
    [/title element in the head section should be non-empty/i,
     () => 'El elemento <title> de la sección <head> no debe estar vacío.'],
    [/Check that the title element describes the document/i,
     () => 'Comprueba que el elemento <title> describe el contenido del documento.'],
    [/tabindex is used, check that the tab order.*follows relationships in the content/i,
     () => 'Si se usa tabindex, comprueba que el orden de tabulación sigue la relación lógica del contenido.'],
    [/link text combined with programmatically determined link context.*title attribute.*identifies the purpose/i,
     () => 'Comprueba que el texto del enlace, combinado con su contexto o atributo title, identifica claramente su propósito.'],
    [/link text combined with programmatically determined link context identifies the purpose/i,
     () => 'Comprueba que el texto del enlace combinado con su contexto programático identifica su propósito.'],
    [/more than one way of locating this Web page within a set/i,
     () => 'Si esta página no forma parte de un proceso lineal, comprueba que existe más de una forma de localizarla (menú, búsqueda, mapa del sitio…).'],
    [/headings and labels describe topic or purpose/i,
     () => 'Comprueba que los encabezados y etiquetas describen el tema o propósito del contenido.'],
    [/at least one mode.*keyboard focus indicator can be visually located/i,
     () => 'Comprueba que existe al menos un modo de operación en que el indicador de foco de teclado sea visible en los controles de la interfaz.'],
    [/Link elements can only be located in the head section/i,
     () => 'Los elementos <link> solo pueden colocarse dentro de la sección <head> del documento.'],
    [/Link element is missing a non-empty rel attribute/i,
     () => 'El elemento <link> no tiene un atributo rel no vacío que indique el tipo de enlace.'],
    [/Link element is missing a non-empty href attribute/i,
     () => 'El elemento <link> no tiene un atributo href no vacío que apunte al recurso enlazado.'],
    [/text of the link describes the purpose of the link/i,
     () => 'Comprueba que el texto del enlace describe su propósito de forma independiente, sin depender del contexto.'],

    // ── Principio 3.1 – Legible ──────────────────────────────────────────────
    [/html element should have a lang or xml:lang attribute/i,
     () => 'El elemento <html> debe tener el atributo lang (o xml:lang) que indique el idioma del documento (p. ej. lang="es").'],
    [/language specified in the lang attribute.*does not appear to be well-formed/i,
     () => 'El idioma especificado en el atributo lang no parece bien formado. Usa un código de idioma válido (p. ej. "es", "en", "es-MX").'],
    [/language specified in the xml:lang attribute.*does not appear to be well-formed/i,
     () => 'El idioma especificado en el atributo xml:lang no parece bien formado. Usa un código de idioma válido.'],
    [/change in language is marked using the lang.*attribute/i,
     () => 'Comprueba que cualquier cambio de idioma en el contenido está marcado con el atributo lang o xml:lang en el elemento correspondiente.'],
    [/mechanism.*for identifying specific definitions of words.*unusual or restricted way/i,
     () => 'Comprueba que existe un mecanismo para identificar definiciones de palabras usadas de forma inusual o restringida (jerga, modismos, etc.).'],
    [/mechanism.*for identifying the expanded form.*abbreviations/i,
     () => 'Comprueba que existe un mecanismo para identificar la forma completa o el significado de las abreviaturas.'],
    [/reading ability more advanced than the lower secondary education level/i,
     () => 'Si el contenido requiere un nivel de lectura superior a la educación secundaria básica, proporciona un resumen o versión alternativa más accesible.'],
    [/Ruby element does not contain an rt element/i,
     () => 'El elemento <ruby> no contiene un elemento <rt> con la información de pronunciación.'],
    [/Ruby element does not contain rp elements/i,
     () => 'El elemento <ruby> no contiene elementos <rp>, que proporcionan puntuación de respaldo para navegadores sin soporte ruby.'],

    // ── Principio 3.2 – Predecible ───────────────────────────────────────────
    [/change of context does not occur when this input field receives focus/i,
     () => 'Comprueba que este campo no produce un cambio de contexto al recibir el foco.'],
    [/form does not contain a submit button/i,
     () => 'Este formulario no tiene botón de envío. Los usuarios que naveguen solo con teclado no podrán enviarlo. Añade un botón <input type="submit"> o <button type="submit">.'],
    [/navigational mechanisms.*repeated on multiple Web pages.*same relative order/i,
     () => 'Comprueba que los mecanismos de navegación repetidos en varias páginas aparecen siempre en el mismo orden relativo.'],
    [/components.*same functionality.*identified consistently/i,
     () => 'Comprueba que los componentes con la misma funcionalidad se identifican de forma coherente en todas las páginas del sitio.'],
    [/link.*opens in a new window/i,
     () => 'Comprueba que el texto de este enlace indica que se abrirá en una nueva ventana o pestaña.'],

    // ── Principio 3.3 – Ayuda en la entrada ──────────────────────────────────
    [/input error is automatically detected.*items in error are identified.*described.*in text/i,
     () => 'Si se detecta automáticamente un error en el formulario, comprueba que los campos con error están identificados y el error descrito en texto.'],
    [/descriptive labels or instructions.*including for required fields.*are provided/i,
     () => 'Comprueba que se proporcionan etiquetas o instrucciones descriptivas (incluyendo campos obligatorios) para la entrada del usuario en este formulario.'],
    [/provides suggested corrections to errors.*unless.*jeopardize the security/i,
     () => 'Comprueba que el formulario sugiere correcciones a los errores de entrada, salvo que hacerlo comprometa la seguridad o el propósito del contenido.'],
    [/financial or legal commitment.*reversible.*checked.*confirmed/i,
     () => 'Si este formulario implica un compromiso legal o económico, comprueba que el envío es reversible, verificado o confirmado por el usuario.'],
    [/context-sensitive help is available/i,
     () => 'Comprueba que está disponible ayuda contextual para este formulario, tanto a nivel de página como de control.'],
    [/submissions to this form are either reversible.*checked.*confirmed/i,
     () => 'Comprueba que los envíos de este formulario son reversibles, verificados o confirmados por el usuario.'],

    // ── Principio 4.1 – Compatible ───────────────────────────────────────────
    [/Duplicate id attribute value "([^"]+)" found on the web page/i,
     (m) => `El id "${m[1]}" está duplicado en la página. Cada id debe ser único en el documento.`],
    [/Duplicate id attribute value/i,
     () => 'Existe un atributo id duplicado en esta página. Cada id debe ser único.'],
    [/Anchor element found with an ID but without a href or link text/i,
     () => 'Se encontró un elemento <a> con ID pero sin href ni texto de enlace. Mueve el ID a un elemento padre o cercano.'],
    [/Anchor element found with a name attribute but without a href or link text/i,
     () => 'Se encontró un elemento <a> con atributo name pero sin href ni texto. Convierte el name en un ID en un elemento padre.'],
    [/Anchor element found with no link content and no name and\/or ID attribute/i,
     () => 'Elemento <a> sin contenido, sin name y sin ID. Añade texto de enlace o elimina el elemento.'],
    [/Anchor elements should not be used for defining in-page link targets/i,
     () => 'Los elementos <a> no deben usarse como destinos de enlace interno. Usa el atributo id en un elemento padre.'],
    [/Anchor element found with link content, but no href, ID or name attribute/i,
     () => 'Este enlace tiene contenido de texto pero no tiene href, ID ni name. No es un enlace funcional.'],
    [/Anchor element found with a valid href attribute, but no link content has been supplied/i,
     () => 'Enlace (<a>) con href válido pero sin contenido de texto ni imagen con alt. Añade texto descriptivo o un aria-label.'],
    [/element has role of "button" but does not have a name available/i,
     () => 'Este elemento actúa como botón pero no tiene nombre accesible. Añade texto visible, aria-label o aria-labelledby.'],
    [/does not have a name available to an accessibility API/i,
     () => 'Este elemento no tiene un nombre accesible. Añade aria-label, aria-labelledby o contenido de texto visible.'],
    [/does not have a value available to an accessibility API/i,
     () => 'Este elemento no expone su valor a las APIs de accesibilidad. Revisa su implementación ARIA.'],
    [/does not have an initially selected option/i,
     () => 'Este selector no tiene una opción seleccionada inicialmente. El valor expuesto a la API de accesibilidad puede ser indefinido.'],
];

function translateIssueMessage(msg, runner) {
    if (!msg) return msg;
    // Los mensajes del dom-checker ya vienen en español desde el backend
    if (runner === 'dom-checker') return msg;
    for (const [pattern, replacer] of PA11Y_TRANSLATIONS) {
        const m = msg.match(pattern);
        if (m) return replacer(m);
    }
    // Sin traducción: loguear para diagnóstico
    console.warn('[pa11y sin traducción]', msg);
    return msg;
}
