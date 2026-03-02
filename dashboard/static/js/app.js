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
        if (view === "vault") { loadVaultFiles(); }
        if (view === "workflows") { loadWorkflowRules(); loadWorkflowExecutions(); }
        if (view === "anchors") { loadAnchors(); }
        if (view === "organize") { initOrganizeView(); }
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

        // Load insights & blockchain metrics
        loadInsights();
    } catch (err) {
        console.error("Dashboard load error:", err);
    }
}

// ─── Insights & Blockchain Metrics ─────────────────────────
async function loadInsights() {
    try {
        const resp = await fetch("/api/insights");
        if (!resp.ok) return;
        const d = await resp.json();

        // Smart Insights card
        $("#insightTimeSaved").textContent = d.time_saved_display || "–";
        $("#insightTopCat").textContent = d.top_category
            ? `${d.top_category} (${d.top_category_pct}%)`
            : "–";
        $("#insightDuplicates").textContent = d.duplicates_prevented || "0";
        $("#insightBlobs").textContent = d.total_blobs || "0";

        // Walrus Blockchain Status panel
        $("#chainTotalBlobs").textContent = d.total_blobs || "0";
        $("#chainStorage").textContent = d.walrus_storage_display || "0 B";
        $("#chainOldest").textContent = d.oldest_blob
            ? new Date(d.oldest_blob).toLocaleDateString()
            : "–";
        $("#chainNewest").textContent = d.newest_blob
            ? new Date(d.newest_blob).toLocaleDateString()
            : "–";
    } catch (err) {
        console.error("Insights load error:", err);
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
//  VAULT (Path 2)
// ═══════════════════════════════════════════════════════════

let vaultSelectedFile = null;

// File input
if ($("#vaultFileInput")) {
    $("#vaultFileInput").addEventListener("change", (e) => {
        vaultSelectedFile = e.target.files[0];
        if (vaultSelectedFile) {
            $("#vaultDropzone").querySelector("p").textContent = `Selected: ${vaultSelectedFile.name} (${formatBytes(vaultSelectedFile.size)})`;
            $("#btnVaultUpload").disabled = false;
        }
    });
}

// Dropzone
if ($("#vaultDropzone")) {
    const dz = $("#vaultDropzone");
    dz.addEventListener("dragover", (e) => { e.preventDefault(); dz.classList.add("dragover"); });
    dz.addEventListener("dragleave", () => dz.classList.remove("dragover"));
    dz.addEventListener("drop", (e) => {
        e.preventDefault(); dz.classList.remove("dragover");
        if (e.dataTransfer.files.length) {
            vaultSelectedFile = e.dataTransfer.files[0];
            dz.querySelector("p").textContent = `Selected: ${vaultSelectedFile.name} (${formatBytes(vaultSelectedFile.size)})`;
            $("#btnVaultUpload").disabled = false;
        }
    });
}

// Upload
if ($("#btnVaultUpload")) {
    $("#btnVaultUpload").addEventListener("click", async () => {
        if (!vaultSelectedFile) return;
        $("#btnVaultUpload").disabled = true;
        $("#btnVaultUpload").textContent = "⏳ Encrypting & Uploading…";
        const formData = new FormData();
        formData.append("file", vaultSelectedFile);
        try {
            const resp = await fetch("/api/vault/upload", { method: "POST", body: formData });
            const data = await resp.json();
            if (data.error) { alert("Vault error: " + data.error); return; }
            // Show result
            $("#vaultResult").classList.remove("hidden");
            $("#vaultBlobId").textContent = data.blob_id || "–";
            $("#vaultSha256").textContent = (data.sha256 || "–").slice(0, 32) + "…";
            $("#vaultEncSize").textContent = formatBytes(data.encrypted_size || 0);
            $("#vaultKeyHex").textContent = data.key_hex || "–";
            $("#vaultShareLink").value = data.share_link || "";
            loadVaultFiles();
        } catch (err) {
            alert("Upload failed: " + err.message);
        } finally {
            $("#btnVaultUpload").disabled = false;
            $("#btnVaultUpload").textContent = "🔒 Encrypt & Upload to Walrus";
        }
    });
}

// Copy share link
if ($("#btnCopyShareLink")) {
    $("#btnCopyShareLink").addEventListener("click", () => {
        const link = $("#vaultShareLink").value;
        navigator.clipboard.writeText(link).then(() => {
            $("#btnCopyShareLink").textContent = "✅ Copied!";
            setTimeout(() => { $("#btnCopyShareLink").textContent = "📋 Copy"; }, 2000);
        });
    });
}

// Folder sync
if ($("#btnVaultSyncFolder")) {
    $("#btnVaultSyncFolder").addEventListener("click", async () => {
        const fp = $("#vaultFolderPath").value.trim();
        if (!fp) return;
        $("#btnVaultSyncFolder").disabled = true;
        $("#btnVaultSyncFolder").textContent = "⏳ Syncing…";
        try {
            const resp = await fetch("/api/vault/upload-folder", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ folder_path: fp }),
            });
            const data = await resp.json();
            if (data.error) { alert("Error: " + data.error); return; }
            $("#vaultFolderResult").classList.remove("hidden");
            $("#vaultFolderSummary").innerHTML = `✅ Synced <strong>${data.file_count}</strong> files from <strong>${data.folder_name}</strong><br>Root Hash: <code>${(data.root_hash || "").slice(0, 32)}…</code><br>Key: <code class="key-blur">${(data.key_hex || "").slice(0, 24)}…</code>`;
        } catch (err) {
            alert("Sync failed: " + err.message);
        } finally {
            $("#btnVaultSyncFolder").disabled = false;
            $("#btnVaultSyncFolder").textContent = "🔄 Sync Folder";
        }
    });
}

// Decrypt & download
if ($("#btnVaultDecrypt")) {
    $("#btnVaultDecrypt").addEventListener("click", async () => {
        let input = ($("#vaultDecryptInput").value || "").trim();
        let keyHex = ($("#vaultDecryptKey").value || "").trim();
        let blobId = "", nonceHex = "", fileName = "downloaded_file";

        // Try parsing as share link / token
        if (input.includes("#")) {
            const token = input.split("#").pop();
            try {
                const decoded = JSON.parse(atob(token.replace(/-/g,"+").replace(/_/g,"/")));
                blobId = decoded.b;
                keyHex = decoded.k;
                nonceHex = decoded.n;
                fileName = decoded.f || fileName;
            } catch(e) { blobId = input; }
        } else {
            blobId = input;
        }

        if (!blobId || !keyHex) { alert("Enter a share link or blob ID + key"); return; }
        // If nonce not extracted from token, try getting from vault files table
        if (!nonceHex) { alert("Nonce not found. Use a full share link."); return; }

        try {
            const resp = await fetch("/api/vault/download", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ blob_id: blobId, key_hex: keyHex, nonce_hex: nonceHex, file_name: fileName }),
            });
            if (!resp.ok) { const err = await resp.json(); alert(err.error); return; }
            const blob = await resp.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url; a.download = fileName; a.click();
            URL.revokeObjectURL(url);
        } catch (err) {
            alert("Decrypt failed: " + err.message);
        }
    });
}

async function loadVaultFiles() {
    try {
        const resp = await fetch("/api/vault/files");
        const data = await resp.json();
        const files = data.files || [];
        const tbody = $("#vaultFilesTable tbody");
        if (!files.length) {
            tbody.innerHTML = '<tr><td colspan="5" style="color:var(--text-muted);text-align:center;padding:24px;">No vault files yet.</td></tr>';
            return;
        }
        tbody.innerHTML = files.map(f => `<tr>
            <td>${formatTime(f.timestamp)}</td>
            <td>${f.file_name || "–"}</td>
            <td>${formatBytes(f.file_size || 0)}</td>
            <td class="blob-id-cell" title="${f.blob_id}">${shortBlob(f.blob_id)}</td>
            <td>
                <button class="btn btn-explore" onclick="copyVaultShare('${f.blob_id}','${f.key_hex}','${f.nonce_hex}','${(f.file_name||"").replace(/'/g,"\\'")}')">🔗 Share</button>
            </td>
        </tr>`).join("");
    } catch(e) { console.error("Vault files error:", e); }
}

function copyVaultShare(blobId, keyHex, nonceHex, fileName) {
    const payload = JSON.stringify({b:blobId,k:keyHex,n:nonceHex,f:fileName});
    const token = btoa(payload).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/,"");
    const link = `${location.origin}/vault/share#${token}`;
    navigator.clipboard.writeText(link).then(() => alert("Share link copied!"));
}

// Check if we arrived via a share link
function checkShareLink() {
    if (location.hash && location.pathname.includes("/vault/share")) {
        const token = location.hash.slice(1);
        try {
            const decoded = JSON.parse(atob(token.replace(/-/g,"+").replace(/_/g,"/")));
            // Switch to vault view
            $$(".nav-item").forEach(n => n.classList.remove("active"));
            document.querySelector('[data-view="vault"]').classList.add("active");
            $$(".view").forEach(v => v.classList.remove("active"));
            $("#view-vault").classList.add("active");
            $("#viewTitle").textContent = "🔐 Vault";
            // Fill decrypt fields
            $("#vaultDecryptInput").value = location.href;
            $("#vaultDecryptKey").value = decoded.k;
        } catch(e) {}
    }
}


// ═══════════════════════════════════════════════════════════
//  WORKFLOWS (Path 3)
// ═══════════════════════════════════════════════════════════

async function loadWorkflowRules() {
    try {
        const resp = await fetch("/api/workflows/rules");
        const data = await resp.json();
        const rules = data.rules || [];
        const list = $("#wfRulesList");
        if (!rules.length) {
            list.innerHTML = '<p style="color:var(--text-muted);padding:16px;">No rules configured.</p>';
            return;
        }
        list.innerHTML = rules.map(r => {
            const status = r.enabled ? "✅" : "⏸️";
            const actionsText = r.actions.map(a => `${a.type}${a.destination ? ":" + a.destination : a.value ? ":" + a.value : ""}`).join(", ");
            return `<div class="wf-rule-card">
                <div class="wf-rule-header">
                    <span class="wf-rule-status">${status}</span>
                    <strong>${r.name}</strong>
                    <span class="wf-rule-type">${r.trigger_type}</span>
                </div>
                <div class="wf-rule-body">
                    <span class="wf-rule-trigger">IF: <code>${r.trigger_value}</code></span>
                    <span class="wf-rule-actions">THEN: ${actionsText}</span>
                </div>
                <div class="wf-rule-actions-btns">
                    <button class="btn btn-sm btn-outline" onclick="toggleWfRule('${r.name}', ${!r.enabled})">${r.enabled ? '⏸️ Disable' : '▶ Enable'}</button>
                    <button class="btn btn-sm btn-outline" style="color:var(--accent-red)" onclick="deleteWfRule('${r.name}')">🗑️ Delete</button>
                </div>
            </div>`;
        }).join("");
    } catch(e) { console.error("Rules error:", e); }
}

async function toggleWfRule(name, enabled) {
    await fetch(`/api/workflows/rules/${encodeURIComponent(name)}/toggle`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
    });
    loadWorkflowRules();
}

async function deleteWfRule(name) {
    if (!confirm(`Delete rule "${name}"?`)) return;
    await fetch(`/api/workflows/rules/${encodeURIComponent(name)}`, { method: "DELETE" });
    loadWorkflowRules();
}

if ($("#btnWfAddRule")) {
    $("#btnWfAddRule").addEventListener("click", async () => {
        const name = ($("#wfRuleName").value || "").trim();
        const triggerType = $("#wfTriggerType").value;
        const triggerValue = ($("#wfTriggerValue").value || "").trim();
        const actionsRaw = ($("#wfActions").value || "").trim();

        if (!name || !triggerValue || !actionsRaw) { alert("Fill all fields"); return; }

        const actions = actionsRaw.split(",").map(a => {
            const parts = a.trim().split(":");
            const action = { type: parts[0].trim() };
            if (parts[1]) {
                if (parts[0].trim() === "move") action.destination = parts[1].trim();
                else action.value = parts[1].trim();
            }
            return action;
        });

        try {
            await fetch("/api/workflows/rules", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name, trigger_type: triggerType, trigger_value: triggerValue, actions, enabled: true }),
            });
            loadWorkflowRules();
            // Clear form
            $("#wfRuleName").value = "";
            $("#wfTriggerValue").value = "";
            $("#wfActions").value = "";
        } catch(e) { alert(e.message); }
    });
}

async function loadWorkflowExecutions() {
    try {
        const resp = await fetch("/api/workflows/executions");
        const data = await resp.json();
        const execs = data.executions || [];
        const list = $("#wfExecutionLog");
        if (!execs.length) {
            list.innerHTML = '<p style="color:var(--text-muted);padding:16px;">No workflow executions yet.</p>';
            return;
        }
        list.innerHTML = execs.map(e => {
            const actions = e.actions_taken ? JSON.parse(e.actions_taken) : [];
            const actText = actions.map(a => `${a.type}: ${a.status}`).join(", ");
            return `<div class="activity-item">
                <span class="activity-emoji">⚡</span>
                <div class="activity-body">
                    <div class="activity-file">${e.file_name} → ${e.rule_name}</div>
                    <div class="activity-meta">${actText} · ${formatTime(e.timestamp)}</div>
                </div>
                <span class="activity-badge badge-moved">${e.status}</span>
            </div>`;
        }).join("");
    } catch(e) { console.error("Executions error:", e); }
}


// ═══════════════════════════════════════════════════════════
//  SUI ANCHOR (Path 3)
// ═══════════════════════════════════════════════════════════

async function loadAnchors() {
    try {
        const resp = await fetch("/api/anchors");
        const data = await resp.json();
        const anchors = data.anchors || [];

        // Stats
        $("#anchorCount").textContent = anchors.length;
        if (anchors.length > 0) {
            const latest = anchors[0];
            $("#anchorLatestDate").textContent = latest.date || "–";
            $("#anchorSource").textContent = latest.source || "local";
        }

        // Table
        const tbody = $("#anchorTable tbody");
        if (!anchors.length) {
            tbody.innerHTML = '<tr><td colspan="5" style="color:var(--text-muted);text-align:center;padding:24px;">No anchors yet. Run the agent to generate daily reports.</td></tr>';
            return;
        }
        tbody.innerHTML = anchors.map(a => `<tr>
            <td>${a.date || "–"}</td>
            <td class="blob-id-cell" title="${a.root_hash}">${(a.root_hash || "–").slice(0,24)}…</td>
            <td>${a.source || "–"}</td>
            <td class="blob-id-cell">${a.tx_digest || "–"}</td>
            <td>${formatTime(a.anchored_at)}</td>
        </tr>`).join("");
    } catch(e) { console.error("Anchors error:", e); }
}

if ($("#btnAnchorVerify")) {
    $("#btnAnchorVerify").addEventListener("click", async () => {
        const date = ($("#anchorVerifyDate").value || "").trim();
        const hash = ($("#anchorVerifyHash").value || "").trim();
        if (!date || !hash) { alert("Enter date and root hash"); return; }

        try {
            const resp = await fetch("/api/anchors/verify", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ date, root_hash: hash }),
            });
            const result = await resp.json();
            const el = $("#anchorVerifyResult");
            el.classList.remove("hidden");
            if (result.verified) {
                el.innerHTML = `<div class="anchor-verified">✅ <strong>Verified!</strong> Root hash matches the ${result.source || "local"} record.</div>`;
            } else {
                el.innerHTML = `<div class="anchor-failed">❌ <strong>Mismatch!</strong> ${result.reason || "Hash does not match."}</div>`;
            }
        } catch(e) { alert(e.message); }
    });
}


// ═══════════════════════════════════════════════════════════
//  ORGANIZE VIEW — Folder Browser + Organization Settings
// ═══════════════════════════════════════════════════════════

let organizeState = {
    currentBrowsePath: "",
    selectedFolder: "",
    destFolder: "",
    browsingDest: false,
    renamePattern: "YYYYMMDD_HHMMSS",
    logToWalrus: true,
    categories: null, // null = use defaults from config
};

async function initOrganizeView() {
    // Fetch the watch folder from config so we start at the right path
    try {
        const resp = await fetch("/api/organize/config");
        const cfg = await resp.json();
        const watchFolder = cfg.watch_folder || "";
        const organizedFolder = cfg.organized_folder || "";
        await browseTo(watchFolder);
        // Pre-select watch folder as source and set destination
        if (watchFolder) { selectSourceFolder(watchFolder); }
        if (organizedFolder) { $("#destFolderInput").value = organizedFolder; }
    } catch {
        await browseTo("");
    }
    loadCategoriesEditor();
}

// ─── Folder Browser ─────────────────────────────────────────

async function browseTo(path) {
    const listEl = $("#folderList");
    listEl.innerHTML = '<div class="folder-list-loading">Loading…</div>';

    try {
        const url = `/api/browse?path=${encodeURIComponent(path)}&files=true`;
        const resp = await fetch(url);
        const data = await resp.json();

        if (data.error) {
            listEl.innerHTML = `<div class="folder-list-error">❌ ${data.error}</div>`;
            return;
        }

        organizeState.currentBrowsePath = data.path;
        updateBreadcrumb(data.path, "folderBreadcrumb", false);

        if (!data.items.length) {
            listEl.innerHTML = '<div class="folder-list-empty">📭 Empty folder</div>';
            return;
        }

        listEl.innerHTML = data.items.map(item => {
            if (item.type === "drive") {
                return `<div class="folder-item drive" onclick="browseTo('${escPath(item.path)}')">
                    <span class="fi-icon">💿</span>
                    <span class="fi-name">${item.name}</span>
                </div>`;
            }
            if (item.type === "folder") {
                return `<div class="folder-item dir" onclick="browseTo('${escPath(item.path)}')" ondblclick="selectSourceFolder('${escPath(item.path)}')">
                    <span class="fi-icon">📁</span>
                    <span class="fi-name">${item.name}</span>
                    <span class="fi-arrow">→</span>
                </div>`;
            }
            // file
            const extColor = CATEGORY_COLORS[extensionToCategory(item.ext)] || CATEGORY_COLORS.Other;
            return `<div class="folder-item file">
                <span class="fi-icon" style="color:${extColor}">${extensionToEmoji(item.ext)}</span>
                <span class="fi-name">${item.name}</span>
                <span class="fi-size">${formatBytes(item.size)}</span>
            </div>`;
        }).join("");

    } catch (err) {
        listEl.innerHTML = `<div class="folder-list-error">❌ ${err.message}</div>`;
    }
}

async function browseDestTo(path) {
    const listEl = $("#destFolderList");
    listEl.innerHTML = '<div class="folder-list-loading">Loading…</div>';

    try {
        const url = `/api/browse?path=${encodeURIComponent(path)}`;
        const resp = await fetch(url);
        const data = await resp.json();
        if (data.error) { listEl.innerHTML = `<div class="folder-list-error">${data.error}</div>`; return; }

        organizeState.destBrowsePath = data.path;
        updateBreadcrumb(data.path, "destBreadcrumb", true);

        listEl.innerHTML = data.items.filter(i => i.type === "drive" || i.type === "folder").map(item => {
            const icon = item.type === "drive" ? "💿" : "📁";
            return `<div class="folder-item dir" onclick="browseDestTo('${escPath(item.path)}')">
                <span class="fi-icon">${icon}</span>
                <span class="fi-name">${item.name}</span>
                <span class="fi-arrow">→</span>
            </div>`;
        }).join("") || '<div class="folder-list-empty">📭 No subfolders</div>';

        $("#destFolderInput").value = data.path;
    } catch (err) {
        listEl.innerHTML = `<div class="folder-list-error">${err.message}</div>`;
    }
}

function escPath(p) { return p.replace(/\\/g, "\\\\").replace(/'/g, "\\'"); }

function updateBreadcrumb(path, elementId, isDest) {
    const el = $(`#${elementId}`);
    const fn = isDest ? "browseDestTo" : "browseTo";
    let html = `<span class="breadcrumb-item" onclick="${fn}('')">💻</span>`;

    if (path) {
        const sep = path.includes("\\") ? "\\" : "/";
        const parts = path.split(sep).filter(Boolean);
        let cumulative = "";
        parts.forEach((part, i) => {
            cumulative += part + sep;
            const isLast = i === parts.length - 1;
            html += `<span class="breadcrumb-sep">/</span>`;
            html += `<span class="breadcrumb-item ${isLast ? 'active' : ''}" onclick="${fn}('${escPath(cumulative)}')">${part}</span>`;
        });
    }
    el.innerHTML = html;
}

function extensionToCategory(ext) {
    const map = {
        ".jpg": "Images", ".jpeg": "Images", ".png": "Images", ".gif": "Images", ".webp": "Images", ".svg": "Images",
        ".pdf": "Documents", ".docx": "Documents", ".doc": "Documents", ".txt": "Documents", ".xlsx": "Documents", ".csv": "Documents", ".md": "Documents",
        ".mp4": "Videos", ".avi": "Videos", ".mov": "Videos", ".mkv": "Videos",
        ".mp3": "Audio", ".wav": "Audio", ".flac": "Audio",
        ".py": "Code", ".js": "Code", ".ts": "Code", ".html": "Code", ".css": "Code", ".json": "Code",
        ".zip": "Archives", ".rar": "Archives", ".tar": "Archives", ".gz": "Archives",
        ".exe": "Executables", ".msi": "Executables",
    };
    return map[ext] || "Other";
}

function extensionToEmoji(ext) {
    const cat = extensionToCategory(ext);
    return CATEGORY_EMOJI[cat] || "📎";
}

// Select source folder
function selectSourceFolder(path) {
    organizeState.selectedFolder = path;
    $("#selectedFolderPath").textContent = path;
    $("#folderSelectedBar").classList.add("selected");
}

if ($("#btnSelectFolder")) {
    $("#btnSelectFolder").addEventListener("click", async () => {
        const path = organizeState.currentBrowsePath;
        if (!path) return;
        selectSourceFolder(path);
        await previewFolder(path);
    });
}

async function previewFolder(path) {
    // Show downstream panels
    $("#folderPreviewPanel").classList.remove("hidden");
    $("#destPanel").classList.remove("hidden");
    $("#settingsPanel").classList.remove("hidden");
    $("#executePanel").classList.remove("hidden");

    // Set default destination
    const sep = path.includes("\\") ? "\\" : "/";
    const defaultDest = path + sep + "Organized";
    $("#destFolderInput").value = defaultDest;
    organizeState.destFolder = defaultDest;

    // Load preview
    $("#previewDesc").textContent = "Scanning folder contents…";
    try {
        const resp = await fetch(`/api/browse/preview?path=${encodeURIComponent(path)}`);
        const data = await resp.json();
        if (data.error) {
            $("#previewDesc").textContent = `Error: ${data.error}`;
            return;
        }
        $("#previewDesc").textContent = `Found ${data.total_files} files (${formatBytes(data.total_size)}) ready to organize:`;

        const cats = data.categories;
        const statsHtml = Object.entries(cats).map(([cat, count]) => {
            const emoji = CATEGORY_EMOJI[cat] || "📎";
            const color = CATEGORY_COLORS[cat] || CATEGORY_COLORS.Other;
            return `<div class="stat-card" style="border-left: 3px solid ${color}">
                <div class="stat-icon">${emoji}</div>
                <div class="stat-body">
                    <span class="stat-value">${count}</span>
                    <span class="stat-label">${cat}</span>
                </div>
            </div>`;
        }).join("");
        $("#previewStats").innerHTML = statsHtml;

        updateExecuteSummary();
    } catch (err) {
        $("#previewDesc").textContent = `Error scanning: ${err.message}`;
    }
}

// Dest folder browser toggle
if ($("#btnBrowseDest")) {
    $("#btnBrowseDest").addEventListener("click", () => {
        const container = $("#destBrowserContainer");
        if (container.classList.contains("hidden")) {
            container.classList.remove("hidden");
            browseDestTo(organizeState.selectedFolder || "");
        } else {
            container.classList.add("hidden");
        }
    });
}
if ($("#btnConfirmDest")) {
    $("#btnConfirmDest").addEventListener("click", () => {
        organizeState.destFolder = organizeState.destBrowsePath || "";
        $("#destFolderInput").value = organizeState.destFolder;
        $("#destBrowserContainer").classList.add("hidden");
        updateExecuteSummary();
    });
}
if ($("#btnCancelDest")) {
    $("#btnCancelDest").addEventListener("click", () => {
        $("#destBrowserContainer").classList.add("hidden");
    });
}
if ($("#destFolderInput")) {
    $("#destFolderInput").addEventListener("input", (e) => {
        organizeState.destFolder = e.target.value;
        updateExecuteSummary();
    });
}

// Rename options
$$(".rename-option").forEach(opt => {
    opt.addEventListener("click", () => {
        $$(".rename-option").forEach(o => o.classList.remove("active"));
        opt.classList.add("active");
        organizeState.renamePattern = opt.querySelector("input").value;
        updateExecuteSummary();
    });
});

// Walrus toggle
if ($("#walrusToggle")) {
    $("#walrusToggle").addEventListener("change", (e) => {
        organizeState.logToWalrus = e.target.checked;
        updateExecuteSummary();
    });
}

// ─── Categories Editor ────────────────────────────────────

async function loadCategoriesEditor() {
    try {
        const resp = await fetch("/api/config");
        const cfg = await resp.json();
        const cats = cfg.categories || {};
        organizeState.categories = { ...cats };
        renderCategoriesEditor(cats);
    } catch (e) {
        console.error("Config load error:", e);
    }
}

function renderCategoriesEditor(cats) {
    const el = $("#categoriesEditor");
    if (!el) return;

    const catEmojis = { Images: "📸", Documents: "📄", Videos: "🎬", Audio: "🎵", Code: "💻", Archives: "📦", Executables: "⚙️", Other: "📎" };

    el.innerHTML = Object.entries(cats).map(([name, exts]) => {
        const emoji = catEmojis[name] || "🏷️";
        const color = CATEGORY_COLORS[name] || CATEGORY_COLORS.Other;
        const extTags = (exts || []).map(ext =>
            `<span class="ext-tag" style="border-color:${color}" data-cat="${name}" data-ext="${ext}">${ext} <span class="ext-remove" onclick="removeExtension('${name}','${ext}')">×</span></span>`
        ).join("");
        return `<div class="category-card" style="border-left: 3px solid ${color}">
            <div class="category-header">
                <span class="category-emoji">${emoji}</span>
                <span class="category-name">${name}</span>
                <button class="btn btn-sm btn-outline" style="color:var(--accent-red);padding:2px 8px;font-size:.65rem;" onclick="removeCategory('${name}')">🗑️</button>
            </div>
            <div class="category-extensions">${extTags}</div>
            <div class="category-add-ext">
                <input type="text" class="input input-sm" placeholder="Add .ext" id="addExt_${name}" onkeydown="if(event.key==='Enter')addExtension('${name}')" />
                <button class="btn btn-sm btn-outline" onclick="addExtension('${name}')">+</button>
            </div>
        </div>`;
    }).join("");
}

function addExtension(category) {
    const input = $(`#addExt_${category}`);
    if (!input) return;
    let ext = input.value.trim().toLowerCase();
    if (!ext) return;
    if (!ext.startsWith(".")) ext = "." + ext;

    if (!organizeState.categories[category]) organizeState.categories[category] = [];
    if (!organizeState.categories[category].includes(ext)) {
        organizeState.categories[category].push(ext);
    }
    input.value = "";
    renderCategoriesEditor(organizeState.categories);
    saveCategoriesDebounced();
}

function removeExtension(category, ext) {
    if (!organizeState.categories[category]) return;
    organizeState.categories[category] = organizeState.categories[category].filter(e => e !== ext);
    renderCategoriesEditor(organizeState.categories);
    saveCategoriesDebounced();
}

function removeCategory(name) {
    if (!confirm(`Remove category "${name}"?`)) return;
    delete organizeState.categories[name];
    renderCategoriesEditor(organizeState.categories);
    saveCategoriesDebounced();
}

if ($("#btnAddCategory")) {
    $("#btnAddCategory").addEventListener("click", () => {
        const name = ($("#newCategoryName").value || "").trim();
        const extsRaw = ($("#newCategoryExts").value || "").trim();
        if (!name) { alert("Enter a category name"); return; }

        const exts = extsRaw.split(",").map(e => {
            let ext = e.trim().toLowerCase();
            if (ext && !ext.startsWith(".")) ext = "." + ext;
            return ext;
        }).filter(Boolean);

        organizeState.categories[name] = exts;
        $("#newCategoryName").value = "";
        $("#newCategoryExts").value = "";
        renderCategoriesEditor(organizeState.categories);
        saveCategoriesDebounced();
    });
}

let _saveCatTimer = null;
function saveCategoriesDebounced() {
    clearTimeout(_saveCatTimer);
    _saveCatTimer = setTimeout(async () => {
        try {
            await fetch("/api/config/categories", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ categories: organizeState.categories }),
            });
        } catch (e) { console.error("Save categories error:", e); }
    }, 800);
}

// ─── Execute Summary ────────────────────────────────────────

function updateExecuteSummary() {
    const el = $("#executeSummary");
    if (!el) return;

    const src = organizeState.selectedFolder || "(not selected)";
    const dst = organizeState.destFolder || "(auto)";
    const pattern = organizeState.renamePattern;
    const walrus = organizeState.logToWalrus ? "✅ Enabled" : "❌ Disabled";

    el.innerHTML = `
        <div class="summary-row"><span class="summary-label">📂 Source:</span> <span class="summary-value">${src}</span></div>
        <div class="summary-row"><span class="summary-label">📦 Destination:</span> <span class="summary-value">${dst}</span></div>
        <div class="summary-row"><span class="summary-label">📝 Naming:</span> <span class="summary-value">${pattern}</span></div>
        <div class="summary-row"><span class="summary-label">🦭 Walrus Log:</span> <span class="summary-value">${walrus}</span></div>
    `;
}

// ─── Preview & Execute ──────────────────────────────────────

if ($("#btnPreviewOrganize")) {
    $("#btnPreviewOrganize").addEventListener("click", async () => {
        if (!organizeState.selectedFolder) { alert("Select a folder first"); return; }
        await runOrganize(true);
    });
}

if ($("#btnExecuteOrganize")) {
    $("#btnExecuteOrganize").addEventListener("click", async () => {
        if (!organizeState.selectedFolder) { alert("Select a folder first"); return; }
        if (!confirm("This will move files into organized folders. Continue?")) return;
        await runOrganize(false);
    });
}

async function runOrganize(dryRun) {
    const btn = dryRun ? $("#btnPreviewOrganize") : $("#btnExecuteOrganize");
    const origText = btn.textContent;
    btn.disabled = true;
    btn.textContent = "⏳ Working…";

    try {
        const payload = {
            folder: organizeState.selectedFolder,
            destination: organizeState.destFolder || "",
            rename_pattern: organizeState.renamePattern,
            log_to_walrus: organizeState.logToWalrus,
            dry_run: dryRun,
        };
        if (organizeState.categories) {
            payload.categories = organizeState.categories;
        }

        const resp = await fetch("/api/organize/run", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await resp.json();

        if (data.error) { alert("Error: " + data.error); return; }

        // Show results
        const resultsEl = $("#organizeResults");
        resultsEl.classList.remove("hidden");

        if (dryRun) {
            $("#resultsTitle").textContent = "👁️ Preview — No files were moved";
        } else {
            $("#resultsTitle").textContent = `✅ Organized ${data.files_moved} files`;
        }

        // Stats
        const statsHtml = `
            <div class="stat-card accent-blue"><div class="stat-icon">📁</div><div class="stat-body"><span class="stat-value">${data.files_processed}</span><span class="stat-label">Files Scanned</span></div></div>
            <div class="stat-card accent-green"><div class="stat-icon">✅</div><div class="stat-body"><span class="stat-value">${data.files_moved || 0}</span><span class="stat-label">${dryRun ? "Would Move" : "Moved"}</span></div></div>
            <div class="stat-card accent-orange"><div class="stat-icon">💾</div><div class="stat-body"><span class="stat-value">${formatBytes(data.total_size || 0)}</span><span class="stat-label">Total Size</span></div></div>
            <div class="stat-card accent-purple"><div class="stat-icon">📂</div><div class="stat-body"><span class="stat-value">${Object.keys(data.categories_summary || {}).length}</span><span class="stat-label">Categories</span></div></div>
        `;
        $("#resultsStats").innerHTML = statsHtml;

        // Walrus result
        if (data.walrus_blob_id) {
            const walrusEl = $("#walrusResult");
            walrusEl.classList.remove("hidden");
            $("#walrusBlobResult").textContent = data.walrus_blob_id;
            if ($("#btnExploreWalrusResult")) {
                $("#btnExploreWalrusResult").onclick = () => exploreBlobFromHistory(data.walrus_blob_id);
            }
        } else {
            $("#walrusResult").classList.add("hidden");
        }

        // Actions table
        const actions = data.actions || [];
        const tbody = $("#resultsTable tbody");
        tbody.innerHTML = actions.map((a, i) => {
            const cat = a.category || "–";
            const emoji = CATEGORY_EMOJI[cat] || "📎";
            const statusBadge = a.action === "error"
                ? '<span class="activity-badge badge-error">ERROR</span>'
                : a.action === "would_move"
                ? '<span class="activity-badge badge-skipped">PREVIEW</span>'
                : '<span class="activity-badge badge-moved">MOVED</span>';
            return `<tr>
                <td>${i + 1}</td>
                <td>${emoji} ${a.file || "–"}</td>
                <td>${cat}</td>
                <td>${formatBytes(a.size || 0)}</td>
                <td class="mono" style="font-size:.72rem;">${a.new_name || a.file || "–"}</td>
                <td>${statusBadge}</td>
            </tr>`;
        }).join("");

        // Refresh preview
        if (!dryRun && organizeState.selectedFolder) {
            await previewFolder(organizeState.selectedFolder);
        }

    } catch (err) {
        alert("Failed: " + err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = origText;
    }
}


// ═══════════════════════════════════════════════════════════
//  BOOT
// ═══════════════════════════════════════════════════════════

document.addEventListener("DOMContentLoaded", () => {
    pollAgentStatus();
    loadDashboardData();
    loadHistory();
    loadVaultFiles();
    loadWorkflowRules();
    loadWorkflowExecutions();
    loadAnchors();
    checkShareLink();
    // Poll agent status every 3s
    setInterval(pollAgentStatus, 3000);
});
