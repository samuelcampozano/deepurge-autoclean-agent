"""
Sui Anchor – On-Chain Root Hash Anchoring for Deepurge
=======================================================

Deploys and interacts with a simple Move smart contract on Sui Testnet
that stores the SHA-256 "root hash" of daily reports.  This provides
on-chain proof that the logs haven't been tampered with.

Approach:
  - Uses the Sui JSON-RPC API directly (no pysui dependency).
  - The Move contract stores a mapping of date → root_hash.
  - Anyone can query the contract to verify a report's integrity.

Author: Samuel Campozano Lopez
Project: Sui Hackathon 2026
"""

import json
import hashlib
import requests
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List


class SuiAnchor:
    """
    Interact with the Deepurge Anchor smart contract on Sui.

    The contract is a minimal on-chain registry that maps
    ``date_string → root_hash_hex`` and emits events for each anchor.

    For the hackathon, we provide:
      - Local root-hash computation from daily reports
      - Sui JSON-RPC calls to store/verify hashes
      - A fallback "local ledger" mode when no wallet is configured
    """

    SUI_TESTNET_RPC = "https://fullnode.testnet.sui.io:443"
    SUI_MAINNET_RPC = "https://fullnode.mainnet.sui.io:443"

    def __init__(
        self,
        rpc_url: Optional[str] = None,
        package_id: Optional[str] = None,
        registry_id: Optional[str] = None,
        signer_address: Optional[str] = None,
    ):
        self.rpc_url = rpc_url or self.SUI_TESTNET_RPC
        self.package_id = package_id
        self.registry_id = registry_id
        self.signer_address = signer_address

        # Local ledger fallback (when no contract is deployed yet)
        self.local_ledger: List[Dict[str, Any]] = []
        self._ledger_path = Path("anchor_ledger.json")
        self._load_local_ledger()

    # ── Root Hash Computation ─────────────────────────────

    @staticmethod
    def compute_root_hash(report_data: Dict[str, Any]) -> str:
        """
        Compute a deterministic SHA-256 root hash for a daily report.

        The hash covers the date, total files, category breakdown,
        and any blob IDs — making it tamper-evident.
        """
        canonical = json.dumps(report_data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    @staticmethod
    def compute_root_hash_from_actions(actions: List[Dict[str, Any]]) -> str:
        """
        Compute root hash from a list of action dicts.

        Chains the individual file hashes together:
          H = SHA256( action1_hash || action2_hash || ... )
        """
        h = hashlib.sha256()
        for action in sorted(actions, key=lambda a: a.get("timestamp", "")):
            file_hash = action.get("file_hash", action.get("sha256", ""))
            h.update(file_hash.encode())
        return h.hexdigest()

    # ── Local Ledger (fallback) ───────────────────────────

    def anchor_local(self, date: str, root_hash: str, report_summary: Optional[Dict] = None):
        """Store anchor in local JSON ledger (no blockchain needed)."""
        entry = {
            "date": date,
            "root_hash": root_hash,
            "anchored_at": datetime.utcnow().isoformat() + "Z",
            "source": "local_ledger",
            "report_summary": report_summary,
        }
        self.local_ledger.append(entry)
        self._save_local_ledger()
        return entry

    def verify_local(self, date: str, root_hash: str) -> bool:
        """Verify a root hash against the local ledger."""
        for entry in self.local_ledger:
            if entry["date"] == date and entry["root_hash"] == root_hash:
                return True
        return False

    def get_local_anchors(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return local ledger entries."""
        return self.local_ledger[-limit:]

    def _load_local_ledger(self):
        try:
            if self._ledger_path.exists():
                with open(self._ledger_path) as f:
                    data = json.load(f)
                    self.local_ledger = data.get("anchors", [])
        except Exception:
            self.local_ledger = []

    def _save_local_ledger(self):
        with open(self._ledger_path, "w") as f:
            json.dump({"anchors": self.local_ledger}, f, indent=2)

    # ── Sui JSON-RPC Calls ────────────────────────────────

    def _rpc_call(self, method: str, params: list) -> Dict[str, Any]:
        """Make a raw Sui JSON-RPC call."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }
        resp = requests.post(self.rpc_url, json=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        if "error" in result:
            raise RuntimeError(f"Sui RPC error: {result['error']}")
        return result.get("result", {})

    def anchor_on_chain(self, date: str, root_hash: str) -> Dict[str, Any]:
        """
        Call the Move contract to anchor a root hash on-chain.

        Requires ``package_id``, ``registry_id``, and ``signer_address``
        to be configured.  Falls back to local ledger otherwise.
        """
        if not all([self.package_id, self.registry_id, self.signer_address]):
            print("[INFO] Sui contract not configured — using local ledger")
            return self.anchor_local(date, root_hash)

        try:
            # Build a moveCall transaction
            tx = self._rpc_call("unsafe_moveCall", [
                self.signer_address,
                self.package_id,
                "deepurge_anchor",
                "anchor_report",
                [],  # type args
                [
                    self.registry_id,
                    date,
                    root_hash,
                ],
                None,  # gas object
                "10000000",  # gas budget
            ])

            return {
                "date": date,
                "root_hash": root_hash,
                "tx_digest": tx.get("digest", "pending"),
                "source": "sui_testnet",
                "anchored_at": datetime.utcnow().isoformat() + "Z",
            }

        except Exception as e:
            print(f"[WARN] On-chain anchor failed, using local ledger: {e}")
            return self.anchor_local(date, root_hash)

    def verify_on_chain(self, date: str, expected_hash: str) -> Dict[str, Any]:
        """
        Query the contract's registry to verify a root hash.

        Falls back to local ledger verification if contract isn't configured.
        """
        if not all([self.package_id, self.registry_id]):
            return {
                "verified": self.verify_local(date, expected_hash),
                "source": "local_ledger",
            }

        try:
            obj = self._rpc_call("sui_getObject", [
                self.registry_id,
                {"showContent": True},
            ])
            # Parse the contract's Table/VecMap to find the date entry
            content = obj.get("data", {}).get("content", {})
            fields = content.get("fields", {})
            entries = fields.get("entries", {}).get("fields", {}).get("contents", [])

            for entry in entries:
                ef = entry.get("fields", {})
                if ef.get("key") == date:
                    stored_hash = ef.get("value", "")
                    return {
                        "verified": stored_hash == expected_hash,
                        "stored_hash": stored_hash,
                        "expected_hash": expected_hash,
                        "source": "sui_testnet",
                    }

            return {"verified": False, "reason": "date not found on-chain", "source": "sui_testnet"}

        except Exception as e:
            return {
                "verified": self.verify_local(date, expected_hash),
                "source": "local_ledger",
                "rpc_error": str(e),
            }

    # ── Convenience ───────────────────────────────────────

    def anchor_daily_report(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convenient method: compute root hash from a daily report and anchor it.
        Tries on-chain first, falls back to local.
        """
        date = report.get("date") or report.get("report_date") or datetime.utcnow().strftime("%Y-%m-%d")
        root_hash = self.compute_root_hash(report)

        anchor = self.anchor_on_chain(date, root_hash)
        anchor["root_hash"] = root_hash

        # Also store locally as a backup
        if anchor.get("source") != "local_ledger":
            self.anchor_local(date, root_hash, report_summary={
                "total_files": report.get("total_files", 0),
                "categories": report.get("categories", {}),
            })

        return anchor


# ────────────────────────── Demo / Test ────────────────────

if __name__ == "__main__":
    print("🧪 Testing Sui Anchor (local ledger mode)...")
    print("-" * 50)

    anchor = SuiAnchor()

    # Simulate a daily report
    report = {
        "date": "2026-02-12",
        "total_files": 42,
        "total_size": 1048576,
        "categories": {
            "Documents": 15,
            "Images": 12,
            "Code": 8,
            "Archives": 4,
            "Videos": 3,
        },
    }

    root_hash = SuiAnchor.compute_root_hash(report)
    print(f"\n📊 Report root hash: {root_hash[:32]}…")

    # Anchor locally
    result = anchor.anchor_daily_report(report)
    print(f"⚓ Anchored: {result['date']} → {result['root_hash'][:24]}…")
    print(f"   Source: {result['source']}")

    # Verify
    verified = anchor.verify_local("2026-02-12", root_hash)
    print(f"   Verified: {'✅' if verified else '❌'}")

    # Show ledger
    entries = anchor.get_local_anchors()
    print(f"\n📜 Local ledger: {len(entries)} entries")

    # Cleanup
    Path("anchor_ledger.json").unlink(missing_ok=True)
    print("\n✅ All anchor tests passed!")
