"""
Deepurge AutoClean Agent
========================

Main autonomous file organization agent that runs on Windows 11.
Monitors Downloads folder, classifies files, organizes them, and logs to Walrus.

Author: Samuel Campozano Lopez
Project: Sui Hackathon 2026
Deadline: February 11, 2026

Features:
- Real-time file monitoring with Watchdog
- Automatic file classification by extension
- Organized folder structure with timestamped files
- Duplicate detection via SHA256 hash
- Action logging to SQLite database
- Walrus blockchain storage integration
- Daily report generation
- Error recovery with retry logic
"""

import os
import sys
import json
import time
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from logging.handlers import RotatingFileHandler

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileMovedEvent
from colorama import init, Fore, Style

from classifier import FileClassifier, format_file_size
from intelligence import DeepIntelligence
from database import Database
from walrus_logger import WalrusLogger, WalrusLoggerDemo
from workflows import WorkflowEngine
from vault import DeepurgeVault, DeepurgeVaultDemo
from sui_anchor import SuiAnchor

# Initialize colorama for Windows
init(autoreset=True)


class DeepurgeAgent(FileSystemEventHandler):
    """
    Autonomous file organization agent
    
    Monitors a watch folder, classifies files by type,
    moves them to organized folders, and logs all actions
    to both SQLite and Walrus decentralized storage.
    """
    
    def __init__(self, config_path: str = "config.json"):
        """Initialize the agent with configuration"""
        self.config = self._load_config(config_path)
        self.processed_files: set = set()
        self.pending_upload_count = 0
        
        # Setup paths
        self.watch_folder = Path(self.config['folders']['watch_folder']).expanduser()
        self.organized_folder = Path(self.config['folders']['organized_folder']).expanduser()
        
        # Initialize components
        self.classifier = FileClassifier(config_path)
        self.db = Database(self.config['database']['path'])
        
        # Setup logging first
        self._setup_logging()
        
        # Initialize Walrus logger
        walrus_config = self.config.get('walrus', {})
        if walrus_config.get('enabled', True):
            try:
                self.walrus = WalrusLogger(
                    network=walrus_config.get('network', 'testnet'),
                    aggregator_url=walrus_config.get('aggregator_url'),
                    publisher_url=walrus_config.get('publisher_url'),
                    epochs=walrus_config.get('epochs', 5)
                )
            except Exception as e:
                self.logger.warning(f"Walrus init failed, using demo mode: {e}")
                self.walrus = WalrusLoggerDemo(network='testnet')
        else:
            self.walrus = WalrusLoggerDemo(network='testnet')
        
        # Blob history file for dashboard integration
        self.blob_history_path = Path("blob_history.json")
        
        # Initialize Workflow Engine (Path 3: Flow)
        wf_config = self.config.get('workflows', {})
        if wf_config.get('enabled', True):
            wf_rules = wf_config.get('rules', None) or None
            self.workflow_engine = WorkflowEngine(
                rules=wf_rules,
                organized_folder=self.organized_folder,
            )
            self.logger.info("Workflow engine loaded with %d rules", len(self.workflow_engine.rules))
        else:
            self.workflow_engine = None

        # Initialize Vault (Path 2: Vault)
        vault_config = self.config.get('vault', {})
        if vault_config.get('enabled', True):
            try:
                walrus_cfg = self.config.get('walrus', {})
                self.vault = DeepurgeVault(
                    aggregator_url=walrus_cfg.get('aggregator_url'),
                    publisher_url=walrus_cfg.get('publisher_url'),
                    epochs=vault_config.get('epochs', 10),
                )
            except Exception as e:
                self.logger.warning(f"Vault init failed, using demo mode: {e}")
                self.vault = DeepurgeVaultDemo()
        else:
            self.vault = DeepurgeVaultDemo()

        # Initialize Sui Anchor (Path 3: on-chain root hash)
        anchor_config = self.config.get('sui_anchor', {})
        self.sui_anchor = SuiAnchor(
            rpc_url=anchor_config.get('rpc_url'),
            package_id=anchor_config.get('package_id') or None,
            registry_id=anchor_config.get('registry_id') or None,
            signer_address=anchor_config.get('signer_address') or None,
        )

        # Statistics
        self.stats = {
            "files_processed": 0,
            "files_moved": 0,
            "files_skipped_duplicate": 0,
            "errors": 0,
            "start_time": datetime.now()
        }
        
        # Setup folders
        self._setup_folders()
        
        self.logger.info("Deepurge Agent initialized successfully")
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from JSON file"""
        default_config = {
            "agent_name": "Deepurge AutoClean Agent",
            "version": "1.0.0",
            "author": "Samuel Campozano Lopez",
            "folders": {
                "watch_folder": "~/Downloads",
                "organized_folder": "~/Downloads/Organized"
            },
            "scan_interval_seconds": 60,
            "min_file_age_seconds": 5,
            "categories": {},
            "ignore_patterns": [".tmp", ".crdownload", ".partial", "~$", ".download"],
            "walrus": {
                "enabled": True,
                "network": "testnet",
                "upload_batch_size": 100
            },
            "database": {
                "path": "actions.db"
            },
            "logging": {
                "file": "agent.log",
                "level": "INFO",
                "max_size_mb": 10,
                "backup_count": 3
            },
            "rename_pattern": "YYYYMMDD_HHMMSS",
            "check_duplicates": True,
            "retry_attempts": 3,
            "retry_delay_seconds": 5
        }
        
        try:
            with open(config_path, 'r') as f:
                loaded_config = json.load(f)
                # Deep merge with defaults
                for key, value in loaded_config.items():
                    if isinstance(value, dict) and key in default_config:
                        default_config[key].update(value)
                    else:
                        default_config[key] = value
        except FileNotFoundError:
            print(f"{Fore.YELLOW}⚠️ Config not found, using defaults{Style.RESET_ALL}")
        except json.JSONDecodeError as e:
            print(f"{Fore.RED}❌ Config parse error: {e}{Style.RESET_ALL}")
        
        return default_config
    
    def _setup_logging(self):
        """Setup file and console logging"""
        log_config = self.config.get('logging', {})
        
        self.logger = logging.getLogger('DeepurgeAgent')
        self.logger.setLevel(getattr(logging, log_config.get('level', 'INFO')))
        
        # File handler with rotation
        file_handler = RotatingFileHandler(
            log_config.get('file', 'agent.log'),
            maxBytes=log_config.get('max_size_mb', 10) * 1024 * 1024,
            backupCount=log_config.get('backup_count', 3)
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '%(message)s'
        ))
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def _setup_folders(self):
        """Create all required folders"""
        print(f"\n{Fore.CYAN}📁 Setting up folders...{Style.RESET_ALL}")
        
        # Create watch folder if not exists
        self.watch_folder.mkdir(parents=True, exist_ok=True)
        print(f"   📂 Watch: {self.watch_folder}")
        
        # Create organized folder structure
        self.organized_folder.mkdir(parents=True, exist_ok=True)
        
        for category in self.classifier.get_all_categories():
            folder = self.organized_folder / category
            folder.mkdir(parents=True, exist_ok=True)
            print(f"   ✓ {folder}")
        
        print(f"{Fore.GREEN}   ✅ Folders ready!{Style.RESET_ALL}\n")
    
    def _should_ignore(self, file_path: Path) -> bool:
        """Check if file should be ignored"""
        file_name = file_path.name.lower()
        
        # Ignore patterns from config
        for pattern in self.config.get('ignore_patterns', []):
            if pattern.lower() in file_name:
                return True
        
        # Ignore hidden files
        if file_name.startswith('.'):
            return True
        
        # Ignore directories
        if file_path.is_dir():
            return True
        
        return False
    
    def _is_file_ready(self, file_path: Path) -> bool:
        """Check if file is ready (not being written)"""
        try:
            if not file_path.exists():
                return False
            
            # Check file age
            min_age = self.config.get('min_file_age_seconds', 5)
            file_age = time.time() - file_path.stat().st_mtime
            if file_age < min_age:
                return False
            
            # Try to open file to ensure not locked
            with open(file_path, 'rb') as f:
                f.read(1)
            return True
            
        except (PermissionError, IOError, OSError):
            return False
    
    def _generate_new_filename(self, file_path: Path) -> str:
        """Generate new filename with timestamp pattern"""
        pattern = self.config.get('rename_pattern', 'YYYYMMDD_HHMMSS')
        now = datetime.now()
        
        timestamp = pattern
        timestamp = timestamp.replace('YYYY', now.strftime('%Y'))
        timestamp = timestamp.replace('MM', now.strftime('%m'))
        timestamp = timestamp.replace('DD', now.strftime('%d'))
        timestamp = timestamp.replace('HH', now.strftime('%H'))
        timestamp = timestamp.replace('mm', now.strftime('%M'))
        timestamp = timestamp.replace('SS', now.strftime('%S'))
        
        return f"{timestamp}_{file_path.name}"
    
    def _check_duplicate(self, file_hash: str) -> bool:
        """Check if file with same hash exists"""
        if not self.config.get('check_duplicates', True):
            return False
        return self.db.file_hash_exists(file_hash)
    
    def process_file(self, file_path: Path) -> Optional[Path]:
        """
        Process a single file: classify, check duplicates, move, log
        
        Args:
            file_path: Path to the file
            
        Returns:
            New path if moved, None otherwise
        """
        if self._should_ignore(file_path):
            return None
        
        if str(file_path) in self.processed_files:
            return None
        
        if not self._is_file_ready(file_path):
            return None
        
        retry_attempts = self.config.get('retry_attempts', 3)
        retry_delay = self.config.get('retry_delay_seconds', 5)
        
        for attempt in range(retry_attempts):
            try:
                # Analyze file
                analysis = self.classifier.analyze_file(file_path)
                category = analysis['category']
                file_size = analysis['size']
                file_hash = analysis['hash']
                
                # Check for duplicates
                if file_hash and self._check_duplicate(file_hash):
                    self.logger.info(f"[SKIP] Skipping duplicate: {file_path.name}")
                    self.stats['files_skipped_duplicate'] += 1
                    self.processed_files.add(str(file_path))
                    
                    # Log skipped file
                    self.db.log_action(
                        action_type="DUPLICATE_SKIPPED",
                        original_path=str(file_path),
                        new_path=None,
                        file_name=file_path.name,
                        category=category,
                        file_size=file_size,
                        file_hash=file_hash
                    )
                    return None
                
                # Generate destination path and smart name
                intel = analysis.get("intelligence", {})
                smart_name = DeepIntelligence.get_smart_name(file_path, intel)
                new_filename = self._generate_new_filename(Path(smart_name + file_path.suffix))
                
                destination_folder = self.classifier.get_smart_destination(
                    file_path, self.organized_folder, intel
                )
                
                # Ensure sub-folders exist
                destination_folder.mkdir(parents=True, exist_ok=True)
                destination_path = destination_folder / new_filename
                
                # Handle name conflicts
                counter = 1
                while destination_path.exists():
                    stem = Path(smart_name).stem
                    suffix = file_path.suffix
                    timestamp = new_filename.rsplit('_', 1)[0]
                    destination_path = destination_folder / f"{timestamp}_{stem}_{counter}{suffix}"
                    counter += 1
                
                # Move the file
                shutil.move(str(file_path), str(destination_path))
                
                # Update statistics
                self.processed_files.add(str(file_path))
                self.stats['files_moved'] += 1
                self.stats['files_processed'] += 1
                self.pending_upload_count += 1
                
                # Log to database
                action_id = self.db.log_action(
                    action_type="MOVED",
                    original_path=str(file_path),
                    new_path=str(destination_path),
                    file_name=file_path.name,
                    category=category,
                    file_size=file_size,
                    file_hash=file_hash
                )
                
                # Log to Walrus (individual or batch)
                walrus_blob_id = None
                batch_size = self.config.get('walrus', {}).get('upload_batch_size', 100)
                
                if self.pending_upload_count >= batch_size:
                    walrus_blob_id = self._upload_batch_to_walrus()
                
                # Print success message
                sub_cat = intel.get("sub_category", "General")
                print(f"{Fore.GREEN}✅ Moved:{Style.RESET_ALL} {file_path.name}")
                print(f"   {Fore.BLUE}Category:{Style.RESET_ALL} {category} ({sub_cat})")
                print(f"   {Fore.BLUE}Size:{Style.RESET_ALL} {format_file_size(file_size)}")
                print(f"   {Fore.BLUE}New name:{Style.RESET_ALL} {new_filename}")
                if walrus_blob_id:
                    print(f"   {Fore.MAGENTA}Walrus Batch:{Style.RESET_ALL} {walrus_blob_id}")

                # ── Run Workflow Engine on the moved file ──
                if self.workflow_engine and destination_path.exists():
                    def _vault_backup(fp):
                        try:
                            manifest = self.vault.store(fp)
                            self.db.log_vault_file(
                                file_name=fp.name,
                                original_path=str(fp),
                                blob_id=manifest["blob_id"],
                                key_hex=manifest["key_hex"],
                                nonce_hex=manifest["nonce_hex"],
                                file_size=manifest["file_size"],
                                encrypted_size=manifest["encrypted_size"],
                                mime_type=manifest.get("mime_type", ""),
                                sha256=manifest.get("sha256", ""),
                                walrus_url=manifest.get("walrus_url", ""),
                            )
                            print(f"   {Fore.CYAN}🔐 Vault backup:{Style.RESET_ALL} {manifest['blob_id'][:24]}…")
                        except Exception as ve:
                            self.logger.warning(f"Vault backup failed: {ve}")

                    wf_results = self.workflow_engine.evaluate(
                        destination_path, vault_callback=_vault_backup
                    )
                    for wfr in wf_results:
                        print(f"   {Fore.YELLOW}⚡ Workflow:{Style.RESET_ALL} {wfr['rule']}")
                        for act in wfr.get("actions", []):
                            print(f"      → {act['type']}: {act.get('status', '')}")
                        self.db.log_workflow_execution(
                            rule_name=wfr["rule"],
                            file_name=wfr["file"],
                            file_path=str(destination_path),
                            actions_taken=json.dumps(wfr["actions"]),
                        )

                print()
                
                self.logger.info(f"Moved: {file_path.name} -> {category}/{new_filename}")
                
                return destination_path
                
            except Exception as e:
                self.logger.error(f"Error processing {file_path.name} (attempt {attempt + 1}): {e}")
                
                if attempt < retry_attempts - 1:
                    time.sleep(retry_delay)
                else:
                    self.stats['errors'] += 1
                    self.db.log_action(
                        action_type="ERROR",
                        original_path=str(file_path),
                        file_name=file_path.name,
                        category="Unknown",
                        status="failed",
                        error_message=str(e)
                    )
                    print(f"{Fore.RED}❌ Error: {file_path.name} - {e}{Style.RESET_ALL}")
        
        return None
    
    def _upload_batch_to_walrus(self) -> Optional[str]:
        """Upload pending actions to Walrus as a batch"""
        try:
            pending = self.db.get_pending_actions(limit=100)
            if not pending:
                return None
            
            # Create batch entry
            batch_data = {
                "batch_type": "action_log",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "action_count": len(pending),
                "actions": pending,
                "agent": "Deepurge-AutoClean-Agent-v1.0",
                "author": "Samuel Campozano Lopez"
            }
            
            blob_id = self.walrus.upload_to_walrus(batch_data)
            
            if blob_id:
                # Mark actions as uploaded
                action_ids = [a['id'] for a in pending]
                self.db.mark_actions_uploaded(action_ids, blob_id)
                self.db.log_walrus_upload(
                    blob_id=blob_id,
                    content_type="action_batch",
                    action_count=len(pending),
                    data_summary={"categories": self._get_category_counts(pending)}
                )
                self.pending_upload_count = 0
                
                self._save_blob_to_history(blob_id, "action_batch", len(pending))
                
                print(f"{Fore.MAGENTA}📤 Uploaded {len(pending)} actions to Walrus{Style.RESET_ALL}")
                print(f"   {Fore.MAGENTA}Blob ID:{Style.RESET_ALL} {blob_id}")
                print(f"   {Fore.MAGENTA}View URL:{Style.RESET_ALL} {self.walrus.get_walrus_url(blob_id)}")
                
                return blob_id
            
        except Exception as e:
            self.logger.error(f"Walrus batch upload failed: {e}")
        
        return None
    
    def _save_blob_to_history(self, blob_id: str, content_type: str, action_count: int = 0):
        """Append a blob ID to blob_history.json for dashboard auto-discovery"""
        try:
            history = {"blobs": []}
            if self.blob_history_path.exists():
                with open(self.blob_history_path, 'r') as f:
                    history = json.load(f)
            
            history["blobs"].append({
                "blob_id": blob_id,
                "url": self.walrus.get_walrus_url(blob_id),
                "content_type": content_type,
                "action_count": action_count,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            })
            
            with open(self.blob_history_path, 'w') as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            self.logger.warning(f"Failed to save blob history: {e}")

    def _get_category_counts(self, actions: list) -> dict:
        """Get category counts from actions"""
        counts = {}
        for action in actions:
            cat = action.get('category', 'Unknown')
            counts[cat] = counts.get(cat, 0) + 1
        return counts
    
    def on_created(self, event):
        """Handle file creation events"""
        if isinstance(event, FileCreatedEvent):
            file_path = Path(event.src_path)
            min_age = self.config.get('min_file_age_seconds', 5)
            time.sleep(min_age)
            self.process_file(file_path)
    
    def on_moved(self, event):
        """Handle file move events (browser completing download)"""
        if isinstance(event, FileMovedEvent):
            file_path = Path(event.dest_path)
            min_age = self.config.get('min_file_age_seconds', 5)
            time.sleep(min_age)
            self.process_file(file_path)
    
    def scan_existing_files(self):
        """Scan and process existing files"""
        print(f"{Fore.YELLOW}🔍 Scanning existing files...{Style.RESET_ALL}\n")
        
        files = list(self.watch_folder.iterdir())
        processed = 0
        
        for file_path in files:
            if file_path.is_file() and not self._should_ignore(file_path):
                result = self.process_file(file_path)
                if result:
                    processed += 1
        
        # Upload any remaining pending actions
        if self.pending_upload_count > 0:
            self._upload_batch_to_walrus()
        
        print(f"{Fore.GREEN}✅ Processed {processed} existing files{Style.RESET_ALL}\n")
        return processed
    
    def create_daily_report(self):
        """Create and upload daily report to Walrus, then anchor root hash"""
        today = datetime.utcnow().strftime('%Y-%m-%d')
        summary = self.db.get_daily_summary(today)
        
        if summary['total_files'] == 0:
            return None
        
        blob_id = self.walrus.create_daily_report(today, summary)
        
        if blob_id:
            self.db.save_daily_report(
                report_date=today,
                total_files=summary['total_files'],
                categories_summary=summary['categories'],
                walrus_blob_id=blob_id
            )
            
            print(f"{Fore.CYAN}📊 Daily report uploaded to Walrus{Style.RESET_ALL}")
            print(f"   {Fore.CYAN}Date:{Style.RESET_ALL} {today}")
            print(f"   {Fore.CYAN}Files:{Style.RESET_ALL} {summary['total_files']}")
            print(f"   {Fore.CYAN}Blob ID:{Style.RESET_ALL} {blob_id}")
            print(f"   {Fore.CYAN}View URL:{Style.RESET_ALL} {self.walrus.get_walrus_url(blob_id)}")
            self._save_blob_to_history(blob_id, "daily_report", summary['total_files'])

            # ── Anchor root hash on Sui (Path 3) ──
            try:
                anchor_result = self.sui_anchor.anchor_daily_report(summary)
                root_hash = anchor_result.get("root_hash", "")
                self.db.save_anchor(
                    date=today,
                    root_hash=root_hash,
                    tx_digest=anchor_result.get("tx_digest", ""),
                    source=anchor_result.get("source", "local_ledger"),
                    report_summary=json.dumps(summary),
                )
                print(f"   {Fore.GREEN}⚓ Root hash anchored:{Style.RESET_ALL} {root_hash[:24]}…")
                print(f"   {Fore.GREEN}   Source:{Style.RESET_ALL} {anchor_result.get('source', 'local')}")
            except Exception as e:
                self.logger.warning(f"Sui anchor failed: {e}")
        
        return blob_id
    
    def print_stats(self):
        """Print current statistics"""
        runtime = datetime.now() - self.stats['start_time']
        db_stats = self.db.get_statistics()
        
        print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}📊 DEEPURGE AGENT STATISTICS{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(f"  Runtime: {runtime}")
        print(f"  Session Files Moved: {self.stats['files_moved']}")
        print(f"  Duplicates Skipped: {self.stats['files_skipped_duplicate']}")
        print(f"  Errors: {self.stats['errors']}")
        print(f"\n  {Fore.BLUE}All-time Statistics:{Style.RESET_ALL}")
        print(f"    Total Files Processed: {db_stats['total_files_processed']}")
        print(f"    Total Data: {format_file_size(db_stats['total_bytes_processed'])}")
        print(f"    Walrus Uploads: {db_stats['walrus_uploads']}")
        print(f"    Today's Files: {db_stats['today_count']}")
        print(f"\n  {Fore.MAGENTA}Categories:{Style.RESET_ALL}")
        for cat_stat in db_stats.get('categories', []):
            print(f"    {cat_stat['category']}: {cat_stat['count']} files ({format_file_size(cat_stat['total_size'] or 0)})")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")


def print_banner():
    """Print the agent banner"""
    banner = f"""
{Fore.CYAN}╔════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║   {Fore.WHITE}██████╗ ███████╗███████╗██████╗ ██╗   ██╗██████╗  ██████╗ ███████╗{Fore.CYAN}    ║
║   {Fore.WHITE}██╔══██╗██╔════╝██╔════╝██╔══██╗██║   ██║██╔══██╗██╔════╝ ██╔════╝{Fore.CYAN}    ║
║   {Fore.WHITE}██║  ██║█████╗  █████╗  ██████╔╝██║   ██║██████╔╝██║  ███╗█████╗{Fore.CYAN}      ║
║   {Fore.WHITE}██║  ██║██╔══╝  ██╔══╝  ██╔═══╝ ██║   ██║██╔══██╗██║   ██║██╔══╝{Fore.CYAN}      ║
║   {Fore.WHITE}██████╔╝███████╗███████╗██║     ╚██████╔╝██║  ██║╚██████╔╝███████╗{Fore.CYAN}    ║
║   {Fore.WHITE}╚═════╝ ╚══════╝╚══════╝╚═╝      ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝{Fore.CYAN}    ║
║                                                                      ║
║   {Fore.YELLOW}🤖 AUTOCLEAN AGENT FOR SUI HACKATHON{Fore.CYAN}                              ║
║   {Fore.GREEN}👤 Author: Samuel Campozano Lopez{Fore.CYAN}                                 ║
║   {Fore.MAGENTA}🦭 Powered by Walrus Decentralized Storage{Fore.CYAN}                        ║
║                                                                      ║
╚════════════════════════════════════════════════════════════════════╝{Style.RESET_ALL}
"""
    print(banner)


def main():
    """Main entry point"""
    print_banner()
    
    print(f"{Fore.CYAN}🚀 Starting Deepurge AutoClean Agent...{Style.RESET_ALL}")
    
    # Create the agent
    try:
        agent = DeepurgeAgent("config.json")
    except Exception as e:
        print(f"{Fore.RED}❌ Failed to initialize agent: {e}{Style.RESET_ALL}")
        sys.exit(1)
    
    print(f"   {Fore.BLUE}Watch Folder:{Style.RESET_ALL} {agent.watch_folder}")
    print(f"   {Fore.BLUE}Organized Folder:{Style.RESET_ALL} {agent.organized_folder}")
    print(f"   {Fore.BLUE}Walrus Network:{Style.RESET_ALL} {agent.walrus.network}")
    print()
    
    # Verify watch folder exists
    if not agent.watch_folder.exists():
        print(f"{Fore.RED}❌ Watch folder not found: {agent.watch_folder}{Style.RESET_ALL}")
        sys.exit(1)
    
    # Scan existing files first
    agent.scan_existing_files()
    
    # Set up file watcher
    observer = Observer()
    observer.schedule(agent, str(agent.watch_folder), recursive=False)
    observer.start()
    
    print(f"{Fore.GREEN}👁️  Watching for new files...{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}   Press Ctrl+C to stop{Style.RESET_ALL}\n")
    
    scan_interval = agent.config.get('scan_interval_seconds', 60)
    last_report_date = None
    
    try:
        while True:
            time.sleep(scan_interval)
            
            # Check for daily report
            today = datetime.utcnow().strftime('%Y-%m-%d')
            if last_report_date != today:
                if last_report_date is not None:
                    agent.create_daily_report()
                last_report_date = today
            
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}🛑 Stopping agent...{Style.RESET_ALL}")
        observer.stop()
        
        # Upload remaining pending actions
        if agent.pending_upload_count > 0:
            print(f"{Fore.CYAN}📤 Uploading remaining actions to Walrus...{Style.RESET_ALL}")
            agent._upload_batch_to_walrus()
        
        # Create session summary
        print(f"{Fore.CYAN}📤 Uploading session summary to Walrus...{Style.RESET_ALL}")
        blob_id = agent.walrus.upload_session_summary()
        if blob_id:
            print(f"   {Fore.GREEN}✅ Summary Blob ID: {blob_id}{Style.RESET_ALL}")
            print(f"   {Fore.GREEN}✅ View URL: {agent.walrus.get_walrus_url(blob_id)}{Style.RESET_ALL}")
            agent._save_blob_to_history(blob_id, "session_summary")
        
        # Save local backup
        agent.walrus.save_local_backup(Path("session_backup.json"))
        print(f"   {Fore.GREEN}✅ Local backup saved{Style.RESET_ALL}")
        
        # Print final stats
        agent.print_stats()
    
    observer.join()
    print(f"{Fore.GREEN}👋 Deepurge Agent stopped. Goodbye!{Style.RESET_ALL}")


if __name__ == "__main__":
    main()
