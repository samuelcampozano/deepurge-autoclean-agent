/* ════════════════════════════════════════════════════════════
   Deepurge Dashboard – Frontend Application Logic
   ════════════════════════════════════════════════════════════ */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ─── Constants ─────────────────────────────────────────────
const CATEGORY_COLORS = {
    Documents: "#58a6ff", Images: "#3fb950", Videos: "#f0883e",
    Audio: "#bc8cff", Code: "#f778ba", Archives: "#79c0ff",
    Executables: "#f85149", Other: "#8b949e",
};
const CATEGORY_EMOJI = {
    Documents: "📄", Images: "📸", Videos: "🎬", Audio: "🎵",
    Code: "💻", Archives: "📦", Executables: "⚙️", Other: "📎",
};

function formatBytes(bytes) {
    if (!bytes || bytes === 0) return "0 B";
    const k = 1024, sizes = ["B", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return (bytes / Math.pow(k, i)).toFixed(1) + " " + sizes[i];
}
function formatTime(ts) { return ts ? new Date(ts).toLocaleString() : "–"; }
function shortBlob(id) {
    if (!id) return "–";
    return id.length > 28 ? id.slice(0, 14) + "…" + id.slice(-10) : id;
}
function extractBlobId(input) {
    input = input.trim();
    const m = input.match(/\/v1\/blobs\/(.+)$/);
    return m ? m[1] : input;
}

// ─── State ─────────────────────────────────────────────────
let liveInterval = null;
let logPollInterval = null;
let dashRefreshInterval = null;
let logOffset = 0;


// ─── Navigation ────────────────────────────────────────────
$$(".nav-item").forEach((item) => {
    item.addEventListener("click", (e) => {
        e.preventDefault();
        const view = item.dataset.view;
        $$(".nav-item").forEach((n) => n.classList.remove("active"));
        item.classList.add("active");
        $$(".view").forEach((v) => v.classList.remove("active"));
        $(`#view-${view}`).classList.add("active");
        $("#viewTitle").textContent = item.textContent.trim();
        closeSidebar();
        // Refresh data when switching to dashboard
        if (view === "dashboard") loadDashboardData();
        if (view === "history") loadHistory();
    });
});

// Sidebar
function openSidebar()  { $("#sidebar").classList.add("open"); $("#overlay").classList.add("visible"); }
function closeSidebar() { $("#sidebar").classList.remove("open"); $("#overlay").classList.remove("visible"); }
$("#menuToggle").addEventListener("click", () => {
    $("#sidebar").classList.contains("open") ? closeSidebar() : openSidebar();
});
$("#overlay").addEventListener("click", closeSidebar);
if ($("#sidebarClose")) $("#sidebarClose").addEventListener("click", closeSidebar);

// Refresh button
$("#refreshBtn").addEventListener("click", () => { loadDashboardData(); pollAgentStatus(); });


// ═══════════════════════════════════════════════════════════
//  CONTROL PANEL
// ═══════════════════════════════════════════════════════════

// ─── Start Agent ───────────────────────────────────────────
$("#btnStartAgent").addEventListener("click", async () => {
    $("#btnStartAgent").disabled = true;
    $("#btnStartAgent").textContent = "⏳ Starting…";
    try {
        const resp = await fetch("/api/agent/start", { method: "POST" });
        const data = await resp.json();
        appendConsole(`[SYS] ${data.status === "started" ? "Agent started ✅" : "Agent already running"}`, "sys");
    } catch (err) {
        appendConsole(`[ERR] Failed to start agent: ${err.message}`, "err");
    }
    pollAgentStatus();
    startLogPolling();
    startDashRefresh();
});

// ─── Stop Agent ────────────────────────────────────────────
$("#btnStopAgent").addEventListener("click", async () => {
    $("#btnStopAgent").disabled = true;
    $("#btnStopAgent").textContent = "⏳ Stopping…";
    try {
        const resp = await fetch("/api/agent/stop", { method: "POST" });
        const data = await resp.json();
        appendConsole(`[SYS] ${data.status === "stopped" ? "Agent stopped 🛑" : "Agent was not running"}`, "sys");
    } catch (err) {
        appendConsole(`[ERR] Failed to stop agent: ${err.message}`, "err");
    }
    pollAgentStatus();
    stopLogPolling();
    stopDashRefresh();
    // Final dashboard refresh after stop
    setTimeout(loadDashboardData, 2000);
});

// ─── Generate Demo ─────────────────────────────────────────
$("#btnGenerateDemo").addEventListener("click", async () => {
    const count = parseInt($("#demoCount").value) || 50;
    $("#btnGenerateDemo").disabled = true;
    $("#btnGenerateDemo").textContent = "⏳ Generating…";
    appendConsole(`[SYS] Generating ${count} demo files...`, "sys");
    try {
        await fetch("/api/demo/generate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ count }),
        });
    } catch (err) {
        appendConsole(`[ERR] ${err.message}`, "err");
    }
    // Re-enable after a delay
    setTimeout(() => {
        $("#btnGenerateDemo").disabled = false;
        $("#btnGenerateDemo").textContent = "📦 Generate Demo Files";
    }, 3000);
    // Start polling logs if not already
    startLogPolling();
});

// ─── Agent Status Polling ──────────────────────────────────
async function pollAgentStatus() {
    try {
        const resp = await fetch("/api/agent/status");
        const data = await resp.json();
        const running = data.running;

        // Topbar indicator
        $("#indicatorDot").classList.toggle("running", running);
        $("#indicatorText").textContent = running ? "Agent Running" : "Agent Stopped";

        // Control panel
        $("#agentStatusPanel").classList.toggle("running", running);
        $("#agentStatusText").innerHTML = running
            ? 'Agent is <strong style="color:var(--accent-green)">running</strong>'
            : 'Agent is <strong style="color:var(--accent-red)">stopped</strong>';
        $("#agentPidText").textContent = running ? `PID: ${data.pid}  ·  Started: ${formatTime(data.started_at)}` : "";

        // Buttons
        $("#btnStartAgent").disabled = running;
        $("#btnStartAgent").textContent = running ? "✅ Running" : "▶ Start Agent";
        $("#btnStopAgent").disabled = !running;
        $("#btnStopAgent").textContent = "⏹ Stop Agent";

        // If running, ensure we're polling logs and refreshing dashboard
        if (running) { startLogPolling(); startDashRefresh(); }
    } catch (err) {
        console.error("Status poll error:", err);
    }
}

// ─── Console Log Polling ───────────────────────────────────
function startLogPolling() {
    if (logPollInterval) return;
    logPollInterval = setInterval(pollLogs, 1000);
    pollLogs();
}
function stopLogPolling() {
    if (logPollInterval) { clearInterval(logPollInterval); logPollInterval = null; }
}

async function pollLogs() {
    try {
        const resp = await fetch(`/api/agent/logs?since=${logOffset}`);
        const data = await resp.json();
        if (data.lines && data.lines.length > 0) {
            data.lines.forEach((line) => {
                const cls = line.includes("[ERR]") || line.includes("ERROR") || line.includes("❌")
                    ? "err"
                    : line.includes("[SYS]") ? "sys"
                    : line.includes("✅") || line.includes("✓") ? "ok" : "";
                appendConsole(line, cls);
            });
            logOffset = data.total;
        }
    } catch (err) { /* ignore */ }
}

function appendConsole(text, cls = "") {
    const el = $("#consoleOutput");
    const div = document.createElement("div");
    div.className = `console-line ${cls}`;
    div.textContent = text;
    el.appendChild(div);
    // Auto-scroll
    el.scrollTop = el.scrollHeight;
    // Trim old lines
    while (el.children.length > 500) el.removeChild(el.firstChild);
}

// ─── Dashboard Auto-refresh ───────────────────────────────
function startDashRefresh() {
    if (dashRefreshInterval) return;
    dashRefreshInterval = setInterval(loadDashboardData, 5000);
}
function stopDashRefresh() {
    if (dashRefreshInterval) { clearInterval(dashRefreshInterval); dashRefreshInterval = null; }
}


// ═══════════════════════════════════════════════════════════
//  DASHBOARD VIEW
// ═══════════════════════════════════════════════════════════

async function loadDashboardData() {
    try {
        const resp = await fetch("/api/db-stats");
        if (!resp.ok) return;
        const data = await resp.json();

        const stats = data.stats || {};
        $("#statFiles").textContent = (stats.total_files_processed || 0).toLocaleString();
        $("#statSize").textContent = formatBytes(stats.total_bytes_processed || 0);
        $("#statUploads").textContent = (data.walrus_uploads || []).length;
        $("#statCategories").textContent = (data.categories || []).length;

        renderCategoryChart(data.categories || []);
        renderRecentActivity(data.recent_actions || []);
        renderUploadsTable(data.walrus_uploads || []);
    } catch (err) {
        console.error("Dashboard load error:", err);
    }
}

function renderCategoryChart(categories) {
    const container = $("#categoryChart");
    if (!categories.length) {
        container.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem;">No data yet — run the agent first!</p>';
        return;
    }
    const max = Math.max(...categories.map((c) => c.count));
    container.innerHTML = categories.map((c) => {
        const pct = Math.max(5, (c.count / max) * 100);
        const color = CATEGORY_COLORS[c.category] || CATEGORY_COLORS.Other;
        const emoji = CATEGORY_EMOJI[c.category] || "📎";
        return `<div class="chart-bar-row">
            <span class="chart-bar-label">${emoji} ${c.category}</span>
            <div class="chart-bar-track"><div class="chart-bar-fill" style="width:${pct}%;background:${color};">${c.count}</div></div>
            <span class="chart-bar-count">${formatBytes(c.total_size)}</span>
        </div>`;
    }).join("");
}

function renderRecentActivity(actions) {
    const list = $("#recentActivity");
    if (!actions.length) {
        list.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem;padding:16px;">No recent activity.</p>';
        return;
    }
    list.innerHTML = actions.slice(0, 30).map((a) => {
        const emoji = CATEGORY_EMOJI[a.category] || "📎";
        const badge = a.action_type === "MOVED" ? "badge-moved" : a.status === "error" ? "badge-error" : "badge-skipped";
        return `<div class="activity-item">
            <span class="activity-emoji">${emoji}</span>
            <div class="activity-body">
                <div class="activity-file">${a.file_name}</div>
                <div class="activity-meta">${a.category} · ${formatBytes(a.file_size)} · ${formatTime(a.timestamp)}</div>
            </div>
            <span class="activity-badge ${badge}">${a.action_type}</span>
        </div>`;
    }).join("");
}

function renderUploadsTable(uploads) {
    const tbody = $("#uploadsTable tbody");
    if (!uploads.length) {
        tbody.innerHTML = '<tr><td colspan="5" style="color:var(--text-muted);text-align:center;padding:24px;">No Walrus uploads recorded yet.</td></tr>';
        return;
    }
    tbody.innerHTML = uploads.map((u) => `<tr>
        <td>${formatTime(u.timestamp)}</td>
        <td>${u.content_type || "–"}</td>
        <td>${u.action_count || "–"}</td>
        <td class="blob-id-cell" title="${u.blob_id}">${shortBlob(u.blob_id)}</td>
        <td><button class="btn btn-explore" onclick="exploreBlobFromHistory('${u.blob_id}')">Explore →</button></td>
    </tr>`).join("");
}


// ═══════════════════════════════════════════════════════════
//  BLOB EXPLORER
// ═══════════════════════════════════════════════════════════

$("#fetchBlobBtn").addEventListener("click", () => {
    const raw = $("#blobInput").value;
    if (!raw.trim()) return;
    fetchAndRenderBlob(extractBlobId(raw));
});
$("#blobInput").addEventListener("keydown", (e) => { if (e.key === "Enter") $("#fetchBlobBtn").click(); });

async function fetchAndRenderBlob(blobId) {
    const panel = $("#blobResultPanel");
    panel.classList.remove("hidden");
    $("#blobResultTitle").textContent = "⏳ Fetching blob…";
    $("#blobRawJson").textContent = "";
    $("#blobStatStrip").classList.add("hidden");
    $("#blobTableWrap").classList.add("hidden");

    try {
        const resp = await fetch(`/api/blob/${encodeURIComponent(blobId)}`);
        const data = await resp.json();
        if (data.error) {
            $("#blobResultTitle").textContent = "❌ Error";
            $("#blobRawJson").textContent = data.error;
            return;
        }
        $("#blobRawJson").textContent = JSON.stringify(data, null, 2);

        if (data.actions && Array.isArray(data.actions)) renderBatchBlob(data, blobId);
        else if (data.report_type === "daily") renderReportBlob(data, blobId);
        else if (data.summary_type === "session") renderSessionBlob(data, blobId);
        else if (data.entries && Array.isArray(data.entries)) renderBatchBlob({ ...data, actions: data.entries, action_count: data.entry_count }, blobId);
        else { $("#blobResultTitle").textContent = "🦭 Blob Data"; $("#blobMeta").textContent = `Blob ID: ${blobId}`; }
    } catch (err) {
        $("#blobResultTitle").textContent = "❌ Fetch Failed";
        $("#blobRawJson").textContent = err.message;
    }
}

function renderBatchBlob(data, blobId) {
    const actions = data.actions || [];
    $("#blobResultTitle").textContent = "📦 Action Batch";
    $("#blobMeta").innerHTML = `<div>Blob: <span style="color:var(--accent-purple)">${shortBlob(blobId)}</span></div><div>${formatTime(data.timestamp)}</div>`;

    const cats = {}; let totalSize = 0;
    actions.forEach((a) => { cats[a.category || "Other"] = (cats[a.category || "Other"] || 0) + 1; totalSize += a.file_size || 0; });

    const strip = $("#blobStatStrip");
    strip.classList.remove("hidden");
    strip.innerHTML = `
        <div class="stat-card accent-blue"><div class="stat-icon">📋</div><div class="stat-body"><span class="stat-value">${actions.length}</span><span class="stat-label">Total Actions</span></div></div>
        <div class="stat-card accent-green"><div class="stat-icon">💾</div><div class="stat-body"><span class="stat-value">${formatBytes(totalSize)}</span><span class="stat-label">Total Size</span></div></div>
        <div class="stat-card accent-purple"><div class="stat-icon">📂</div><div class="stat-body"><span class="stat-value">${Object.keys(cats).length}</span><span class="stat-label">Categories</span></div></div>
        <div class="stat-card accent-orange"><div class="stat-icon">✅</div><div class="stat-body"><span class="stat-value">${actions.filter(a => a.status === "completed").length}</span><span class="stat-label">Completed</span></div></div>`;

    const wrap = $("#blobTableWrap"); wrap.classList.remove("hidden");
    $("#blobTable tbody").innerHTML = actions.map((a, i) => {
        const emoji = CATEGORY_EMOJI[a.category] || "📎";
        const badge = a.action_type === "MOVED" ? "badge-moved" : a.status === "error" ? "badge-error" : "badge-skipped";
        return `<tr><td>${a.id || i + 1}</td><td>${formatTime(a.timestamp)}</td><td><span class="activity-badge ${badge}">${a.action_type}</span></td><td title="${a.original_path || ""}">${emoji} ${a.file_name}</td><td>${a.category}</td><td>${formatBytes(a.file_size)}</td><td>${a.status || "–"}</td></tr>`;
    }).join("");
}

function renderReportBlob(data, blobId) {
    $("#blobResultTitle").textContent = "📊 Daily Report";
    $("#blobMeta").innerHTML = `<div>Date: <strong>${data.report_date}</strong></div><div>Blob: <span style="color:var(--accent-purple)">${shortBlob(blobId)}</span></div>`;
    const stats = data.statistics || {};
    const strip = $("#blobStatStrip"); strip.classList.remove("hidden");
    strip.innerHTML = `
        <div class="stat-card accent-blue"><div class="stat-icon">📁</div><div class="stat-body"><span class="stat-value">${stats.total_files || 0}</span><span class="stat-label">Files</span></div></div>
        <div class="stat-card accent-green"><div class="stat-icon">💾</div><div class="stat-body"><span class="stat-value">${formatBytes(stats.total_size || 0)}</span><span class="stat-label">Size</span></div></div>`;
    $("#blobTableWrap").classList.add("hidden");
}

function renderSessionBlob(data, blobId) {
    const ops = data.operations || [];
    renderBatchBlob({ actions: ops, action_count: ops.length, timestamp: data.session_end }, blobId);
    $("#blobResultTitle").textContent = "🔄 Session Summary";
}

function exploreBlobFromHistory(blobId) {
    $$(".nav-item").forEach((n) => n.classList.remove("active"));
    document.querySelector('[data-view="explorer"]').classList.add("active");
    $$(".view").forEach((v) => v.classList.remove("active"));
    $("#view-explorer").classList.add("active");
    $("#viewTitle").textContent = "🔍 Blob Explorer";
    $("#blobInput").value = blobId;
    fetchAndRenderBlob(blobId);
}


// ═══════════════════════════════════════════════════════════
//  UPLOAD HISTORY
// ═══════════════════════════════════════════════════════════

async function loadHistory() {
    try {
        const resp = await fetch("/api/db-walrus-blobs");
        const data = await resp.json();
        const blobs = data.blobs || [];
        const tbody = $("#historyTable tbody");
        if (!blobs.length) {
            tbody.innerHTML = '<tr><td colspan="5" style="color:var(--text-muted);text-align:center;padding:24px;">No uploads found.</td></tr>';
            return;
        }
        tbody.innerHTML = blobs.map((b) => `<tr>
            <td>${formatTime(b.timestamp)}</td><td>${b.content_type || "–"}</td><td>${b.action_count || "–"}</td>
            <td class="blob-id-cell" title="${b.blob_id}">${shortBlob(b.blob_id)}</td>
            <td><button class="btn btn-explore" onclick="exploreBlobFromHistory('${b.blob_id}')">Explore →</button></td>
        </tr>`).join("");
    } catch (err) { console.error("History error:", err); }
}


// ═══════════════════════════════════════════════════════════
//  LIVE FEED
// ═══════════════════════════════════════════════════════════

$("#liveToggle").addEventListener("click", () => {
    if (liveInterval) {
        clearInterval(liveInterval); liveInterval = null;
        $("#liveToggle").textContent = "▶ Start Live";
        $("#liveStatus").textContent = "Paused"; $("#liveStatus").classList.remove("active");
    } else {
        loadLiveFeed();
        liveInterval = setInterval(loadLiveFeed, 10000);
        $("#liveToggle").textContent = "⏸ Pause";
        $("#liveStatus").textContent = "● Live"; $("#liveStatus").classList.add("active");
    }
});

async function loadLiveFeed() {
    try {
        const resp = await fetch("/api/db-stats");
        if (!resp.ok) return;
        const data = await resp.json();
        const actions = data.recent_actions || [];
        const list = $("#liveFeed");
        if (!actions.length) { list.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem;padding:16px;">Waiting for agent activity…</p>'; return; }
        list.innerHTML = actions.map((a) => {
            const emoji = CATEGORY_EMOJI[a.category] || "📎";
            const badge = a.action_type === "MOVED" ? "badge-moved" : a.status === "error" ? "badge-error" : "badge-skipped";
            return `<div class="activity-item"><span class="activity-emoji">${emoji}</span><div class="activity-body"><div class="activity-file">${a.file_name}</div><div class="activity-meta">${a.category} · ${formatBytes(a.file_size)} · ${formatTime(a.timestamp)}</div></div><span class="activity-badge ${badge}">${a.action_type}</span></div>`;
        }).join("");
    } catch (err) { console.error("Live feed error:", err); }
}


// ═══════════════════════════════════════════════════════════
//  BOOT
// ═══════════════════════════════════════════════════════════

document.addEventListener("DOMContentLoaded", () => {
    pollAgentStatus();
    loadDashboardData();
    loadHistory();
    // Poll agent status every 3s
    setInterval(pollAgentStatus, 3000);
});
