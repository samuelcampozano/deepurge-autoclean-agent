"""
Database Module for Deepurge AutoClean Agent
SQLite operations for logging file actions

Author: Samuel Campozano Lopez
Project: Sui Hackathon 2026
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager


class Database:
    """SQLite database handler for action logging"""
    
    def __init__(self, db_path: str = "actions.db"):
        self.db_path = Path(db_path)
        self._init_database()
    
    def _init_database(self):
        """Initialize database with required tables"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Main actions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    original_path TEXT NOT NULL,
                    new_path TEXT,
                    file_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    file_size INTEGER DEFAULT 0,
                    file_hash TEXT,
                    walrus_blob_id TEXT,
                    status TEXT DEFAULT 'completed',
                    error_message TEXT
                )
            """)
            
            # Walrus uploads table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS walrus_uploads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    blob_id TEXT NOT NULL,
                    content_type TEXT,
                    action_count INTEGER,
                    data_summary TEXT,
                    status TEXT DEFAULT 'success'
                )
            """)
            
            # Daily reports table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_date TEXT UNIQUE NOT NULL,
                    total_files INTEGER DEFAULT 0,
                    categories_summary TEXT,
                    walrus_blob_id TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Statistics cache table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS statistics (
                    id INTEGER PRIMARY KEY,
                    total_files_processed INTEGER DEFAULT 0,
                    total_bytes_processed INTEGER DEFAULT 0,
                    last_updated TEXT
                )
            """)

            # ── Vault tables (Path 2) ──────────────────────
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vault_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    original_path TEXT,
                    blob_id TEXT NOT NULL,
                    key_hex TEXT NOT NULL,
                    nonce_hex TEXT NOT NULL,
                    file_size INTEGER DEFAULT 0,
                    encrypted_size INTEGER DEFAULT 0,
                    mime_type TEXT,
                    sha256 TEXT,
                    walrus_url TEXT,
                    share_token TEXT,
                    folder_name TEXT,
                    status TEXT DEFAULT 'stored'
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vault_folders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    folder_name TEXT NOT NULL,
                    file_count INTEGER DEFAULT 0,
                    root_hash TEXT,
                    key_hex TEXT NOT NULL,
                    manifest_blob_id TEXT,
                    status TEXT DEFAULT 'stored'
                )
            """)

            # ── Workflow tables (Path 3) ───────────────────
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workflow_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    trigger_type TEXT NOT NULL,
                    trigger_value TEXT NOT NULL,
                    actions_json TEXT NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workflow_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    rule_name TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    file_path TEXT,
                    actions_taken TEXT,
                    status TEXT DEFAULT 'completed'
                )
            """)

            # ── Sui anchor ledger table ────────────────────
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sui_anchors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT UNIQUE NOT NULL,
                    root_hash TEXT NOT NULL,
                    tx_digest TEXT,
                    source TEXT DEFAULT 'local_ledger',
                    report_summary TEXT,
                    anchored_at TEXT NOT NULL
                )
            """)

            # Initialize statistics row if not exists
            cursor.execute("""
                INSERT OR IGNORE INTO statistics (id, total_files_processed, total_bytes_processed, last_updated)
                VALUES (1, 0, 0, ?)
            """, (datetime.utcnow().isoformat(),))
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def log_action(
        self,
        action_type: str,
        original_path: str,
        file_name: str,
        category: str,
        new_path: Optional[str] = None,
        file_size: int = 0,
        file_hash: Optional[str] = None,
        walrus_blob_id: Optional[str] = None,
        status: str = "completed",
        error_message: Optional[str] = None
    ) -> int:
        """
        Log a file action to the database
        
        Returns:
            The ID of the inserted record
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO actions (
                    timestamp, action_type, original_path, new_path, file_name,
                    category, file_size, file_hash, walrus_blob_id, status, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.utcnow().isoformat() + "Z",
                action_type,
                original_path,
                new_path,
                file_name,
                category,
                file_size,
                file_hash,
                walrus_blob_id,
                status,
                error_message
            ))
            
            # Update statistics
            cursor.execute("""
                UPDATE statistics 
                SET total_files_processed = total_files_processed + 1,
                    total_bytes_processed = total_bytes_processed + ?,
                    last_updated = ?
                WHERE id = 1
            """, (file_size, datetime.utcnow().isoformat()))
            
            conn.commit()
            return cursor.lastrowid
    
    def update_walrus_blob_id(self, action_id: int, blob_id: str):
        """Update the Walrus blob ID for an action"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE actions SET walrus_blob_id = ? WHERE id = ?
            """, (blob_id, action_id))
            conn.commit()
    
    def log_walrus_upload(
        self,
        blob_id: str,
        content_type: str,
        action_count: int,
        data_summary: Dict[str, Any],
        status: str = "success"
    ) -> int:
        """Log a Walrus upload event"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO walrus_uploads (
                    timestamp, blob_id, content_type, action_count, data_summary, status
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                datetime.utcnow().isoformat() + "Z",
                blob_id,
                content_type,
                action_count,
                json.dumps(data_summary),
                status
            ))
            conn.commit()
            return cursor.lastrowid
    
    def get_pending_actions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get actions that haven't been uploaded to Walrus yet"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM actions 
                WHERE walrus_blob_id IS NULL AND status = 'completed'
                ORDER BY timestamp ASC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_action_count(self) -> int:
        """Get total number of actions without Walrus upload"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as count FROM actions 
                WHERE walrus_blob_id IS NULL AND status = 'completed'
            """)
            return cursor.fetchone()['count']
    
    def get_recent_actions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get most recent actions"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM actions 
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get overall statistics"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get basic stats
            cursor.execute("SELECT * FROM statistics WHERE id = 1")
            stats = dict(cursor.fetchone())
            
            # Get category breakdown
            cursor.execute("""
                SELECT category, COUNT(*) as count, SUM(file_size) as total_size
                FROM actions
                WHERE status = 'completed'
                GROUP BY category
                ORDER BY count DESC
            """)
            stats['categories'] = [dict(row) for row in cursor.fetchall()]
            
            # Get Walrus upload stats
            cursor.execute("SELECT COUNT(*) as count FROM walrus_uploads WHERE status = 'success'")
            stats['walrus_uploads'] = cursor.fetchone()['count']
            
            # Get today's stats
            today = datetime.utcnow().strftime('%Y-%m-%d')
            cursor.execute("""
                SELECT COUNT(*) as count FROM actions 
                WHERE timestamp LIKE ? AND status = 'completed'
            """, (f"{today}%",))
            stats['today_count'] = cursor.fetchone()['count']
            
            return stats
    
    def get_daily_summary(self, date: Optional[str] = None) -> Dict[str, Any]:
        """Get summary for a specific date"""
        if date is None:
            date = datetime.utcnow().strftime('%Y-%m-%d')
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_files,
                    SUM(file_size) as total_size,
                    category,
                    COUNT(*) as category_count
                FROM actions
                WHERE timestamp LIKE ? AND status = 'completed'
                GROUP BY category
            """, (f"{date}%",))
            
            rows = cursor.fetchall()
            
            categories = {}
            total_files = 0
            total_size = 0
            
            for row in rows:
                categories[row['category']] = row['category_count']
                total_files += row['category_count']
                if row['total_size']:
                    total_size += row['total_size']
            
            return {
                'date': date,
                'total_files': total_files,
                'total_size': total_size,
                'categories': categories
            }
    
    def save_daily_report(
        self,
        report_date: str,
        total_files: int,
        categories_summary: Dict[str, int],
        walrus_blob_id: Optional[str] = None
    ):
        """Save daily report"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO daily_reports 
                (report_date, total_files, categories_summary, walrus_blob_id, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                report_date,
                total_files,
                json.dumps(categories_summary),
                walrus_blob_id,
                datetime.utcnow().isoformat() + "Z"
            ))
            conn.commit()
    
    def file_hash_exists(self, file_hash: str) -> bool:
        """Check if a file with the same hash already exists"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as count FROM actions 
                WHERE file_hash = ? AND status = 'completed'
            """, (file_hash,))
            return cursor.fetchone()['count'] > 0
    
    def mark_actions_uploaded(self, action_ids: List[int], blob_id: str):
        """Mark multiple actions as uploaded to Walrus"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ','.join('?' * len(action_ids))
            cursor.execute(f"""
                UPDATE actions 
                SET walrus_blob_id = ?
                WHERE id IN ({placeholders})
            """, [blob_id] + action_ids)
            conn.commit()

    # ── Vault Methods (Path 2) ────────────────────────────

    def log_vault_file(
        self,
        file_name: str,
        original_path: str,
        blob_id: str,
        key_hex: str,
        nonce_hex: str,
        file_size: int = 0,
        encrypted_size: int = 0,
        mime_type: str = "",
        sha256: str = "",
        walrus_url: str = "",
        share_token: str = "",
        folder_name: str = "",
    ) -> int:
        """Log a vault file entry."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO vault_files (
                    timestamp, file_name, original_path, blob_id, key_hex,
                    nonce_hex, file_size, encrypted_size, mime_type, sha256,
                    walrus_url, share_token, folder_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.utcnow().isoformat() + "Z",
                file_name, original_path, blob_id, key_hex,
                nonce_hex, file_size, encrypted_size, mime_type, sha256,
                walrus_url, share_token, folder_name,
            ))
            conn.commit()
            return cursor.lastrowid

    def log_vault_folder(
        self,
        folder_name: str,
        file_count: int,
        root_hash: str,
        key_hex: str,
        manifest_blob_id: str = "",
    ) -> int:
        """Log a vault folder sync."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO vault_folders (
                    timestamp, folder_name, file_count, root_hash,
                    key_hex, manifest_blob_id
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                datetime.utcnow().isoformat() + "Z",
                folder_name, file_count, root_hash, key_hex, manifest_blob_id,
            ))
            conn.commit()
            return cursor.lastrowid

    def get_vault_files(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get vault file entries."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM vault_files ORDER BY id DESC LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_vault_folders(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get vault folder entries."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM vault_folders ORDER BY id DESC LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    # ── Workflow Methods (Path 3) ─────────────────────────

    def save_workflow_rule(
        self,
        name: str,
        trigger_type: str,
        trigger_value: str,
        actions_json: str,
        enabled: bool = True,
    ) -> int:
        """Save or update a workflow rule."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO workflow_rules
                    (name, trigger_type, trigger_value, actions_json, enabled, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, trigger_type, trigger_value, actions_json, int(enabled),
                  datetime.utcnow().isoformat() + "Z"))
            conn.commit()
            return cursor.lastrowid

    def get_workflow_rules(self) -> List[Dict[str, Any]]:
        """Get all workflow rules."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM workflow_rules ORDER BY id ASC")
            return [dict(row) for row in cursor.fetchall()]

    def delete_workflow_rule(self, name: str):
        """Delete a workflow rule by name."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM workflow_rules WHERE name = ?", (name,))
            conn.commit()

    def log_workflow_execution(
        self,
        rule_name: str,
        file_name: str,
        file_path: str = "",
        actions_taken: str = "",
        status: str = "completed",
    ) -> int:
        """Log a workflow rule execution."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO workflow_executions
                    (timestamp, rule_name, file_name, file_path, actions_taken, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (datetime.utcnow().isoformat() + "Z", rule_name, file_name,
                  file_path, actions_taken, status))
            conn.commit()
            return cursor.lastrowid

    def get_workflow_executions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent workflow executions."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM workflow_executions ORDER BY id DESC LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    # ── Sui Anchor Methods ────────────────────────────────

    def save_anchor(
        self,
        date: str,
        root_hash: str,
        tx_digest: str = "",
        source: str = "local_ledger",
        report_summary: str = "",
    ) -> int:
        """Save a Sui anchor entry."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO sui_anchors
                    (date, root_hash, tx_digest, source, report_summary, anchored_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (date, root_hash, tx_digest, source, report_summary,
                  datetime.utcnow().isoformat() + "Z"))
            conn.commit()
            return cursor.lastrowid

    def get_anchors(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent Sui anchors."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM sui_anchors ORDER BY id DESC LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def verify_anchor(self, date: str, root_hash: str) -> bool:
        """Check if an anchor matches."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT root_hash FROM sui_anchors WHERE date = ?
            """, (date,))
            row = cursor.fetchone()
            if row:
                return row['root_hash'] == root_hash
            return False


if __name__ == "__main__":
    # Test the database
    print("🧪 Testing Database Module...")
    print("-" * 40)
    
    db = Database("test_actions.db")
    
    # Test logging an action
    action_id = db.log_action(
        action_type="MOVED",
        original_path="/downloads/test.pdf",
        new_path="/documents/test.pdf",
        file_name="test.pdf",
        category="Documents",
        file_size=1024,
        file_hash="abc123"
    )
    print(f"  ✅ Logged action ID: {action_id}")
    
    # Test getting statistics
    stats = db.get_statistics()
    print(f"  ✅ Statistics: {stats['total_files_processed']} files processed")
    
    # Test getting pending actions
    pending = db.get_pending_actions()
    print(f"  ✅ Pending actions: {len(pending)}")
    
    # Cleanup test database
    import os
    os.remove("test_actions.db")
    print("\n  ✅ All tests passed!")
