"""
Deepurge Workflows – OCR Triggers, File Conversion & Automation
================================================================

Automation engine that adds:
  1. OCR & content-based action triggers (e.g. PDF contains "Total Due" → move to Expenses)
  2. Automatic file conversion (PNG→PDF, auto-unzip)

Author: Samuel Campozano Lopez
Project: Sui Hackathon 2026
"""

import io
import os
import re
import json
import shutil
import zipfile
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable

import fitz  # PyMuPDF – used for OCR-like text extraction
from PIL import Image


# ────────────────────────── OCR Engine ─────────────────────

class OCREngine:
    """
    Extracts text from PDFs and images.

    Uses PyMuPDF for PDFs (native text extraction, no Tesseract needed)
    and basic filename/metadata heuristics for images.
    """

    @staticmethod
    def extract_text_pdf(file_path: Path, max_pages: int = 5) -> str:
        """Extract text from a PDF using PyMuPDF."""
        try:
            doc = fitz.open(str(file_path))
            text_parts = []
            for i in range(min(max_pages, len(doc))):
                text_parts.append(doc[i].get_text())
            doc.close()
            return "\n".join(text_parts)
        except Exception as e:
            print(f"⚠️ OCR PDF error: {e}")
            return ""

    @staticmethod
    def extract_text_image(file_path: Path) -> str:
        """
        Attempt basic text extraction from images via PyMuPDF OCR.
        Falls back to returning empty string if OCR is not available.
        """
        try:
            # PyMuPDF can OCR images if Tesseract is installed
            doc = fitz.open(str(file_path))
            page = doc[0]
            text = page.get_text()
            doc.close()
            return text
        except Exception:
            # OCR not available — return empty; workflow will rely on filename
            return ""

    @staticmethod
    def extract_text(file_path: Path) -> str:
        """Dispatch to the right extractor based on file type."""
        ext = file_path.suffix.lower()
        if ext == ".pdf":
            return OCREngine.extract_text_pdf(file_path)
        elif ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"):
            return OCREngine.extract_text_image(file_path)
        elif ext in (".txt", ".md", ".csv", ".log"):
            try:
                return file_path.read_text(encoding="utf-8", errors="ignore")[:5000]
            except Exception:
                return ""
        return ""


# ────────────────────────── Workflow Rules ─────────────────

class WorkflowRule:
    """
    A single IF→THEN automation rule.

    Parameters
    ----------
    name : str          Human-readable rule name.
    trigger_type : str  "content_match" | "extension_match" | "filename_match"
    trigger_value : str Regex pattern for content, extension list, or filename pattern.
    actions : list      List of action dicts: {"type": "move", "destination": "..."}, etc.
    enabled : bool
    """

    def __init__(
        self,
        name: str,
        trigger_type: str,
        trigger_value: str,
        actions: List[Dict[str, str]],
        enabled: bool = True,
    ):
        self.name = name
        self.trigger_type = trigger_type
        self.trigger_value = trigger_value
        self.actions = actions
        self.enabled = enabled
        self._compiled_re = None
        if trigger_type == "content_match":
            try:
                self._compiled_re = re.compile(trigger_value, re.IGNORECASE)
            except re.error:
                self._compiled_re = re.compile(re.escape(trigger_value), re.IGNORECASE)

    def matches(self, file_path: Path, file_text: str = "") -> bool:
        """Return True if the rule triggers for the given file."""
        if not self.enabled:
            return False

        if self.trigger_type == "content_match":
            if self._compiled_re and self._compiled_re.search(file_text):
                return True

        elif self.trigger_type == "extension_match":
            exts = [e.strip().lower() for e in self.trigger_value.split(",")]
            if file_path.suffix.lower() in exts:
                return True

        elif self.trigger_type == "filename_match":
            pattern = re.compile(self.trigger_value, re.IGNORECASE)
            if pattern.search(file_path.name):
                return True

        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "trigger_type": self.trigger_type,
            "trigger_value": self.trigger_value,
            "actions": self.actions,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WorkflowRule":
        return cls(
            name=d["name"],
            trigger_type=d["trigger_type"],
            trigger_value=d["trigger_value"],
            actions=d.get("actions", []),
            enabled=d.get("enabled", True),
        )


# ────────────────────────── File Converter ─────────────────

class FileConverter:
    """Handles automatic file conversions."""

    @staticmethod
    def png_to_pdf(image_path: Path, output_path: Optional[Path] = None) -> Path:
        """Convert a PNG/JPG image to a single-page PDF."""
        image_path = Path(image_path)
        if output_path is None:
            output_path = image_path.with_suffix(".pdf")

        img = Image.open(image_path)
        if img.mode == "RGBA":
            # PDF doesn't support transparency — composite on white
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        img.save(str(output_path), "PDF", resolution=150.0)
        return output_path

    @staticmethod
    def auto_unzip(zip_path: Path, output_dir: Optional[Path] = None) -> Path:
        """Extract a ZIP archive to a folder of the same name."""
        zip_path = Path(zip_path)
        if output_dir is None:
            output_dir = zip_path.parent / zip_path.stem

        output_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(output_dir)

        return output_dir

    @staticmethod
    def images_to_pdf(image_paths: List[Path], output_path: Path) -> Path:
        """Merge multiple images into a single multi-page PDF."""
        if not image_paths:
            raise ValueError("No images provided")

        imgs = []
        for p in image_paths:
            img = Image.open(p)
            if img.mode == "RGBA":
                bg = Image.new("RGB", img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[3])
                img = bg
            elif img.mode != "RGB":
                img = img.convert("RGB")
            imgs.append(img)

        first, *rest = imgs
        first.save(str(output_path), "PDF", resolution=150.0, save_all=True, append_images=rest)
        return output_path


# ────────────────────────── Workflow Engine ─────────────────

class WorkflowEngine:
    """
    Evaluates automation rules against incoming files.

    Integrates with the main Deepurge agent: when a new file arrives,
    the engine runs OCR (if needed), checks every enabled rule, and
    executes the matched actions.
    """

    # Default built-in rules
    DEFAULT_RULES = [
        {
            "name": "Expenses Trigger",
            "trigger_type": "content_match",
            "trigger_value": r"total\s*due|amount\s*due|invoice\s*total|factura",
            "actions": [
                {"type": "move", "destination": "Expenses"},
                {"type": "tag", "value": "expense"},
                {"type": "walrus_backup", "value": "true"},
            ],
            "enabled": True,
        },
        {
            "name": "Receipt Auto-Save",
            "trigger_type": "content_match",
            "trigger_value": r"receipt|recibo|order\s*confirmation|payment\s*received",
            "actions": [
                {"type": "move", "destination": "Receipts"},
                {"type": "walrus_backup", "value": "true"},
            ],
            "enabled": True,
        },
        {
            "name": "Auto-Unzip Archives",
            "trigger_type": "extension_match",
            "trigger_value": ".zip",
            "actions": [
                {"type": "unzip"},
            ],
            "enabled": True,
        },
        {
            "name": "Screenshot to PDF",
            "trigger_type": "filename_match",
            "trigger_value": r"screenshot|captura|snip|screen",
            "actions": [
                {"type": "convert_to_pdf"},
            ],
            "enabled": False,  # Disabled by default; user can turn on
        },
    ]

    def __init__(self, rules: Optional[List[Dict]] = None, organized_folder: Optional[Path] = None):
        self.organized_folder = organized_folder or Path.home() / "Downloads" / "Organized"
        self.rules: List[WorkflowRule] = []
        self.execution_log: List[Dict[str, Any]] = []

        rule_dicts = rules or self.DEFAULT_RULES
        for rd in rule_dicts:
            self.rules.append(WorkflowRule.from_dict(rd))

    # ── Rule management ───────────────────────────────────

    def add_rule(self, rule_dict: Dict[str, Any]):
        """Add a new rule at runtime."""
        self.rules.append(WorkflowRule.from_dict(rule_dict))

    def remove_rule(self, name: str):
        """Remove a rule by name."""
        self.rules = [r for r in self.rules if r.name != name]

    def toggle_rule(self, name: str, enabled: bool):
        """Enable/disable a rule."""
        for r in self.rules:
            if r.name == name:
                r.enabled = enabled
                return True
        return False

    def get_rules(self) -> List[Dict[str, Any]]:
        """Return all rules as dicts."""
        return [r.to_dict() for r in self.rules]

    # ── Execution ─────────────────────────────────────────

    def evaluate(
        self,
        file_path: Path,
        vault_callback: Optional[Callable] = None,
    ) -> List[Dict[str, Any]]:
        """
        Run all rules against a file.

        Parameters
        ----------
        file_path : Path
            The file to evaluate.
        vault_callback : callable, optional
            Called with (file_path,) when a rule requests ``walrus_backup``.

        Returns
        -------
        list of dicts
            Each entry documents a fired rule and actions taken.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            return []

        # Extract text lazily (only for content_match rules)
        needs_ocr = any(
            r.trigger_type == "content_match" and r.enabled for r in self.rules
        )
        file_text = OCREngine.extract_text(file_path) if needs_ocr else ""

        results: List[Dict[str, Any]] = []

        for rule in self.rules:
            if rule.matches(file_path, file_text):
                actions_taken = self._execute_actions(file_path, rule, vault_callback)
                entry = {
                    "rule": rule.name,
                    "file": file_path.name,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "actions": actions_taken,
                }
                results.append(entry)
                self.execution_log.append(entry)

        return results

    def _execute_actions(
        self,
        file_path: Path,
        rule: WorkflowRule,
        vault_callback: Optional[Callable],
    ) -> List[Dict[str, str]]:
        """Execute all actions for a triggered rule."""
        taken = []

        for action in rule.actions:
            atype = action.get("type", "")

            try:
                if atype == "move":
                    dest_name = action.get("destination", "Workflows")
                    dest = self.organized_folder / dest_name
                    dest.mkdir(parents=True, exist_ok=True)
                    new_path = dest / file_path.name
                    counter = 1
                    while new_path.exists():
                        new_path = dest / f"{file_path.stem}_{counter}{file_path.suffix}"
                        counter += 1
                    shutil.move(str(file_path), str(new_path))
                    taken.append({"type": "move", "destination": str(new_path), "status": "ok"})
                    file_path = new_path  # update reference for subsequent actions

                elif atype == "tag":
                    taken.append({"type": "tag", "value": action.get("value", ""), "status": "ok"})

                elif atype == "walrus_backup":
                    if vault_callback:
                        vault_callback(file_path)
                        taken.append({"type": "walrus_backup", "status": "ok"})
                    else:
                        taken.append({"type": "walrus_backup", "status": "skipped", "reason": "no vault"})

                elif atype == "unzip":
                    if file_path.suffix.lower() == ".zip":
                        out = FileConverter.auto_unzip(file_path)
                        taken.append({"type": "unzip", "output": str(out), "status": "ok"})

                elif atype == "convert_to_pdf":
                    if file_path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
                        pdf = FileConverter.png_to_pdf(file_path)
                        taken.append({"type": "convert_to_pdf", "output": str(pdf), "status": "ok"})

            except Exception as e:
                taken.append({"type": atype, "status": "error", "error": str(e)})

        return taken

    def get_execution_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return the last N execution log entries."""
        return self.execution_log[-limit:]


# ────────────────────────── Quick Test ─────────────────────

if __name__ == "__main__":
    print("🧪 Testing Workflow Engine...")
    print("-" * 50)

    engine = WorkflowEngine()

    # Show built-in rules
    print("\n📋 Built-in rules:")
    for r in engine.get_rules():
        status = "✅" if r["enabled"] else "⏸️"
        print(f"  {status} {r['name']} ({r['trigger_type']}: {r['trigger_value'][:40]})")
        for a in r["actions"]:
            print(f"      → {a['type']}: {a.get('destination', a.get('value', ''))}")

    # Test file converter
    print("\n🔄 File Converter tests:")
    test_img = Path("_test_convert.png")
    try:
        img = Image.new("RGB", (800, 600), color=(73, 109, 137))
        img.save(str(test_img))
        pdf = FileConverter.png_to_pdf(test_img)
        print(f"  ✅ PNG→PDF: {pdf} ({pdf.stat().st_size:,} bytes)")
        pdf.unlink(missing_ok=True)
    finally:
        test_img.unlink(missing_ok=True)

    print("\n✅ All workflow tests passed!")
