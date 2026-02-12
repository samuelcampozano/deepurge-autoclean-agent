"""
Deepurge Vault – Encrypted Decentralized File Storage on Walrus
================================================================

Allows users to encrypt files with AES-256-GCM on the client side,
upload the ciphertext to Walrus, and generate shareable links that
can only be decrypted with the original key.

Author: Samuel Campozano Lopez
Project: Sui Hackathon 2026
"""

import os
import io
import json
import base64
import hashlib
import secrets
import mimetypes
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# ────────────────────────── Crypto helpers ──────────────────

def generate_vault_key() -> bytes:
    """Generate a random 256-bit AES key."""
    return AESGCM.generate_key(bit_length=256)


def key_to_hex(key: bytes) -> str:
    """Encode key as hex string for safe storage / sharing."""
    return key.hex()


def hex_to_key(hex_str: str) -> bytes:
    """Decode a hex-encoded AES key."""
    return bytes.fromhex(hex_str)


def encrypt_bytes(data: bytes, key: bytes) -> Tuple[bytes, bytes]:
    """
    Encrypt *data* with AES-256-GCM.

    Returns (nonce, ciphertext).  Nonce is 12 bytes.
    """
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, data, None)
    return nonce, ciphertext


def decrypt_bytes(nonce: bytes, ciphertext: bytes, key: bytes) -> bytes:
    """Decrypt AES-256-GCM ciphertext."""
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


def encrypt_file(file_path: Path, key: bytes) -> Tuple[bytes, bytes]:
    """Read a file and return (nonce, ciphertext)."""
    data = file_path.read_bytes()
    return encrypt_bytes(data, key)


def decrypt_to_file(nonce: bytes, ciphertext: bytes, key: bytes, output_path: Path):
    """Decrypt ciphertext and write the plaintext to *output_path*."""
    plaintext = decrypt_bytes(nonce, ciphertext, key)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(plaintext)
    return output_path


# ────────────────────────── Walrus Vault ───────────────────

class DeepurgeVault:
    """
    Encrypted file vault backed by Walrus decentralized storage.

    Workflow
    --------
    1. ``vault.store(file_path)`` → encrypts → uploads to Walrus → returns manifest
    2. ``vault.retrieve(blob_id, key_hex)`` → downloads → decrypts → returns bytes
    3. ``vault.share_link(blob_id, key_hex)`` → returns a URL-safe shareable link
    """

    TESTNET_AGGREGATOR = "https://aggregator.walrus-testnet.walrus.space"
    TESTNET_PUBLISHER = "https://publisher.walrus-testnet.walrus.space"

    def __init__(
        self,
        aggregator_url: Optional[str] = None,
        publisher_url: Optional[str] = None,
        epochs: int = 10,
    ):
        self.aggregator_url = aggregator_url or self.TESTNET_AGGREGATOR
        self.publisher_url = publisher_url or self.TESTNET_PUBLISHER
        self.epochs = epochs

    # ── Upload ────────────────────────────────────────────

    def store(
        self,
        file_path: Path,
        key: Optional[bytes] = None,
        epochs: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Encrypt a file and upload to Walrus.

        Returns a *vault manifest* dict:
        {
            "blob_id":    "<walrus blob id>",
            "key_hex":    "<hex-encoded AES key>",
            "nonce_hex":  "<hex-encoded 12-byte nonce>",
            "file_name":  "original.pdf",
            "file_size":  12345,
            "mime_type":  "application/pdf",
            "sha256":     "<sha256 of plaintext>",
            "encrypted_size": 12361,
            "uploaded_at": "...",
            "walrus_url": "..."
        }
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        plaintext = file_path.read_bytes()
        plaintext_hash = hashlib.sha256(plaintext).hexdigest()
        mime = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"

        if key is None:
            key = generate_vault_key()

        nonce, ciphertext = encrypt_bytes(plaintext, key)

        # Upload ciphertext to Walrus
        blob_id = self._upload_raw(ciphertext, epochs)

        if blob_id is None:
            raise RuntimeError("Walrus upload failed")

        manifest = {
            "blob_id": blob_id,
            "key_hex": key_to_hex(key),
            "nonce_hex": nonce.hex(),
            "file_name": file_path.name,
            "file_size": len(plaintext),
            "mime_type": mime,
            "sha256": plaintext_hash,
            "encrypted_size": len(ciphertext),
            "uploaded_at": datetime.utcnow().isoformat() + "Z",
            "walrus_url": f"{self.aggregator_url}/v1/blobs/{blob_id}",
        }
        return manifest

    def store_folder(
        self,
        folder_path: Path,
        key: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        """
        Encrypt and upload every file in *folder_path* with the same key.

        Returns a *folder manifest* containing a list of per-file manifests
        plus a root hash (SHA-256 of all individual hashes concatenated).
        """
        folder_path = Path(folder_path)
        if not folder_path.is_dir():
            raise NotADirectoryError(f"Not a directory: {folder_path}")

        if key is None:
            key = generate_vault_key()

        manifests: List[Dict[str, Any]] = []
        hash_chain = hashlib.sha256()

        for fp in sorted(folder_path.rglob("*")):
            if fp.is_file():
                try:
                    m = self.store(fp, key=key)
                    m["relative_path"] = str(fp.relative_to(folder_path))
                    manifests.append(m)
                    hash_chain.update(m["sha256"].encode())
                except Exception as e:
                    manifests.append({
                        "file_name": fp.name,
                        "relative_path": str(fp.relative_to(folder_path)),
                        "error": str(e),
                    })

        folder_manifest = {
            "type": "vault_folder",
            "folder_name": folder_path.name,
            "key_hex": key_to_hex(key),
            "file_count": len(manifests),
            "root_hash": hash_chain.hexdigest(),
            "files": manifests,
            "uploaded_at": datetime.utcnow().isoformat() + "Z",
        }

        # Upload the manifest itself (unencrypted metadata, keys stripped)
        safe_manifest = {**folder_manifest, "key_hex": "[REDACTED]"}
        for f in safe_manifest.get("files", []):
            if "key_hex" in f:
                f["key_hex"] = "[REDACTED]"
        manifest_blob_id = self._upload_raw(
            json.dumps(safe_manifest, indent=2).encode()
        )
        folder_manifest["manifest_blob_id"] = manifest_blob_id

        return folder_manifest

    # ── Retrieve ──────────────────────────────────────────

    def retrieve(
        self,
        blob_id: str,
        key_hex: str,
        nonce_hex: str,
    ) -> bytes:
        """Download ciphertext from Walrus and decrypt to bytes."""
        ciphertext = self._download_raw(blob_id)
        if ciphertext is None:
            raise RuntimeError(f"Failed to download blob {blob_id}")

        key = hex_to_key(key_hex)
        nonce = bytes.fromhex(nonce_hex)
        return decrypt_bytes(nonce, ciphertext, key)

    def retrieve_to_file(
        self,
        blob_id: str,
        key_hex: str,
        nonce_hex: str,
        output_path: Path,
    ) -> Path:
        """Download, decrypt, and save to disk."""
        plaintext = self.retrieve(blob_id, key_hex, nonce_hex)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(plaintext)
        return output_path

    # ── Shareable Links ───────────────────────────────────

    @staticmethod
    def create_share_token(blob_id: str, key_hex: str, nonce_hex: str, file_name: str = "") -> str:
        """
        Encode retrieval parameters into a single URL-safe base64 token.

        The token contains everything needed to download & decrypt,
        so anyone with the token can access the file — *no central server*.
        """
        payload = json.dumps({
            "b": blob_id,
            "k": key_hex,
            "n": nonce_hex,
            "f": file_name,
        }, separators=(",", ":"))
        return base64.urlsafe_b64encode(payload.encode()).decode()

    @staticmethod
    def parse_share_token(token: str) -> Dict[str, str]:
        """Decode a share token back into its components."""
        payload = base64.urlsafe_b64decode(token.encode()).decode()
        data = json.loads(payload)
        return {
            "blob_id": data["b"],
            "key_hex": data["k"],
            "nonce_hex": data["n"],
            "file_name": data.get("f", ""),
        }

    def generate_share_link(
        self,
        blob_id: str,
        key_hex: str,
        nonce_hex: str,
        file_name: str = "",
        dashboard_base_url: str = "http://localhost:5050",
    ) -> str:
        """
        Generate a full shareable link pointing at the dashboard.

        The link embeds all decryption info in the URL fragment (#),
        which is never sent to the server — true client-side decryption.
        """
        token = self.create_share_token(blob_id, key_hex, nonce_hex, file_name)
        return f"{dashboard_base_url}/vault/share#{token}"

    # ── Internal transport ────────────────────────────────

    def _upload_raw(self, data: bytes, epochs: Optional[int] = None) -> Optional[str]:
        """PUT raw bytes to Walrus publisher; return blob_id."""
        epochs = epochs or self.epochs
        url = f"{self.publisher_url}/v1/blobs?epochs={epochs}"
        try:
            resp = requests.put(
                url,
                data=data,
                headers={"Content-Type": "application/octet-stream"},
                timeout=120,
            )
            if resp.status_code == 200:
                result = resp.json()
                if "newlyCreated" in result:
                    return result["newlyCreated"]["blobObject"]["blobId"]
                if "alreadyCertified" in result:
                    return result["alreadyCertified"]["blobId"]
            print(f"[WARN] Vault upload failed: HTTP {resp.status_code}")
        except Exception as e:
            print(f"[WARN] Vault upload error: {e}")
        return None

    def _download_raw(self, blob_id: str) -> Optional[bytes]:
        """GET raw bytes from Walrus aggregator."""
        url = f"{self.aggregator_url}/v1/blobs/{blob_id}"
        try:
            resp = requests.get(url, timeout=120)
            if resp.status_code == 200:
                return resp.content
            print(f"[WARN] Vault download failed: HTTP {resp.status_code}")
        except Exception as e:
            print(f"[WARN] Vault download error: {e}")
        return None


# ────────────────────────── Demo / Test ────────────────────

class DeepurgeVaultDemo(DeepurgeVault):
    """
    Demo vault that simulates uploads (no network required).
    """
    _counter = 0

    def _upload_raw(self, data: bytes, epochs: Optional[int] = None) -> Optional[str]:
        DeepurgeVaultDemo._counter += 1
        fake_hash = hashlib.sha256(data).hexdigest()[:32]
        blob_id = f"vault_demo_{fake_hash}_{self._counter}"
        print(f"  🎭 [DEMO] Simulated vault upload ({len(data):,} bytes)")
        return blob_id

    def _download_raw(self, blob_id: str) -> Optional[bytes]:
        print(f"  🎭 [DEMO] Simulated vault download: {blob_id}")
        return None


if __name__ == "__main__":
    print("🧪 Testing Deepurge Vault (demo mode)...")
    print("-" * 50)

    vault = DeepurgeVaultDemo()

    # Create a small test file
    test_file = Path("_vault_test.txt")
    test_file.write_text("Hello from the Deepurge Vault! Encrypted storage test.", encoding="utf-8")

    try:
        # Store
        manifest = vault.store(test_file)
        print(f"\n✅ Stored: {manifest['file_name']}")
        print(f"   Blob ID:  {manifest['blob_id']}")
        print(f"   SHA-256:  {manifest['sha256'][:24]}…")
        print(f"   Key:      {manifest['key_hex'][:24]}…")

        # Share link
        link = vault.generate_share_link(
            manifest["blob_id"],
            manifest["key_hex"],
            manifest["nonce_hex"],
            manifest["file_name"],
        )
        print(f"\n🔗 Share link: {link[:80]}…")

        # Parse token round-trip
        token = link.split("#")[1]
        parsed = vault.parse_share_token(token)
        assert parsed["blob_id"] == manifest["blob_id"]
        assert parsed["key_hex"] == manifest["key_hex"]
        print("   ✅ Token round-trip OK")

        # Local encrypt/decrypt round-trip
        key = hex_to_key(manifest["key_hex"])
        plaintext = test_file.read_bytes()
        enc_nonce, ct = encrypt_file(test_file, key)
        recovered = decrypt_bytes(enc_nonce, ct, key)
        assert recovered == plaintext
        print("   ✅ Encrypt/decrypt round-trip OK")

    finally:
        test_file.unlink(missing_ok=True)

    print("\n✅ All vault tests passed!")
