"""
Walrus Logger Module for Deepurge AutoClean Agent
Logs file operations to Walrus decentralized storage on Sui blockchain

Author: Samuel Campozano Lopez
Project: Sui Hackathon 2026

Based on Sui Stack plugin patterns for Walrus integration.
Uses Publisher pattern (HTTP REST API) for server-side uploads.

Reference: https://docs.wal.app/
"""
import json
import hashlib
import requests
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List


class WalrusLogger:
    """
    Logs file operations to Walrus decentralized storage.
    
    Uses the Publisher pattern which is ideal for:
    - Server-side/backend applications
    - Batch uploading content
    - No user wallet interaction needed
    
    Architecture:
        Agent → Publisher Server → Walrus Storage Nodes
               (publisher.walrus-testnet.walrus.space)
    """
    
    # Walrus testnet endpoints
    TESTNET_AGGREGATOR = "https://aggregator.walrus-testnet.walrus.space"
    TESTNET_PUBLISHER = "https://publisher.walrus-testnet.walrus.space"
    
    # Walrus mainnet endpoints (when available)
    MAINNET_AGGREGATOR = "https://aggregator.walrus.space"
    MAINNET_PUBLISHER = "https://publisher.walrus.space"
    
    def __init__(
        self,
        network: str = "testnet",
        aggregator_url: Optional[str] = None,
        publisher_url: Optional[str] = None,
        epochs: int = 5
    ):
        """
        Initialize Walrus logger
        
        Args:
            network: "testnet" or "mainnet"
            aggregator_url: Custom aggregator URL (for retrieval)
            publisher_url: Custom publisher URL (for uploads)
            epochs: Number of storage epochs (≈5 days per epoch on testnet)
        """
        if network == "mainnet":
            self.aggregator_url = aggregator_url or self.MAINNET_AGGREGATOR
            self.publisher_url = publisher_url or self.MAINNET_PUBLISHER
        else:
            self.aggregator_url = aggregator_url or self.TESTNET_AGGREGATOR
            self.publisher_url = publisher_url or self.TESTNET_PUBLISHER
        
        self.network = network
        self.epochs = epochs
        self.session_logs: List[Dict[str, Any]] = []
        self.blob_ids: List[str] = []
        self._enabled = True
        
    def disable(self):
        """Disable Walrus uploads (for offline mode)"""
        self._enabled = False
    
    def enable(self):
        """Enable Walrus uploads"""
        self._enabled = True
    
    def is_enabled(self) -> bool:
        """Check if Walrus uploads are enabled"""
        return self._enabled
        
    def create_log_entry(
        self,
        action: str,
        file_name: str,
        source_path: str,
        destination_path: str,
        category: str,
        file_size: int = 0,
        file_hash: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a structured log entry
        
        Args:
            action: Action performed (e.g., "MOVED", "CLASSIFIED", "DUPLICATE_SKIPPED")
            file_name: Name of the file
            source_path: Original file path
            destination_path: New file path
            category: File category
            file_size: File size in bytes
            file_hash: SHA256 hash of the file
            
        Returns:
            Structured log entry dictionary
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": action,
            "file_name": file_name,
            "source_path": source_path,
            "destination_path": destination_path,
            "category": category,
            "file_size": file_size,
            "file_hash": file_hash or self._compute_entry_hash(file_name),
            "agent": "Deepurge-AutoClean-Agent-v1.0",
            "network": self.network,
            "author": "Samuel Campozano Lopez"
        }
        
        self.session_logs.append(entry)
        return entry
    
    def _compute_entry_hash(self, content: str) -> str:
        """Compute a hash identifier for the log entry"""
        data = f"{content}{datetime.utcnow().isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def upload_to_walrus(
        self,
        data: Dict[str, Any],
        epochs: Optional[int] = None
    ) -> Optional[str]:
        """
        Upload data to Walrus using Publisher pattern
        
        This uses the HTTP REST API of Walrus:
        PUT /v1/blobs?epochs=N
        
        Args:
            data: Dictionary to upload as JSON
            epochs: Number of storage epochs (default: self.epochs)
            
        Returns:
            Blob ID if successful, None otherwise
        """
        if not self._enabled:
            return None
            
        try:
            json_data = json.dumps(data, indent=2)
            epochs = epochs or self.epochs
            
            # Walrus Publisher API endpoint (correct endpoint is /v1/blobs)
            url = f"{self.publisher_url}/v1/blobs?epochs={epochs}"
            
            response = requests.put(
                url,
                data=json_data.encode('utf-8'),
                headers={
                    "Content-Type": "application/json"
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Handle different response formats
                blob_id = None
                
                # New blob created
                if "newlyCreated" in result:
                    blob_id = result["newlyCreated"].get("blobObject", {}).get("blobId")
                
                # Blob already exists (deduplication)
                elif "alreadyCertified" in result:
                    blob_id = result["alreadyCertified"].get("blobId")
                
                if blob_id:
                    self.blob_ids.append(blob_id)
                    return blob_id
                
                print(f"[WARN] Walrus: Could not extract blob ID from response")
                return None
            
            elif response.status_code == 413:
                print(f"[WARN] Walrus: Payload too large (max 10MB)")
                return None
            else:
                print(f"[WARN] Walrus upload failed: HTTP {response.status_code}")
                return None
                
        except requests.exceptions.Timeout:
            print(f"[WARN] Walrus upload timeout (60s exceeded)")
            return None
        except requests.exceptions.ConnectionError:
            print(f"[WARN] Walrus: Connection failed (check network)")
            return None
        except requests.exceptions.RequestException as e:
            print(f"[WARN] Walrus upload error: {e}")
            return None
        except Exception as e:
            print(f"[WARN] Unexpected Walrus error: {e}")
            return None
    
    def log_and_upload(
        self,
        action: str,
        file_name: str,
        source_path: str,
        destination_path: str,
        category: str,
        file_size: int = 0,
        file_hash: Optional[str] = None
    ) -> Optional[str]:
        """
        Create a log entry and immediately upload to Walrus
        
        Returns:
            Blob ID if upload successful, None otherwise
        """
        entry = self.create_log_entry(
            action, file_name, source_path, destination_path,
            category, file_size, file_hash
        )
        return self.upload_to_walrus(entry)
    
    def upload_batch(self, entries: List[Dict[str, Any]]) -> Optional[str]:
        """
        Upload a batch of log entries to Walrus
        
        Args:
            entries: List of log entry dictionaries
            
        Returns:
            Blob ID of the batch upload
        """
        batch = {
            "batch_id": self._compute_entry_hash(f"batch-{len(entries)}"),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "entry_count": len(entries),
            "entries": entries,
            "agent": "Deepurge-AutoClean-Agent-v1.0",
            "network": self.network,
            "author": "Samuel Campozano Lopez"
        }
        
        return self.upload_to_walrus(batch)
    
    def upload_session_summary(self) -> Optional[str]:
        """
        Upload all session logs as a summary to Walrus
        
        Returns:
            Blob ID of the summary
        """
        if not self.session_logs:
            return None
            
        summary = {
            "summary_type": "session",
            "session_start": self.session_logs[0]["timestamp"] if self.session_logs else None,
            "session_end": datetime.utcnow().isoformat() + "Z",
            "total_operations": len(self.session_logs),
            "operations": self.session_logs,
            "blob_ids_generated": self.blob_ids,
            "agent": "Deepurge-AutoClean-Agent-v1.0",
            "network": self.network,
            "author": "Samuel Campozano Lopez"
        }
        
        return self.upload_to_walrus(summary)
    
    def create_daily_report(
        self,
        date: str,
        stats: Dict[str, Any]
    ) -> Optional[str]:
        """
        Create and upload a daily report to Walrus
        
        Args:
            date: Report date (YYYY-MM-DD)
            stats: Statistics dictionary
            
        Returns:
            Blob ID of the report
        """
        report = {
            "report_type": "daily",
            "report_date": date,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "statistics": stats,
            "agent": "Deepurge-AutoClean-Agent-v1.0",
            "network": self.network,
            "author": "Samuel Campozano Lopez"
        }
        
        return self.upload_to_walrus(report, epochs=30)  # Store reports longer
    
    def retrieve_from_walrus(self, blob_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve data from Walrus by blob ID
        
        Args:
            blob_id: The Walrus blob ID
            
        Returns:
            Retrieved data as dictionary, or None if failed
        """
        try:
            url = f"{self.aggregator_url}/v1/blobs/{blob_id}"
            
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            
            print(f"[WARN] Walrus retrieval failed: HTTP {response.status_code}")
            return None
            
        except Exception as e:
            print(f"[WARN] Failed to retrieve from Walrus: {e}")
            return None
    
    def get_walrus_url(self, blob_id: str) -> str:
        """
        Get the HTTP URL to access a blob
        
        Args:
            blob_id: The Walrus blob ID
            
        Returns:
            Full URL to retrieve the blob
        """
        return f"{self.aggregator_url}/v1/blobs/{blob_id}"
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get statistics for the current session"""
        if not self.session_logs:
            return {
                "total_operations": 0,
                "categories": {},
                "total_size_bytes": 0,
                "blob_ids": []
            }
            
        categories: Dict[str, int] = {}
        total_size = 0
        
        for log in self.session_logs:
            cat = log.get("category", "Unknown")
            categories[cat] = categories.get(cat, 0) + 1
            total_size += log.get("file_size", 0)
        
        return {
            "total_operations": len(self.session_logs),
            "categories": categories,
            "total_size_bytes": total_size,
            "blob_ids": self.blob_ids.copy()
        }
    
    def save_local_backup(self, log_file: Path):
        """Save session logs to a local file as backup"""
        backup_data = {
            "session_logs": self.session_logs,
            "blob_ids": self.blob_ids,
            "network": self.network,
            "exported_at": datetime.utcnow().isoformat() + "Z",
            "agent": "Deepurge-AutoClean-Agent-v1.0",
            "author": "Samuel Campozano Lopez"
        }
        
        with open(log_file, 'w') as f:
            json.dump(backup_data, f, indent=2)
    
    def clear_session(self):
        """Clear session logs (but keep blob IDs)"""
        self.session_logs = []


# Demo mode for testing without network
class WalrusLoggerDemo(WalrusLogger):
    """
    Demo version of WalrusLogger that simulates uploads
    Use this for testing and demonstrations when network is unavailable
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._demo_mode = True
        self._demo_counter = 0
    
    def upload_to_walrus(
        self,
        data: Dict[str, Any],
        epochs: Optional[int] = None
    ) -> Optional[str]:
        """Simulate upload and return fake blob ID"""
        self._demo_counter += 1
        
        # Generate realistic-looking blob ID
        content_hash = hashlib.sha256(
            json.dumps(data).encode()
        ).hexdigest()[:32]
        
        fake_blob_id = f"demo_{content_hash}_{self._demo_counter}"
        self.blob_ids.append(fake_blob_id)
        
        print(f"  🎭 [DEMO MODE] Simulated Walrus upload")
        return fake_blob_id


if __name__ == "__main__":
    # Test the Walrus logger
    print("🧪 Testing Walrus Logger...")
    print("-" * 50)
    
    # Use demo mode for testing
    logger = WalrusLoggerDemo(network="testnet")
    
    # Create test log entry
    entry = logger.create_log_entry(
        action="MOVED",
        file_name="test_document.pdf",
        source_path="C:/Users/Test/Downloads/test_document.pdf",
        destination_path="C:/Users/Test/Downloads/Organized/Documents/test_document.pdf",
        category="Documents",
        file_size=1024000,
        file_hash="abc123def456"
    )
    
    print(f"\n📝 Created log entry:")
    print(f"   File: {entry['file_name']}")
    print(f"   Action: {entry['action']}")
    print(f"   Category: {entry['category']}")
    print(f"   Timestamp: {entry['timestamp']}")
    
    # Test upload (demo mode)
    print(f"\n[UPLOAD] Testing upload...")
    blob_id = logger.upload_to_walrus(entry)
    
    if blob_id:
        print(f"   [OK] Blob ID: {blob_id}")
        print(f"   [LINK] URL: {logger.get_walrus_url(blob_id)}")
    
    # Test batch upload
    print(f"\n[BATCH] Testing batch upload...")
    for i in range(5):
        logger.create_log_entry(
            action="MOVED",
            file_name=f"file_{i}.jpg",
            source_path=f"/downloads/file_{i}.jpg",
            destination_path=f"/organized/Images/file_{i}.jpg",
            category="Images",
            file_size=50000
        )
    
    batch_blob_id = logger.upload_batch(logger.session_logs)
    if batch_blob_id:
        print(f"   [OK] Batch Blob ID: {batch_blob_id}")
    
    # Test statistics
    print(f"\n[STATS] Session Statistics:")
    stats = logger.get_session_stats()
    print(f"   Total Operations: {stats['total_operations']}")
    print(f"   Categories: {stats['categories']}")
    print(f"   Blob IDs: {len(stats['blob_ids'])}")
    
    print(f"\n[OK] All tests passed!")
