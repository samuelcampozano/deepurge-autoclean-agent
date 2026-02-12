"""
Deepurge Dashboard - Web UI + Agent Controller
Serves a modern dashboard, proxies Walrus blobs, and manages the agent process.

Author: Samuel Campozano Lopez
Project: x OpenClaw Agent Hackathon
"""
import os
import sys
import json
import sqlite3
import signal
import subprocess
import threading
from collections import deque
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS
import requests as http_requests

# Add parent dir so we can import vault / workflows / sui_anchor
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vault import DeepurgeVault, DeepurgeVaultDemo
from workflows import WorkflowEngine
from sui_anchor import SuiAnchor

app = Flask(__name__)
CORS(app)

# ──────────────────────────── Config ───────────────────────────

WALRUS_AGGREGATOR = os.environ.get(
    "WALRUS_AGGREGATOR",
    "https://aggregator.walrus-testnet.walrus.space",
)

AGENT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = AGENT_ROOT / "actions.db"
BLOB_HISTORY_PATH = AGENT_ROOT / "blob_history.json"
CONFIG_PATH = AGENT_ROOT / "config.json"
PYTHON = sys.executable


def _get_watch_folder():
    """Read the watch folder from config.json (works in Docker & locally)."""
    try:
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        folder = cfg["folders"]["watch_folder"]
        return str(Path(folder).expanduser())
    except Exception:
        return str(Path.home() / "Downloads")


def _load_config():
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


# ──────────────────────────── Singletons ───────────────────

_cfg = _load_config()
_walrus_cfg = _cfg.get("walrus", {})
_vault_cfg = _cfg.get("vault", {})
_anchor_cfg = _cfg.get("sui_anchor", {})

try:
    vault = DeepurgeVault(
        aggregator_url=_walrus_cfg.get("aggregator_url"),
        publisher_url=_walrus_cfg.get("publisher_url"),
        epochs=_vault_cfg.get("epochs", 10),
    )
except Exception:
    vault = DeepurgeVaultDemo()

workflow_engine = WorkflowEngine(organized_folder=Path(_get_watch_folder()).parent / "Organized")

sui_anchor = SuiAnchor(
    rpc_url=_anchor_cfg.get("rpc_url"),
    package_id=_anchor_cfg.get("package_id") or None,
    registry_id=_anchor_cfg.get("registry_id") or None,
    signer_address=_anchor_cfg.get("signer_address") or None,
)


# ──────────────────────────── Process Manager ──────────────────

class ProcessManager:
    """Manages the agent & demo-generator as child processes."""

    def __init__(self):
        self.agent_proc = None
        self.demo_proc = None
        self.log_buffer = deque(maxlen=500)
        self._lock = threading.Lock()
        self.agent_started_at = None

    # -- helpers ---------------------------------------------------

    def _read_stream(self, proc, label):
        """Background thread: reads stdout+stderr into log buffer."""
        try:
            for raw_line in iter(proc.stdout.readline, ""):
                line = raw_line.rstrip("\n\r")
                if line:
                    ts = datetime.utcnow().strftime("%H:%M:%S")
                    with self._lock:
                        self.log_buffer.append(f"[{ts}] {line}")
        except Exception:
            pass

    def _spawn(self, cmd, label):
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        kwargs = dict(
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            cwd=str(AGENT_ROOT),
            env=env,
        )
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        proc = subprocess.Popen(cmd, **kwargs)
        t = threading.Thread(target=self._read_stream, args=(proc, label), daemon=True)
        t.start()
        return proc

    # -- agent -----------------------------------------------------

    def start_agent(self):
        if self.agent_proc and self.agent_proc.poll() is None:
            return {"status": "already_running", "pid": self.agent_proc.pid}

        self.agent_proc = self._spawn([PYTHON, "agent.py"], "AGENT")
        self.agent_started_at = datetime.utcnow().isoformat() + "Z"
        with self._lock:
            self.log_buffer.append(f"[SYS] Agent started (PID {self.agent_proc.pid})")
        return {"status": "started", "pid": self.agent_proc.pid}

    def stop_agent(self):
        if not self.agent_proc or self.agent_proc.poll() is not None:
            return {"status": "not_running"}

        pid = self.agent_proc.pid
        try:
            if os.name == "nt":
                os.kill(pid, signal.CTRL_BREAK_EVENT)
            else:
                self.agent_proc.send_signal(signal.SIGINT)
            self.agent_proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.agent_proc.kill()
        except Exception:
            self.agent_proc.kill()

        with self._lock:
            self.log_buffer.append(f"[SYS] Agent stopped (PID {pid})")
        self.agent_started_at = None
        return {"status": "stopped", "pid": pid}

    def agent_status(self):
        running = self.agent_proc is not None and self.agent_proc.poll() is None
        return {
            "running": running,
            "pid": self.agent_proc.pid if running else None,
            "started_at": self.agent_started_at if running else None,
        }

    # -- demo generator --------------------------------------------

    def generate_demo(self, count=50):
        if self.demo_proc and self.demo_proc.poll() is None:
            return {"status": "already_running"}

        with self._lock:
            self.log_buffer.append(f"[SYS] Generating {count} demo files...")
        target_folder = _get_watch_folder()
        self.demo_proc = self._spawn(
            [PYTHON, "demo_generator.py", target_folder, str(count)],
            "DEMO",
        )
        threading.Thread(target=self._wait_demo, daemon=True).start()
        return {"status": "generating", "count": count}

    def _wait_demo(self):
        if self.demo_proc:
            self.demo_proc.wait()
            with self._lock:
                self.log_buffer.append("[SYS] Demo file generation complete ✅")

    # -- logs ------------------------------------------------------

    def get_logs(self, since=0):
        with self._lock:
            all_lines = list(self.log_buffer)
        if since >= len(all_lines):
            return []
        return all_lines[since:]


pm = ProcessManager()


# ──────────────────────────── Pages ────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# ──────────────────────────── Agent Control API ────────────────

@app.route("/api/agent/start", methods=["POST"])
def api_agent_start():
    return jsonify(pm.start_agent())

@app.route("/api/agent/stop", methods=["POST"])
def api_agent_stop():
    return jsonify(pm.stop_agent())

@app.route("/api/agent/status")
def api_agent_status():
    return jsonify(pm.agent_status())

@app.route("/api/agent/logs")
def api_agent_logs():
    since = request.args.get("since", 0, type=int)
    lines = pm.get_logs(since)
    return jsonify({"lines": lines, "total": since + len(lines)})

@app.route("/api/demo/generate", methods=["POST"])
def api_demo_generate():
    count = 50
    if request.is_json and request.json:
        count = request.json.get("count", 50)
    return jsonify(pm.generate_demo(count))


# ──────────────────────────── Walrus Proxy ─────────────────────

@app.route("/api/blob/<path:blob_id>")
def proxy_blob(blob_id):
    try:
        url = f"{WALRUS_AGGREGATOR}/v1/blobs/{blob_id}"
        resp = http_requests.get(url, timeout=30)
        if resp.status_code == 200:
            try:
                return jsonify(resp.json())
            except ValueError:
                return jsonify({"error": "Blob is not JSON", "raw": resp.text[:2000]}), 200
        return jsonify({"error": f"Walrus returned HTTP {resp.status_code}"}), resp.status_code
    except http_requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 502


@app.route("/api/blob-history")
def blob_history():
    if BLOB_HISTORY_PATH.exists():
        with open(BLOB_HISTORY_PATH, "r") as f:
            return jsonify(json.load(f))
    return jsonify({"blobs": []})


# ──────────────────────────── Database API ─────────────────────

def _empty_stats():
    return {
        "stats": {"total_files_processed": 0, "total_bytes_processed": 0},
        "categories": [],
        "recent_actions": [],
        "walrus_uploads": [],
        "daily_reports": [],
    }

@app.route("/api/db-stats")
def db_stats():
    if not DB_PATH.exists():
        return jsonify(_empty_stats())
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT total_files_processed, total_bytes_processed FROM statistics WHERE id=1")
        row = cur.fetchone()
        stats = dict(row) if row else _empty_stats()["stats"]

        cur.execute("SELECT category, COUNT(*) as count, SUM(file_size) as total_size FROM actions GROUP BY category ORDER BY count DESC")
        categories = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT * FROM actions ORDER BY id DESC LIMIT 50")
        recent = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT * FROM walrus_uploads ORDER BY id DESC LIMIT 20")
        uploads = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT * FROM daily_reports ORDER BY report_date DESC LIMIT 10")
        reports = [dict(r) for r in cur.fetchall()]

        conn.close()
        return jsonify({
            "stats": stats,
            "categories": categories,
            "recent_actions": recent,
            "walrus_uploads": uploads,
            "daily_reports": reports,
        })
    except Exception:
        return jsonify(_empty_stats())


@app.route("/api/db-walrus-blobs")
def db_walrus_blobs():
    if not DB_PATH.exists():
        return jsonify({"blobs": []})
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT blob_id, timestamp, content_type, action_count, data_summary FROM walrus_uploads ORDER BY id DESC")
        blobs = [dict(r) for r in cur.fetchall()]
        conn.close()
        return jsonify({"blobs": blobs})
    except Exception:
        return jsonify({"blobs": []})


# ──────────────────────────── Vault API (Path 2) ───────────────

@app.route("/api/vault/upload", methods=["POST"])
def vault_upload():
    """Upload a file to the Deepurge Vault (encrypted → Walrus)."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400

    # Save to temp location
    tmp_dir = AGENT_ROOT / "_vault_tmp"
    tmp_dir.mkdir(exist_ok=True)
    tmp_path = tmp_dir / f.filename
    f.save(str(tmp_path))

    try:
        manifest = vault.store(tmp_path)

        # Generate share token & link
        share_token = vault.create_share_token(
            manifest["blob_id"], manifest["key_hex"],
            manifest["nonce_hex"], manifest["file_name"],
        )
        share_link = vault.generate_share_link(
            manifest["blob_id"], manifest["key_hex"],
            manifest["nonce_hex"], manifest["file_name"],
        )
        manifest["share_token"] = share_token
        manifest["share_link"] = share_link

        # Log to DB
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO vault_files (
                    timestamp, file_name, original_path, blob_id, key_hex,
                    nonce_hex, file_size, encrypted_size, mime_type, sha256,
                    walrus_url, share_token, folder_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                manifest["uploaded_at"], manifest["file_name"], str(tmp_path),
                manifest["blob_id"], manifest["key_hex"], manifest["nonce_hex"],
                manifest["file_size"], manifest["encrypted_size"],
                manifest.get("mime_type", ""), manifest.get("sha256", ""),
                manifest.get("walrus_url", ""), share_token, "",
            ))
            conn.commit()
            conn.close()
        except Exception:
            pass

        return jsonify(manifest)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        tmp_path.unlink(missing_ok=True)


@app.route("/api/vault/upload-folder", methods=["POST"])
def vault_upload_folder():
    """Upload all files in a folder path to vault."""
    data = request.get_json(silent=True) or {}
    folder_path = data.get("folder_path", "")
    if not folder_path or not Path(folder_path).is_dir():
        return jsonify({"error": "Invalid folder path"}), 400

    try:
        manifest = vault.store_folder(Path(folder_path))

        # Log folder to DB
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO vault_folders (timestamp, folder_name, file_count, root_hash, key_hex, manifest_blob_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                manifest["uploaded_at"], manifest["folder_name"],
                manifest["file_count"], manifest["root_hash"],
                manifest["key_hex"], manifest.get("manifest_blob_id", ""),
            ))
            conn.commit()
            conn.close()
        except Exception:
            pass

        return jsonify(manifest)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/vault/download", methods=["POST"])
def vault_download():
    """Download and decrypt a file from vault."""
    data = request.get_json(silent=True) or {}
    blob_id = data.get("blob_id", "")
    key_hex = data.get("key_hex", "")
    nonce_hex = data.get("nonce_hex", "")
    file_name = data.get("file_name", "downloaded_file")

    if not all([blob_id, key_hex, nonce_hex]):
        return jsonify({"error": "blob_id, key_hex, nonce_hex required"}), 400

    try:
        plaintext = vault.retrieve(blob_id, key_hex, nonce_hex)
        import io
        return send_file(
            io.BytesIO(plaintext),
            download_name=file_name,
            as_attachment=True,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/vault/files")
def vault_files():
    """List vault files from DB."""
    if not DB_PATH.exists():
        return jsonify({"files": []})
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM vault_files ORDER BY id DESC LIMIT 100")
        files = [dict(r) for r in cur.fetchall()]
        conn.close()
        return jsonify({"files": files})
    except Exception:
        return jsonify({"files": []})


@app.route("/api/vault/folders")
def vault_folders():
    """List vault folders from DB."""
    if not DB_PATH.exists():
        return jsonify({"folders": []})
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM vault_folders ORDER BY id DESC LIMIT 50")
        folders = [dict(r) for r in cur.fetchall()]
        conn.close()
        return jsonify({"folders": folders})
    except Exception:
        return jsonify({"folders": []})


@app.route("/api/vault/share", methods=["POST"])
def vault_share():
    """Generate a share link for a vault file."""
    data = request.get_json(silent=True) or {}
    blob_id = data.get("blob_id", "")
    key_hex = data.get("key_hex", "")
    nonce_hex = data.get("nonce_hex", "")
    file_name = data.get("file_name", "")

    if not all([blob_id, key_hex, nonce_hex]):
        return jsonify({"error": "Missing parameters"}), 400

    token = vault.create_share_token(blob_id, key_hex, nonce_hex, file_name)
    link = vault.generate_share_link(blob_id, key_hex, nonce_hex, file_name)
    return jsonify({"share_token": token, "share_link": link})


@app.route("/vault/share")
def vault_share_page():
    """Serve the share page (decryption happens client-side via JS)."""
    return render_template("index.html")


# ──────────────────────────── Workflow API (Path 3) ────────────

@app.route("/api/workflows/rules")
def workflows_rules():
    """Get all workflow rules."""
    return jsonify({"rules": workflow_engine.get_rules()})


@app.route("/api/workflows/rules", methods=["POST"])
def workflows_add_rule():
    """Add a new workflow rule."""
    data = request.get_json(silent=True) or {}
    required = ["name", "trigger_type", "trigger_value", "actions"]
    if not all(k in data for k in required):
        return jsonify({"error": "Missing fields: name, trigger_type, trigger_value, actions"}), 400

    workflow_engine.add_rule(data)
    return jsonify({"status": "added", "rule": data})


@app.route("/api/workflows/rules/<name>", methods=["DELETE"])
def workflows_delete_rule(name):
    """Delete a workflow rule."""
    workflow_engine.remove_rule(name)
    return jsonify({"status": "deleted", "name": name})


@app.route("/api/workflows/rules/<name>/toggle", methods=["POST"])
def workflows_toggle_rule(name):
    """Toggle a workflow rule on/off."""
    data = request.get_json(silent=True) or {}
    enabled = data.get("enabled", True)
    workflow_engine.toggle_rule(name, enabled)
    return jsonify({"status": "toggled", "name": name, "enabled": enabled})


@app.route("/api/workflows/executions")
def workflows_executions():
    """Get recent workflow execution log."""
    if not DB_PATH.exists():
        return jsonify({"executions": []})
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM workflow_executions ORDER BY id DESC LIMIT 100")
        execs = [dict(r) for r in cur.fetchall()]
        conn.close()
        return jsonify({"executions": execs})
    except Exception:
        return jsonify({"executions": []})


# ──────────────────────────── Sui Anchor API (Path 3) ──────────

@app.route("/api/anchors")
def anchors_list():
    """List all Sui anchor entries."""
    if not DB_PATH.exists():
        return jsonify({"anchors": sui_anchor.get_local_anchors()})
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM sui_anchors ORDER BY id DESC LIMIT 50")
        anchors = [dict(r) for r in cur.fetchall()]
        conn.close()
        # Merge with local ledger if DB is empty
        if not anchors:
            anchors = sui_anchor.get_local_anchors()
        return jsonify({"anchors": anchors})
    except Exception:
        return jsonify({"anchors": sui_anchor.get_local_anchors()})


@app.route("/api/anchors/verify", methods=["POST"])
def anchors_verify():
    """Verify a root hash for a given date."""
    data = request.get_json(silent=True) or {}
    date = data.get("date", "")
    root_hash = data.get("root_hash", "")
    if not date or not root_hash:
        return jsonify({"error": "date and root_hash required"}), 400

    result = sui_anchor.verify_on_chain(date, root_hash)
    return jsonify(result)


# ──────────────────────────── Insights API ─────────────────────

# Research-backed estimate: manually sorting a file takes ~30 seconds on average.
# This includes: locating the file, deciding on a category, creating/finding the
# target folder, renaming with a timestamp, and dragging it.  This is a conservative
# figure — studies on desktop file management (Bergman et al., 2010) show users
# spend 1-2 minutes per file when they also have to decide where to put it.
AVG_SECONDS_PER_FILE_MANUAL = 30

@app.route("/api/insights")
def insights():
    """Return data-driven insights computed from real database metrics."""
    result = {
        "time_saved_seconds": 0,
        "time_saved_display": "0 min",
        "walrus_storage_bytes": 0,
        "walrus_storage_display": "0 B",
        "total_blobs": 0,
        "oldest_blob": None,
        "newest_blob": None,
        "top_category": None,
        "top_category_pct": 0,
        "duplicates_prevented": 0,
        "duplicates_saved_bytes": 0,
        "methodology": (
            "Time saved is calculated at 30 seconds per file — a conservative "
            "estimate based on the average time a person spends manually locating, "
            "categorising, renaming and moving a single file on their desktop."
        ),
    }

    if not DB_PATH.exists():
        return jsonify(result)

    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Total files processed
        cur.execute("SELECT total_files_processed, total_bytes_processed FROM statistics WHERE id=1")
        row = cur.fetchone()
        total_files = row["total_files_processed"] if row else 0
        total_bytes = row["total_bytes_processed"] if row else 0

        # Time saved
        seconds_saved = total_files * AVG_SECONDS_PER_FILE_MANUAL
        result["time_saved_seconds"] = seconds_saved
        if seconds_saved < 60:
            result["time_saved_display"] = f"{seconds_saved} sec"
        elif seconds_saved < 3600:
            result["time_saved_display"] = f"{seconds_saved / 60:.1f} min"
        else:
            result["time_saved_display"] = f"{seconds_saved / 3600:.1f} hrs"

        # Top category
        cur.execute("SELECT category, COUNT(*) as cnt FROM actions GROUP BY category ORDER BY cnt DESC LIMIT 1")
        top = cur.fetchone()
        if top and total_files > 0:
            result["top_category"] = top["category"]
            result["top_category_pct"] = round(top["cnt"] / total_files * 100)

        # Duplicates prevented (actions with status 'skipped' or action_type 'SKIPPED')
        cur.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(file_size),0) as saved FROM actions WHERE action_type='SKIPPED' OR status='skipped'")
        dup = cur.fetchone()
        result["duplicates_prevented"] = dup["cnt"] if dup else 0
        result["duplicates_saved_bytes"] = dup["saved"] if dup else 0

        # Walrus blockchain metrics
        cur.execute("SELECT COUNT(*) as cnt FROM walrus_uploads")
        result["total_blobs"] = cur.fetchone()["cnt"]

        cur.execute("SELECT timestamp FROM walrus_uploads ORDER BY id ASC LIMIT 1")
        oldest = cur.fetchone()
        result["oldest_blob"] = oldest["timestamp"] if oldest else None

        cur.execute("SELECT timestamp FROM walrus_uploads ORDER BY id DESC LIMIT 1")
        newest = cur.fetchone()
        result["newest_blob"] = newest["timestamp"] if newest else None

        # Walrus storage estimate: each action averages ~250 bytes of JSON
        cur.execute("SELECT COALESCE(SUM(action_count),0) as total_actions FROM walrus_uploads")
        total_actions = cur.fetchone()["total_actions"]
        result["walrus_storage_bytes"] = total_actions * 250
        ws = result["walrus_storage_bytes"]
        if ws < 1024:
            result["walrus_storage_display"] = f"{ws} B"
        elif ws < 1024 * 1024:
            result["walrus_storage_display"] = f"{ws/1024:.1f} KB"
        else:
            result["walrus_storage_display"] = f"{ws/1024/1024:.1f} MB"

        conn.close()
    except Exception:
        pass

    return jsonify(result)


# ──────────────────────────── Run ──────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    print(f"\n🦭 Deepurge Dashboard running at http://localhost:{port}")
    print(f"   Agent root: {AGENT_ROOT}")
    print(f"   Python:     {PYTHON}\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
