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

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import requests as http_requests

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


# ──────────────────────────── Run ──────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    print(f"\n🦭 Deepurge Dashboard running at http://localhost:{port}")
    print(f"   Agent root: {AGENT_ROOT}")
    print(f"   Python:     {PYTHON}\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
